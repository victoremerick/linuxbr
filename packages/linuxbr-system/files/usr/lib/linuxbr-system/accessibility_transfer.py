"""Transfer a limited set of Plasma input accessibility preferences."""

import json
from pathlib import Path
import subprocess
import sys

from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from store_sources import atomic_write


TITLE = 'Transferir preferências de acessibilidade'
SCHEMA = 'linuxbr-accessibility-1'
FIELDS = {
    'StickyKeys': ('Keyboard', 'Teclas de aderência', False),
    'SlowKeys': ('Keyboard', 'Teclas lentas', False),
    'SlowKeysDelay': ('Keyboard', 'Atraso das teclas lentas (ms)', 500),
    'BounceKeys': ('Keyboard', 'Filtro de teclas repetidas', False),
    'BounceKeysDelay': ('Keyboard', 'Intervalo do filtro (ms)', 500),
    'MouseKeys': ('Mouse', 'Controlar o mouse pelo teclado', False),
}


def setting(command, group, key, *args):
    result = subprocess.run(
        [command, '--file', 'kaccessrc', '--group', group, '--key', key, *args],
        check=True, capture_output=True, text=True, timeout=5
    )
    return result.stdout.strip()


def read_preferences():
    values = {}
    for key, (group, _, default) in FIELDS.items():
        raw = setting('kreadconfig6', group, key, '--default', str(default).lower())
        if type(default) is bool:
            spelling = raw.lower()
            if spelling not in ('true', 'false', 'on', 'off', 'yes', 'no', '1', '0'):
                raise ValueError('A configuração de acessibilidade contém um valor inválido.')
            values[key] = spelling in ('true', 'on', 'yes', '1')
        else:
            values[key] = int(raw)
    return validate(dict(schema=SCHEMA, preferences=values))


def validate(record):
    if not isinstance(record, dict) or record.keys() != {'schema', 'preferences'} or record['schema'] != SCHEMA:
        raise ValueError('Escolha um arquivo de acessibilidade exportado pelo Linux BR.')
    values = record['preferences']
    if not isinstance(values, dict) or values.keys() != FIELDS.keys():
        raise ValueError('O conjunto de preferências está incompleto ou contém campos desconhecidos.')
    for key, (_, _, default) in FIELDS.items():
        value = values[key]
        if type(value) is not type(default) or type(value) is int and not 0 <= value <= 10000:
            raise ValueError('O arquivo contém um tipo ou valor de preferência inválido.')
    return values


def write_preferences(values):
    before = read_preferences()
    written = []
    try:
        for key, value in values.items():
            if before[key] != value:
                setting('kwriteconfig6', FIELDS[key][0], key, str(value).lower())
                written.append(key)
        if read_preferences() != values:
            raise ValueError('Algumas preferências são bloqueadas neste computador.')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        try:
            for key in reversed(written):
                setting('kwriteconfig6', FIELDS[key][0], key, str(before[key]).lower())
            if read_preferences() != before:
                raise ValueError
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ValueError('A importação falhou. Confira as preferências em Acessibilidade.') from error
        raise


def main():
    app = QApplication(sys.argv)
    options = ['Exportar preferências', 'Importar preferências']
    choice, accepted = QInputDialog.getItem(None, TITLE, 'O que deseja fazer?', options, editable=False)
    if not accepted:
        return 0
    try:
        if choice == options[0]:
            filename, _ = QFileDialog.getSaveFileName(None, TITLE, 'linuxbr-acessibilidade.json', 'JSON (*.json)')
            if filename:
                record = dict(schema=SCHEMA, preferences=read_preferences())
                atomic_write(Path(filename), (json.dumps(record, indent=2) + '\n').encode(), 0o600)
        else:
            filename, _ = QFileDialog.getOpenFileName(None, TITLE, '', 'JSON (*.json)')
            if not filename:
                return 0
            with Path(filename).open('rb') as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise ValueError('O arquivo de preferências excede 4 KiB.')
            values = validate(json.loads(raw))
            preview = '\n'.join(
                f'{label} — {("Ativado" if values[key] else "Desativado") if type(default) is bool else values[key]}'
                for key, (_, label, default) in FIELDS.items()
            )
            if QMessageBox.question(None, TITLE, preview + '\n\nAplicar estas preferências?') == QMessageBox.StandardButton.Yes:
                write_preferences(values)
                QMessageBox.information(None, TITLE, 'Preferências salvas. Encerre e inicie a sessão para aplicar.')
    except (OSError, ValueError, subprocess.SubprocessError):
        QMessageBox.warning(None, TITLE, 'A transferência falhou. Confira o arquivo e as preferências em Acessibilidade.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
