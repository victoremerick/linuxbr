"""Offline conversion and read-only access to virtual disks."""
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile

from virtualization_transfer import validate_disk


GIB = 1024 ** 3


def local_disk(filename):
    source = Path(filename)
    if not source.is_absolute() or source.is_symlink() or not stat.S_ISREG(source.stat().st_mode):
        raise ValueError('Selecione um arquivo de disco local, sem links simbólicos.')
    return source


def run(argv, cancelled=lambda: False, limit=900):
    with tempfile.TemporaryFile() as errors:
        with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=errors) as process:
            try:
                for _ in range(limit):
                    if cancelled():
                        raise ValueError('Operação cancelada.')
                    try:
                        output, _ = process.communicate(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        continue
                else:
                    raise ValueError('A operação excedeu o tempo de espera.')
                if process.returncode:
                    errors.seek(0)
                    raise ValueError(errors.read(8192).decode(errors='replace').strip()
                                     or 'O utilitário não concluiu a leitura do disco.')
                return output
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


def qemu_img(*args, cancelled=lambda: False, limit=900):
    program = shutil.which('qemu-img')
    if not program:
        raise ValueError('Instale o pacote qemu-utils para usar esta ferramenta.')
    return run([program, *args], cancelled, limit)


def hyperv_format(source):
    formats = {'.vhd': 'vpc', '.vhdx': 'vhdx'}
    format_name = formats.get(source.suffix.casefold())
    if not format_name:
        raise ValueError('Selecione uma imagem VHD ou VHDX.')
    with source.open('rb') as handle:
        header = handle.read(8)
        if format_name == 'vpc':
            handle.seek(-512, os.SEEK_END)
            if handle.read(8) != b'conectix':
                raise ValueError('Rodapé do disco VHD inválido.')
            handle.seek(52, os.SEEK_CUR)
            if int.from_bytes(handle.read(4), 'big') not in (2, 3):
                raise ValueError('Exporte um VHD independente no Hyper-V antes de importar.')
        elif header != b'vhdxfile':
            raise ValueError('Cabeçalho do disco VHDX inválido.')
    return format_name


def hyperv_preview(filename):
    source = local_disk(filename)
    format_name = hyperv_format(source)
    data = json.loads(qemu_img('info', '-f', format_name, '--output=json', str(source), limit=30))
    if data.get('backing-filename'):
        raise ValueError('Exporte um disco independente no Hyper-V antes de importar.')
    capacity = data.get('virtual-size')
    if type(capacity) is not int or not 0 < capacity <= 2048 * GIB:
        raise ValueError('A capacidade do disco está fora do intervalo de importação.')
    with tempfile.TemporaryDirectory(prefix='linuxbr-hyperv-') as directory:
        boot = Path(directory) / 'inicio.raw'
        qemu_img('dd', '-f', format_name, '-O', 'raw', 'bs=512', 'count=16',
                 'if=' + str(source), 'of=' + str(boot), limit=30)
        data = boot.read_bytes()
    scheme = 'GPT' if any(data[offset:offset + 8] == b'EFI PART' for offset in (512, 4096)) else (
        'MBR' if data[510:512] == b'\x55\xaa' and any(data[446:510]) else 'Indeterminado')
    firmware = {'GPT': 'UEFI', 'MBR': 'BIOS legado'}.get(scheme, 'Confirme no hospedeiro de origem')
    return dict(format=format_name, capacity=capacity, scheme=scheme, firmware=firmware)


def chain(filename):
    source = local_disk(filename)
    data = json.loads(qemu_img('info', '-f', 'qcow2', '--backing-chain', '--output=json',
                               str(source), limit=45))
    return [dict(path=row.get('filename', ''), format=row.get('format', ''),
                 capacity=row.get('virtual-size', 0), parent=row.get('backing-filename', ''))
            for row in data]


def convert(filename, destination, capacity, source_format, cancelled=lambda: False):
    source = local_disk(filename)
    if source_format in ('vpc', 'vhdx'):
        if hyperv_format(source) != source_format:
            raise ValueError('A imagem mudou após a revisão.')
    elif source_format != 'qcow2':
        raise ValueError('Formato de origem inválido.')
    output = Path(destination)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError('Informe o caminho de um novo arquivo QCOW2.')
    with tempfile.TemporaryDirectory(prefix='.linuxbr-virtual-', dir=output.parent) as directory:
        copy = Path(directory) / 'disco.qcow2'
        qemu_img('convert', '-f', source_format, '-O', 'qcow2', str(source), str(copy), cancelled=cancelled)
        validate_disk(copy, 'qcow2', capacity)
        qemu_img('check', '-f', 'qcow2', str(copy), cancelled=cancelled)
        copy.chmod(0o600)
        with copy.open('rb') as stream:
            os.fsync(stream.fileno())
        if cancelled():
            raise ValueError('Operação cancelada.')
        os.link(copy, output, follow_symlinks=False)
    return str(output)


def restore_file(filename, format_name, guest_path, destination, cancelled=lambda: False):
    source = local_disk(filename)
    if format_name not in ('qcow2', 'raw'):
        raise ValueError('O leitor de arquivos aceita imagens QCOW2 e RAW.')
    path = PurePosixPath(guest_path)
    if not path.is_absolute() or '..' in path.parts or len(path.parts) < 2 or '\x00' in guest_path:
        raise ValueError('Informe o caminho absoluto de um arquivo do convidado.')
    output = Path(destination)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError('Selecione o destino de um novo arquivo.')
    guestfish = shutil.which('guestfish')
    if not guestfish:
        raise ValueError('Ative Leitura de discos de máquinas virtuais em Recursos do Linux BR para instalar o guestfish.')
    with tempfile.TemporaryDirectory(prefix='.linuxbr-restore-', dir=output.parent) as directory:
        recovered = Path(directory) / 'arquivo'
        run([guestfish, '--ro', '--format=' + format_name, '-a', str(source), '-i', 'download',
             str(path), str(recovered)], cancelled)
        recovered.chmod(0o600)
        if cancelled():
            raise ValueError('Operação cancelada.')
        os.link(recovered, output, follow_symlinks=False)
    return str(output)
