"""Embedded screen timeout, suspend, lid and power button controls."""
from datetime import datetime
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox,
                             QCheckBox, QSpinBox, QPushButton, QDialog, QDialogButtonBox,
                             QHeaderView, QTableWidget, QTableWidgetItem)
import power_backend

ACTION_OPTIONS = [('Não fazer nada', 0), ('Suspender', 1), ('Hibernar', 2),
                  ('Desligar', 8), ('Mostrar opções de desligamento', 16),
                  ('Bloquear a sessão', 32), ('Apagar a tela', 64)]


class BatteryReport(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Relatório de bateria')
        self.resize(650, 410)
        body = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setTextFormat(Qt.TextFormat.PlainText)
        self.note.setWordWrap(True)
        body.addWidget(self.note)
        self.batteries = QComboBox()
        self.batteries.setAccessibleName('Bateria')
        self.batteries.currentIndexChanged.connect(self.show_reading)
        selector = QFormLayout()
        selector.addRow('&Bateria', self.batteries)
        body.addLayout(selector)
        self.table = QTableWidget(0, 2)
        self.table.setAccessibleName('Medições da bateria selecionada')
        self.table.setHorizontalHeaderLabels(['Medição', 'Valor'])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('Fechar')
        buttons.rejected.connect(self.reject)
        self.save_button = buttons.addButton('Registrar leitura inicial', QDialogButtonBox.ButtonRole.ActionRole)
        self.save_button.clicked.connect(lambda: self.refresh(save=True))
        buttons.addButton('Atualizar', QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.refresh)
        body.addWidget(buttons)
        self.refresh()

    def refresh(self, *, save=False):
        readings = power_backend.battery_report()
        previous = self.batteries.currentIndex()
        self.batteries.blockSignals(True)
        self.batteries.clear()
        storage = QSettings('Linux BR', 'Relatorio de bateria')
        saved = False
        pending = False
        for row in readings:
            health = row['health']
            delta = 'Disponível após registrar uma leitura'
            if row['identity'] and health is not None:
                key = f'{row["identity"]}/primeira-leitura'
                first = storage.value(key, defaultValue=None)
                if first:
                    try:
                        observed, day = first
                        delta = f'{health - float(observed):+.1f} p.p. desde {day}'.replace('.', ',', 1)
                    except (TypeError, ValueError):
                        first = None
                if save and not first:
                    storage.setValue(key, [str(health), datetime.now().strftime('%d/%m/%Y')])
                    saved = True
                    delta = 'Primeira leitura registrada'
                elif not first:
                    pending = True
            else:
                delta = 'Identificação ou capacidade indisponível'
            def capacity(value):
                return f'{value:.2f} {row["unit"]}'.replace('.', ',') if value is not None else 'Indisponível'
            self.batteries.addItem(row['name'], [
                ('Capacidade de fábrica', capacity(row['design'])),
                ('Capacidade máxima atual', capacity(row['full'])),
                ('Saúde estimada', f'{health:.1f}%'.replace('.', ',') if health is not None else 'Indisponível'),
                ('Ciclos', str(row['cycles']) if row['cycles'] is not None else 'Indisponível'),
                ('Variação de saúde', delta),
            ])
        self.batteries.setCurrentIndex(min(max(previous, 0), len(readings) - 1))
        self.batteries.blockSignals(False)
        self.show_reading()
        if saved:
            storage.sync()
        self.save_button.setEnabled(pending or storage.status() != QSettings.Status.NoError)
        if not readings:
            self.note.setText('Nenhuma bateria interna foi encontrada.')
        elif saved and storage.status() != QSettings.Status.NoError:
            self.note.setText('Não foi possível gravar a leitura nesta conta.')
        else:
            self.note.setText('O relatório usa os dados informados pela bateria. Registre a primeira leitura para acompanhar a variação nesta conta.')

    def show_reading(self):
        rows = self.batteries.currentData() or []
        self.table.setVisible(bool(rows))
        self.batteries.setEnabled(bool(rows))
        self.table.setRowCount(len(rows))
        for index, (label, value) in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(label))
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            self.table.setItem(index, 1, item)


