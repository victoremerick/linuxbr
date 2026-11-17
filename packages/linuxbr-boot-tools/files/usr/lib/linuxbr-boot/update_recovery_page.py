"""Desktop entry point for offline recovery of a managed update."""
import json
from pathlib import Path
import sys

from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel,
                             QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)


BACKEND = '/usr/lib/linuxbr-boot/update_recovery.py'


class UpdateRecovery(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Recuperar atualização — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('edit-undo'))
        self.resize(720, 500)
        self.plan = None
        self.process = None
        body = QVBoxLayout(self)
        live = Path('/run/live/medium').is_dir()
        message = (
            'Escolha a partição do Linux BR. O assistente confere o último ponto de atualização '
            'gerenciada e mostra o plano antes de restaurar.'
            if live else
            'Reinicie pela mídia live do Linux BR no mesmo modo BIOS ou UEFI da instalação. '
            'Abra Recuperação → Recuperar atualização e escolha a partição do sistema. '
            'A mídia live pode restaurar o sistema mesmo sem rede ou desktop funcional.'
        )
        intro = QLabel(message)
        intro.setWordWrap(True)
        body.addWidget(intro)
        self.devices = QComboBox()
        label = QLabel('&Partição da instalação')
        label.setBuddy(self.devices)
        body.addWidget(label)
        body.addWidget(self.devices)
        self.devices.currentIndexChanged.connect(self.invalidate)
        self.details = QPlainTextEdit(readOnly=True)
        self.details.setAccessibleName('Plano e resultado da recuperação')
        self.details.setMaximumBlockCount(180)
        body.addWidget(self.details)
        buttons = QHBoxLayout()
        self.review = QPushButton(QIcon.fromTheme('edit-find'), 'Testar recuperação…', clicked=self.review_point)
        self.compare = QPushButton(QIcon.fromTheme('document-compare'), 'Comparar pontos…', clicked=self.compare_points)
        self.reinstall = QPushButton(QIcon.fromTheme('system-software-install'), 'Planejar reinstalação…',
                                     clicked=self.plan_reinstall)
        self.apply = QPushButton(QIcon.fromTheme('edit-undo'), 'Restaurar atualização…', clicked=self.confirm)
        self.close_button = QPushButton(QIcon.fromTheme('window-close'), 'Fechar', clicked=self.reject)
        for button in (self.review, self.compare, self.apply, self.close_button):
            button.setMinimumHeight(44)
            buttons.addWidget(button)
        body.addLayout(buttons)
        self.reinstall.setMinimumHeight(44)
        body.addWidget(self.reinstall, alignment=Qt.AlignmentFlag.AlignLeft)
        self.invalidate()
        if live:
            self.run('devices')

    def invalidate(self):
        self.plan = None
        self.details.clear()
        self.controls()

    def controls(self):
        busy = self.process is not None
        self.devices.setEnabled(not busy and self.devices.count() > 1)
        self.review.setEnabled(not busy and bool(self.devices.currentData()))
        self.compare.setEnabled(not busy and bool(self.devices.currentData()))
        self.reinstall.setEnabled(not busy and bool(self.devices.currentData()))
        self.apply.setEnabled(not busy and self.plan is not None)
        self.close_button.setEnabled(not busy)

    def review_point(self):
        uuid = self.devices.currentData()
        if uuid:
            self.invalidate()
            self.run('inspect', '--uuid', uuid)

    def compare_points(self):
        uuid = self.devices.currentData()
        if uuid:
            self.invalidate()
            self.run('points', '--uuid', uuid)

    def plan_reinstall(self):
        uuid = self.devices.currentData()
        if uuid:
            self.invalidate()
            self.run('reinstall-plan', '--uuid', uuid)

    def show_reinstall(self, result):
        lines = [f"Partição do sistema · {result['root']}", '',
                 'Antes de reinstalar, copie os arquivos pessoais para outro disco e confira a cópia.']
        if result['users']:
            lines.extend(['', 'Contas locais encontradas'])
            lines.extend(f"{user['name']} · UID {user['uid']} · {user['home']}" for user in result['users'])
        else:
            lines.append('Nenhuma conta local com pasta pessoal foi detectada.')
        for volume in result['volumes']:
            lines.append('')
            if volume['kind'] == 'independent':
                lines.append(f"{volume['mount']} · {volume['volume']} pode ser reutilizado com "
                             'particionamento manual. Selecione o mesmo ponto de montagem e desmarque Formatar.')
            elif volume['kind'] == 'root':
                lines.append('Pastas no volume raiz precisam da cópia externa. A formatação as remove.')
            else:
                lines.append(f"{volume['mount']} · Revise este volume manualmente antes de prosseguir.")
        lines.extend(['', 'Guarde os nomes e os UIDs para associar as pastas às contas após a reinstalação.',
                      'A análise foi feita sem escrever nos volumes. Abra o instalador quando a cópia estiver pronta.'])
        self.details.setPlainText('\n'.join(lines))

    def choose_points(self, points):
        if len(points) < 2:
            self.details.setPlainText('São necessários dois pontos compatíveis desta instalação.')
            return
        self.details.setPlainText('Escolha os dois pontos para comparar.')
        before, accepted = QInputDialog.getItem(self, 'Comparar pontos', 'Ponto de origem', points,
                                                len(points) - 1, False)
        if not accepted:
            return
        after, accepted = QInputDialog.getItem(self, 'Comparar pontos', 'Ponto de destino',
                                               [entry for entry in points if entry != before], 0, False)
        if accepted:
            self.run('compare', '--uuid', self.devices.currentData(), '--points', before, after)

    def show_comparison(self, reply):
        lines = [f"Origem · {reply['before']}", f"Destino · {reply['after']}"]
        for key, heading in (('packages', 'Pacotes'), ('services', 'Serviços'), ('configuration', 'Configurações')):
            portion = reply[key]
            lines.append(f"\n{heading} · {portion['total']} mudanças")
            for entry in portion['changes']:
                change = f"{entry['action']} · {entry['name']}"
                if 'before' in entry:
                    change += f" · {entry['before'] or '—'} → {entry['after'] or '—'}"
                lines.append(change)
            hidden = portion['total'] - len(portion['changes'])
            if hidden:
                lines.append(f'Mais {hidden} mudanças nesta seção.')
        if reply['incomplete_configuration']:
            lines.append('\nParte dos arquivos de configuração ficou indisponível para comparação.')
        self.details.setPlainText('\n'.join(lines))

    def confirm(self):
        if not self.plan or self.process:
            return
        answer = QMessageBox.question(
            self, 'Confirmar restauração',
            'Restaurar o ponto conferido na partição selecionada? Os arquivos de sistema e os '
            'pacotes voltarão ao estado mostrado. Após conferir o resultado, reinicie pelo disco.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            token = self.plan['token']
            self.plan = None
            self.run('restore', '--uuid', self.devices.currentData(), '--confirm', token)

    def run(self, action, *args):
        if self.process is not None:
            return
        self.details.setPlainText('Aguarde a consulta…' if action != 'restore'
                                  else 'Restauração em andamento. Mantenha a mídia e os discos conectados.')
        process = QProcess(self)
        self.process = process
        output, errors = bytearray(), bytearray()

        def read():
            output.extend(bytes(process.readAllStandardOutput()))
            errors.extend(bytes(process.readAllStandardError()))
            del output[:-65536]
            del errors[:-4096]

        def finish(code, *_):
            if self.process is not process:
                return
            read()
            self.process = None
            process.deleteLater()
            try:
                if code != 0:
                    fallback = ('Não foi possível concluir. Confira a autorização e os discos conectados.'
                                if action != 'restore' else
                                'Restauração não confirmada. Mantenha a mídia live aberta para diagnóstico.')
                    self.details.setPlainText(errors.decode(errors='replace').strip() or fallback)
                elif action == 'devices':
                    self.devices.addItem('Selecione uma partição', None)
                    for device in json.loads(output):
                        self.devices.addItem(device['path']+' · '+device['uuid'], device['uuid'])
                    self.details.setPlainText('Selecione a partição e escolha Testar recuperação.'
                        if self.devices.count() > 1 else
                        'Nenhuma partição ext4 desmontada está disponível. Confira os discos na manutenção.')
                elif action == 'inspect':
                    self.show_plan(json.loads(output))
                elif action == 'reinstall-plan':
                    self.show_reinstall(json.loads(output))
                elif action == 'points':
                    self.choose_points(json.loads(output))
                elif action == 'compare':
                    self.show_comparison(json.loads(output))
                else:
                    self.details.setPlainText(output.decode(errors='replace').strip()[-2000:] +
                        '\n\nReinicie pelo disco e confira a sessão, o funcionamento dos serviços e a versão.')
            except (KeyError, TypeError, ValueError):
                self.plan = None
                self.details.setPlainText('O plano de recuperação não pôde ser lido.')
            self.controls()

        process.readyReadStandardOutput.connect(read)
        process.readyReadStandardError.connect(read)
        process.finished.connect(finish)
        process.errorOccurred.connect(lambda error: finish(1)
            if error == QProcess.ProcessError.FailedToStart else None)
        self.controls()
        argv = ['/usr/bin/python3', BACKEND, action, *args]
        if action != 'devices':
            argv.insert(0, '/usr/bin/pkexec')
        process.start(argv[0], argv[1:])

    def show_plan(self, reply):
        plan = reply['plan']
        estimate = reply.get('estimate')
        capacity = 'Estimativa de cópia indisponível.'
        if estimate:
            size = estimate['bytes_to_copy'] / (1024 ** 2)
            free = estimate['bytes_free'] / (1024 ** 2)
            capacity = f'Estimativa de cópia: {size:,.1f} MiB. Espaço livre: {free:,.1f} MiB.'
            if size > free:
                capacity += '\nRevise o espaço antes de restaurar. A estimativa considera os dados dos arquivos alterados.'
        self.details.setPlainText(
            f"Destino: {plan['target']['path']} ({plan['target']['uuid']})\n"
            f"Origem: {plan['backup']['path']} ({plan['backup']['uuid']})\n"
            f"Ponto: {plan['point']}\nVersão do ponto: {plan['version']}\n"
            f"Revisão que ficará suspensa: {plan['revision']}\n"
            f"Pacotes críticos registrados: {', '.join(plan['packages']) or 'nenhum'}\n\n"
            "Ponto conferido em modo somente leitura.\n" + capacity + "\n\n"
            "A restauração exclui /home e /root. O Timeshift aplicará o ponto ao sistema e "
            "preservará a instalação existente do GRUB. Reinicie pelo disco depois da conferência.")
        self.plan = reply

    def reject(self):
        if self.process is None:
            super().reject()

    def closeEvent(self, event):
        if self.process is not None:
            event.ignore()
        else:
            super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = UpdateRecovery()
    dialog.show()
    sys.exit(app.exec())
