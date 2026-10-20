"""Shared read-only volume properties and usage widgets."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QProgressBar, QDialogButtonBox


def size(value):
    return f'{value / 1024**3:.1f} GiB' if value >= 1024**3 else f'{value / 1024**2:.1f} MiB'


def usage_widget(row):
    usage = row.get('usage')
    if not usage:
        return QLabel('Não disponível na rede' if row.get('url') else 'Monte para consultar' if not row.get('mounts') else 'Não foi possível consultar')
    bar = QProgressBar()
    bar.setRange(0, 1000)
    bar.setValue(round(1000 * usage['used'] / usage['total']))
    bar.setFormat(f"{size(usage['free'])} livres de {size(usage['total'])}")
    bar.setToolTip(f"Usado: {size(usage['used'])}\nLivre para o usuário: {size(usage['free'])}\nReservado pelo filesystem: {size(usage['reserved'])}")
    bar.setAccessibleName('Espaço da unidade')
    bar.setMinimumWidth(240)
    return bar


class Properties(QDialog):
    def __init__(self, row, letter, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Propriedades da unidade')
        self.resize(540, 440)
        body = QVBoxLayout(self); body.setContentsMargins(24,24,24,20); body.setSpacing(16)
        title = QLabel(f"{row['name']} ({letter}:)" if letter else row['name'])
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setStyleSheet('font-size:22px; font-weight:600'); body.addWidget(title)
        body.addWidget(usage_widget(row))
        form = QFormLayout(); form.setSpacing(12); body.addLayout(form)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        rows = [('Tipo', row['kind']), ('Sistema de arquivos', row.get('fs') or 'Não informado'),
                ('Dispositivo', row.get('device') or '—'), ('Identificador', row.get('key') or '—'),
                ('Local', row.get('url') or ', '.join(row.get('mounts', [])) or 'Não montado')]
        if row.get('size'): rows.append(('Capacidade do volume', size(row['size'])))
        usage = row.get('usage')
        if usage:
            rows += [('Capacidade do filesystem', size(usage['total'])), ('Usado', size(usage['used'])),
                     ('Livre para o usuário', size(usage['free'])), ('Reservado pelo filesystem', size(usage['reserved']))]
        for name, value in rows:
            label = QLabel(value); label.setTextFormat(Qt.TextFormat.PlainText); label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(name, label)
        note = QLabel('Dados da última consulta. Esta janela não monta, formata ou altera unidades.')
        note.setWordWrap(True); body.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); body.addWidget(buttons)
