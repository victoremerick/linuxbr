"""Boot the original release ISO in QEMU and verify each live Plasma session."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time


def guest_probe(marker, firmware, version):
    return f'''#!/bin/sh
set -eu
report() {{ printf '%s %s\\n' {shlex.quote(marker)} "$1" >/dev/ttyS0; }}
if ! test -d /run/live/medium; then report FAIL-live; exit 1; fi
actual=bios
if test -d /sys/firmware/efi; then actual=uefi; fi
if test "$actual" != {shlex.quote(firmware)}; then report FAIL-firmware; exit 1; fi
release=$(dpkg-query -W -f='${{Version}}' linuxbr-release)
if test "$release" != {shlex.quote(version)}; then report FAIL-version; exit 1; fi
if ! systemctl is-active --quiet display-manager; then report FAIL-sddm; exit 1; fi
desktop_session() {{
    pgrep -u user -x plasmashell >/dev/null || return 1
    for session in $(loginctl show-user user -p Sessions --value); do
        type=$(loginctl show-session "$session" -p Type --value)
        case "$type" in
            wayland|x11) printf '%s\\n' "$type"; return 0 ;;
        esac
    done
    return 1
}}
remaining=90
until session_type=$(desktop_session); do
    remaining=$((remaining - 1))
    if test "$remaining" = 0; then report FAIL-plasma; exit 1; fi
    sleep 1
done
report "PASS $actual $release $session_type"
'''.encode()


def serve_probe(payload):
    class ProbeHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/probe.sh':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = HTTPServer(('127.0.0.1', 0), ProbeHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


class Monitor:
    def __init__(self, path, process):
        self.path = path
        self.process = process

    def command(self, operation, **arguments):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(10)
            connection.connect(str(self.path))
            with connection.makefile('rwb') as stream:
                if 'QMP' not in json.loads(stream.readline()):
                    raise RuntimeError('Monitor QMP inválido.')
                for command, params in (('qmp_capabilities', {}), (operation, arguments)):
                    stream.write((json.dumps({'execute': command, 'arguments': params})+'\n').encode())
                    stream.flush()
                    while True:
                        answer = json.loads(stream.readline())
                        if 'error' in answer:
                            raise RuntimeError(answer['error'])
                        if 'return' in answer:
                            break
                return answer['return']

    def keys(self, *codes):
        self.command('send-key', keys=[{'type': 'qcode', 'data': code} for code in codes],
                     **{'hold-time': 50})
        time.sleep(0.10)

    def type_command(self, text):
        symbols = {' ': ('spc',), '-': ('minus',), '.': ('dot',), '/': ('ro',),
                   ':': ('shift', 'slash')}
        for character in text:
            if character in symbols:
                self.keys(*symbols[character])
            elif character.isupper():
                self.keys('shift', character.lower())
            else:
                self.keys(character)
        self.keys('ret')

    def wait_screen(self, screen, deadline, predicate, description):
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('QEMU encerrou antes de '+description+'.')
            if self.path.is_socket():
                self.command('screendump', filename=str(screen))
                text = subprocess.check_output(
                    ['tesseract', str(screen), 'stdout', '--psm', '11'],
                    text=True, stderr=subprocess.DEVNULL, timeout=15).lower()
                if predicate(text):
                    return text
            time.sleep(3)
        raise RuntimeError('Tempo excedido aguardando '+description+'.')


def check_boot(iso, evidence, version, firmware, timeout):
    marker = 'LINUXBR-QA-'+secrets.token_hex(12)
    server = serve_probe(guest_probe(marker, firmware, version))
    try:
        with tempfile.TemporaryDirectory(prefix='linuxbr-iso-qa-') as temporary:
            work = Path(temporary)
            serial = evidence / f'{firmware}-serial.log'
            screen = evidence / f'{firmware}-last-screen.ppm'
            qmp = work / 'qmp.sock'
            forward = f'guestfwd=tcp:10.0.2.100:8888-tcp:127.0.0.1:{server.server_port}'
            use_kvm = os.access('/dev/kvm', os.R_OK | os.W_OK)
            accel = ['-enable-kvm', '-cpu', 'host'] if use_kvm else ['-accel', 'tcg,thread=multi']
            args = ['qemu-system-x86_64', '-machine', 'q35', *accel,
                    '-m', os.environ['RAM_MB'], '-smp', os.environ['CPUS'], '-display', 'none',
                    '-device', 'VGA,edid=on,xres=1280,yres=768', '-device', 'virtio-rng-pci',
                    '-nic', 'user,model=virtio-net-pci,restrict=on,'+forward,
                    '-qmp', f'unix:{qmp},server=on,wait=off', '-serial', f'file:{serial}',
                    '-no-reboot', '-boot', 'order=d',
                    '-drive', f'file={iso},media=cdrom,format=raw,readonly=on']
            if firmware == 'uefi':
                variables = work / 'vars.fd'
                shutil.copyfile(os.environ['OVMF_VARS_TEMPLATE'], variables)
                code = os.environ['OVMF_CODE']
                args.extend(['-drive', f'if=pflash,format=raw,readonly=on,file={code}',
                             '-drive', f'if=pflash,format=raw,file={variables}'])
            with (evidence / f'{firmware}-qemu.log').open('wb') as output:
                process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output,
                                           stderr=subprocess.STDOUT)
                try:
                    verify_session(Monitor(qmp, process), screen, serial, evidence,
                                   firmware, version, marker, time.monotonic()+timeout, use_kvm)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
    finally:
        server.shutdown()
        server.server_close()


def verify_session(monitor, screen, serial, evidence, firmware, version, marker, deadline, kvm):
    print(f'Iniciando Live {firmware.upper()} com {"KVM" if kvm else "TCG"}.', flush=True)

    def login_screen(text):
        return 'senha' in text and re.search(r'linux\s*br', text)

    boot = monitor.wait_screen(screen, deadline, lambda text: login_screen(text)
                               or re.search(r'iniciar\s+linux\s*br', text),
                               'menu de boot ou login gráfico')
    if not login_screen(boot):
        shutil.copyfile(screen, evidence / f'{firmware}-boot-menu.ppm')
        monitor.keys('ret')
        monitor.wait_screen(screen, deadline, login_screen, 'login gráfico')
    shutil.copyfile(screen, evidence / f'{firmware}-greeter.ppm')
    monitor.type_command('live')
    monitor.wait_screen(screen, deadline, lambda text: not login_screen(text), 'entrada no desktop')
    time.sleep(25 if kvm else 45)
    monitor.command('screendump', filename=str(evidence / f'{firmware}-desktop.ppm'))
    monitor.keys('ctrl', 'alt', 'f6')
    console = monitor.wait_screen(screen, deadline, lambda text: re.search(
        r'user\s*[@©]\s*linuxbr|linuxbr\s+login\s*:\s*$', text, re.M), 'console Live')
    if not re.search(r'user\s*[@©]\s*linuxbr', console):
        monitor.type_command('user')
        monitor.wait_screen(screen, deadline, lambda text: 'password' in text or 'senha' in text,
                            'senha do console Live')
        monitor.type_command('live')
        monitor.wait_screen(screen, deadline, lambda text: re.search(r'user\s*[@©]\s*linuxbr', text),
                            'prompt do console Live')
    monitor.type_command('curl -fsS http://10.0.2.100:8888/probe.sh -o /tmp/probe.sh')
    time.sleep(4)
    monitor.type_command('sudo sh /tmp/probe.sh')
    while time.monotonic() < deadline:
        data = serial.read_text(errors='replace') if serial.exists() else ''
        outcome = re.search(re.escape(marker)+r' ([^\r\n]+)', data)
        if outcome:
            passed = re.fullmatch(re.escape(f'PASS {firmware} {version}')+r' (wayland|x11)', outcome.group(1))
            if not passed:
                raise RuntimeError('Verificação do guest falhou: '+outcome.group(1))
            result = {'status': 'PASS', 'id': f'live-{firmware}', 'version': version,
                      'iso_sha256': (evidence / 'iso.sha256').read_text().split()[0],
                      'session_type': passed.group(1), 'acceleration': 'kvm' if kvm else 'tcg',
                      'serial_log': serial.name}
            (evidence / f'{firmware}-result.json').write_text(json.dumps(result, indent=2)+'\n')
            print(f'Live {firmware.upper()} aprovado pelo guest.', flush=True)
            return
        if monitor.process.poll() is not None:
            break
        time.sleep(3)
    monitor.command('screendump', filename=str(screen))
    raise RuntimeError('O console Live não confirmou a sessão no serial.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iso', type=Path)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('version')
    parser.add_argument('--timeout', type=int, default=600, help='segundos por boot')
    args = parser.parse_args()
    for binary in ('qemu-system-x86_64', 'tesseract'):
        if not shutil.which(binary):
            parser.exit(1, f'Comando ausente: {binary}\n')
    for firmware in ('uefi', 'bios'):
        try:
            check_boot(args.iso, args.evidence, args.version, firmware, args.timeout)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            parser.exit(1, f'Live {firmware.upper()} pendente. {error}\n')


if __name__ == '__main__':
    main()