class Power(QWidget):
    def __init__(self):
        super().__init__()
        body = QVBoxLayout(self)
        body.setContentsMargins(32, 28, 32, 28)
        body.setSpacing(14)
        title = QLabel('Energia e bateria')
        title.setStyleSheet('font-size:26px;font-weight:600')
        body.addWidget(title)
        description = QLabel('Configure o comportamento na tomada, na bateria e com bateria fraca. Alterações de cada perfil são salvas separadamente.')
        description.setWordWrap(True)
        body.addWidget(description)
        form = QFormLayout()
        self.profile = QComboBox()
        for label, value in [('Na tomada', 'AC'), ('Na bateria', 'Battery'),
                             ('Bateria fraca', 'LowBattery')]:
            self.profile.addItem(label, value)
        self.profile.currentIndexChanged.connect(self.load)
        form.addRow('Perfil', self.profile)
        self.screen_enabled = QCheckBox('Apagar a tela quando ociosa')
        form.addRow('', self.screen_enabled)
        self.screen = QSpinBox()
        self.screen.setRange(1, 1440)
        self.screen.setSuffix(' minutos')
        form.addRow('Apagar após', self.screen)
        self.screen_enabled.toggled.connect(self.screen.setEnabled)
        self.suspend = QSpinBox()
        self.suspend.setRange(1, 1440)
        self.suspend.setSuffix(' minutos')
        form.addRow('Suspender após', self.suspend)
        self.suspend_action = self.action_combo()
        form.addRow('Quando ocioso', self.suspend_action)
        self.lid = self.action_combo()
        form.addRow('Ao fechar a tampa', self.lid)
        self.power = self.action_combo()
        form.addRow('Ao pressionar o botão de energia', self.power)
        body.addLayout(form)
        save = QPushButton('Aplicar neste perfil')
        save.setProperty('primary', True)
        save.clicked.connect(self.save)
        body.addWidget(save)
        report = QPushButton('Relatório de bateria…')
        report.clicked.connect(lambda: BatteryReport(self).exec())
        body.addWidget(report)
        self.status = QLabel()
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        body.addStretch()
        self.load()

    @staticmethod
    def action_combo():
        combo = QComboBox()
        for label, value in ACTION_OPTIONS:
            combo.addItem(label, value)
        return combo

    def load(self):
        try:
            values = power_backend.profile(self.profile.currentData())
            self.screen_enabled.setChecked(values['screen_enabled'])
            self.screen.setValue(max(1, round(values['screen']/60)))
            self.suspend.setValue(max(1, round(values['suspend']/60)))
            for field in ('suspend_action', 'lid', 'power'):
                combo = getattr(self, field)
                index = combo.findData(values[field])
                if index < 0:
                    combo.addItem('Ação atual (' + str(values[field]) + ')', values[field])
                    index = combo.count()-1
                combo.setCurrentIndex(index)
            self.loaded = self.values()
            self.status.setText('Configurações carregadas.')
        except (OSError, ValueError) as error:
            self.status.setText('Não foi possível ler as opções de energia: ' + str(error))

    def save(self):
        values = self.values()
        try:
            power_backend.write(self.profile.currentData(), values, getattr(self, 'loaded', None))
            self.loaded = values.copy()
            self.status.setText('Configurações de energia aplicadas.')
        except (OSError, ValueError) as error:
            self.status.setText('Não foi possível aplicar: ' + str(error))

    def values(self):
        return {'screen_enabled': self.screen_enabled.isChecked(),
                'screen': self.screen.value()*60, 'suspend': self.suspend.value()*60,
                'suspend_action': self.suspend_action.currentData(),
                'lid': self.lid.currentData(), 'power': self.power.currentData()}
