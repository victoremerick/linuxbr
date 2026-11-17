"""Display disk health and the changes between recorded observations."""

from PyQt6.QtCore import QDateTime, QLocale, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHeaderView, QLabel,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)

from health import COUNT_LABELS, HISTORY_DAYS, MAX_SAMPLES

METRICS = {
    'ATA': ['bad_sectors', 'attributes_failing', 'attributes_failed_before'],
    'NVMe': ['media_errors', 'error_log_entries', 'unsafe_shutdowns', 'percent_used'],
}


class HealthDialog(QDialog):
    def __init__(self, drives, parent=None):
        super().__init__(parent)
        self.drives = drives
        self.setWindowTitle('Saúde dos discos — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('drive-harddisk'))
        self.resize(900, 520)
        body = QVBoxLayout(self)
        body.setContentsMargins(24, 24, 24, 20)
        title = QLabel('Histórico de saúde dos discos')
        title.setStyleSheet('font-size: 23px; font-weight: 600')
        body.addWidget(title)

        self.drives_box = QComboBox(self)
        self.drives_box.setAccessibleName('Disco para consultar')
        for drive in drives:
            location = drive['node'] or ('Conectado' if drive['connected'] else 'Desconectado')
            self.drives_box.addItem(f"{drive['name']} · {drive['protocol']} · {location}")
        body.addWidget(self.drives_box)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        self.table = QTableWidget()
        self.table.setAccessibleName('Leituras de saúde do disco')
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        body.addWidget(self.table, 1)
        note = QLabel(f'O sistema registra até {MAX_SAMPLES} leituras por disco, por até {HISTORY_DAYS} dias. '
                      'A disponibilidade das medições depende da unidade e da conexão.')
        note.setWordWrap(True)
        body.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons)
        self.drives_box.currentIndexChanged.connect(self.select_drive)
        self.select_drive(self.drives_box.currentIndex())

    def select_drive(self, index):
        if index < 0:
            self.drives_box.hide()
            self.table.hide()
            self.status.setText('Nenhuma unidade apresentou uma interface SMART compatível ao UDisks2.')
            return
        drive = self.drives[index]
        readings = list(drive['samples'])
        current = drive['current']
        if current and current not in readings:
            readings.append(current)
        readings.sort(key=lambda row: row['read_at'], reverse=True)
        summary = []
        if not drive['connected']:
            summary.append('Disco desconectado. Veja as últimas leituras registradas.')
        elif not drive['enabled']:
            summary.append('A unidade informa SMART desativado.')
        elif current is None:
            summary.append('A unidade ainda não forneceu uma leitura SMART nesta sessão.')
        if not drive['history_available']:
            summary.append('O disco não possui identificação única para guardar o histórico.')
        summary.extend(drive['alerts'])
        if not summary:
            summary.append('Consulte abaixo os indicadores registrados pela unidade.')
        self.status.setText('\n'.join(summary))

        keys = METRICS.get(drive['protocol'], [])
        headings = ['Data e hora', 'Temperatura (°C)']
        headings += [COUNT_LABELS[key] if key in COUNT_LABELS else 'Vida útil usada (%)' for key in keys]
        self.table.clear()
        self.table.setColumnCount(len(headings))
        self.table.setHorizontalHeaderLabels(headings)
        self.table.setRowCount(len(readings))
        locale = QLocale.system()
        for row, reading in enumerate(readings):
            time = QDateTime.fromSecsSinceEpoch(reading['read_at'])
            values = [locale.toString(time, 'dd/MM/yyyy HH:mm')]
            for key in ['temperature', *keys]:
                value = reading.get(key)
                values.append('—' if value is None else locale.toString(value) if key == 'temperature' else str(value))
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
