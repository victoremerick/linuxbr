#!/usr/bin/python3
"""Dolphin service action; lookup only, never Resolve (which may mount)."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QApplication, QMessageBox
from properties import Properties


def lookup(state, url):
    parsed = urlsplit(url)
    letter = parsed.path.strip('/')
    if parsed.scheme != 'linuxbr' or parsed.netloc or parsed.query or parsed.fragment or len(letter) != 1 or letter not in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        raise ValueError('Selecione uma unidade em Este computador.')
    key = 'system' if letter == 'C' else next((k for k,v in state['data']['letters'].items() if v == letter), None)
    if key and key.startswith('smb:'):
        target = key[4:]
        if target in state['data']['shares']:
            return dict(key=key, name=state['data']['shares'][target], kind='Rede SMB', url=target), letter
    row = next((r for r in state['rows'] if r['key'] == key), None)
    if row is None: raise ValueError('Unidade desconectada ou letra não atribuída.')
    return row, letter


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    process = QProcess()
    def done(code, status):
        try:
            payload = json.loads(bytes(process.readAllStandardOutput()).decode())
            if code or 'error' in payload: raise ValueError(payload.get('error', 'Falha na consulta.'))
            state = payload['result']
            if state.get('error'): raise ValueError(state['error'])
            row, letter = lookup(state, sys.argv[1] if len(sys.argv) == 2 else '')
            Properties(row, letter).exec()
        except (ValueError, KeyError) as error:
            QMessageBox.warning(None, 'Propriedades da unidade', str(error))
        app.quit()
    process.finished.connect(done)
    def failed(error):
        if error == QProcess.ProcessError.FailedToStart:
            QMessageBox.warning(None, 'Propriedades da unidade', 'Não foi possível consultar o serviço.')
            app.quit()
    process.errorOccurred.connect(failed)
    process.start(sys.executable, [str(Path(__file__).with_name('client.py')), 'list'])
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
