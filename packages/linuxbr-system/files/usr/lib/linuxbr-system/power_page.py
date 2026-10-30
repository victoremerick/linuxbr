"""Embedded screen timeout, suspend, lid and power button controls."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox,
                             QCheckBox, QSpinBox, QPushButton)
import power_backend

ACTION_OPTIONS = [('Não fazer nada', 0), ('Suspender', 1), ('Hibernar', 2),
                  ('Desligar', 8), ('Mostrar opções de desligamento', 16),
                  ('Bloquear a sessão', 32), ('Apagar a tela', 64)]


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
