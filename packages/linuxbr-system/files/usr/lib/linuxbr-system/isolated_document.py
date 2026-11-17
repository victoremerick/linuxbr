"""Abra um único documento em uma sessão descartável, isolada por Bubblewrap."""
import os
import stat
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox


VIEWERS = {
    '.pdf': ('/usr/bin/okular', ()),
    '.txt': ('/usr/bin/kate', ()), '.log': ('/usr/bin/kate', ()), '.csv': ('/usr/bin/kate', ()),
    '.png': ('/usr/bin/gwenview', ()), '.jpg': ('/usr/bin/gwenview', ()),
    '.jpeg': ('/usr/bin/gwenview', ()), '.webp': ('/usr/bin/gwenview', ()),
    '.odt': ('/usr/bin/libreoffice', ('--view', '--norestore')),
    '.docx': ('/usr/bin/libreoffice', ('--view', '--norestore')),
    '.ods': ('/usr/bin/libreoffice', ('--view', '--norestore')),
    '.xlsx': ('/usr/bin/libreoffice', ('--view', '--norestore')),
    '.odp': ('/usr/bin/libreoffice', ('--view', '--norestore')),
    '.pptx': ('/usr/bin/libreoffice', ('--view', '--norestore')),
}


def sandbox_command(document, socket_path):
    source = Path(document).resolve(strict=True)
    if not source.is_file():
        raise ValueError('Escolha um documento comum.')
    try:
        viewer, settings = VIEWERS[source.suffix.casefold()]
    except KeyError:
        raise ValueError('Este formato não possui um visualizador isolado selecionado.') from None
    if not os.access(viewer, os.X_OK):
        raise ValueError('Instale o visualizador necessário pela Loja antes de abrir este formato.')
    target = '/documento/arquivo'+source.suffix.casefold()
    sandbox = ['/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--disable-userns', '--new-session',
               '--die-with-parent', '--clearenv', '--cap-drop', 'ALL', '--hostname', 'linuxbr-documento',
               '--ro-bind', '/usr', '/usr', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
               '--dir', '/home/isolado', '--perms', '0700', '--dir', '/run/painel', '--dir', '/documento',
               '--ro-bind', str(socket_path), '/run/painel/wayland-0',
               '--ro-bind', str(source), target,
               '--setenv', 'HOME', '/home/isolado', '--setenv', 'PATH', '/usr/bin:/bin',
               '--setenv', 'USER', 'isolado', '--setenv', 'XDG_RUNTIME_DIR', '/run/painel',
               '--setenv', 'WAYLAND_DISPLAY', 'wayland-0', '--setenv', 'QT_QPA_PLATFORM', 'wayland',
               '--setenv', 'GDK_BACKEND', 'wayland', '--setenv', 'SAL_USE_VCLPLUGIN', 'gtk3',
               '--setenv', 'LANG', 'pt_BR.UTF-8', '--chdir', '/home/isolado']
    for folder in ('/bin', '/sbin', '/lib', '/lib64'):
        path = Path(folder)
        if path.is_symlink():
            sandbox += ['--symlink', os.readlink(path), folder]
        elif path.is_dir():
            sandbox += ['--ro-bind', folder, folder]
    for folder in ('/etc/fonts', '/etc/ld.so.cache', '/etc/localtime'):
        if Path(folder).exists():
            sandbox += ['--ro-bind', folder, folder]
    return [*sandbox, '--', viewer, *settings, target]


def wayland_socket():
    display = os.environ.get('WAYLAND_DISPLAY')
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if os.geteuid() == 0 or not display or '/' in display or not runtime or not runtime.startswith('/'):
        raise ValueError('Abra o documento em uma sessão Wayland da sua conta.')
    socket = Path(runtime)/display
    try:
        info = socket.lstat()
    except OSError:
        raise ValueError('A conexão com a sessão Wayland está indisponível.') from None
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
        raise ValueError('A conexão Wayland não pertence à sessão atual.')
    return socket


def main():
    app = QApplication(sys.argv)
    if len(sys.argv) > 2:
        raise SystemExit(2)
    document = sys.argv[1] if len(sys.argv) == 2 else QFileDialog.getOpenFileName(
        None, 'Abrir documento isolado', '', 'Documentos compatíveis ('+
        ' '.join('*'+suffix for suffix in VIEWERS)+')')[0]
    if not document:
        return 0
    try:
        args = sandbox_command(document, wayland_socket())
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                close_fds=True)
        if result.returncode:
            raise ValueError('Não foi possível abrir este documento no ambiente isolado.')
    except (OSError, ValueError) as error:
        QMessageBox.warning(None, 'Documento isolado', str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
