"""Physical disk overview and operation selection; geometry comes from UDisks."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea


def disk_groups(rows):
    """Keep mapped volumes with their parent; expose unknown topology separately."""
    disks = [(i, r) for i, r in enumerate(rows) if r.get('is_disk') and not r.get('parent')]
    disks.sort(key=lambda pair: (not (pair[1]['key'] == 'system' or any(
        v['key'] == 'system' and v.get('parent') == pair[1].get('path') for v in rows)), pair[1].get('device', '')))
    groups = []
    used = set()
    for index, disk in disks:
        children = [(i, r) for i, r in enumerate(rows) if r.get('parent') and r['parent'] == disk.get('path')]
        children.sort(key=lambda pair: (pair[1].get('offset', 0), pair[1].get('partition_number', 0)))
        volumes = children or [(index, disk)]
        groups.append((index, disk, volumes))
        used.add(index); used.update(i for i, _ in volumes)
    other = [(i, r) for i, r in enumerate(rows) if i not in used and not r.get('url')]
    return groups, other


def size_text(size):
    return f'{size / 1024**3:.1f} GiB' if size else 'Capacidade indisponível'


class DiskMap(QScrollArea):
    selected = pyqtSignal(int)
    context_requested = pyqtSignal(int, object)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setMinimumHeight(180)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.buttons = {}

    def populate(self, rows, letters):
        body = QWidget(); layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 8, 0, 0); layout.setSpacing(12)
        self.buttons = {}
        groups, other = disk_groups(rows)
        for number, (index, disk, volumes) in enumerate(groups):
            label = f"Disco {number}\n{disk.get('device', '')}\n{size_text(disk['size'])}"
            if disk.get('table_type'): label += '\n' + disk['table_type'].upper()
            self.add_group(layout, label, volumes, letters)
            if disk.get('partition_disk', {}).get('reason'):
                reason = QLabel(disk['partition_disk']['reason']); reason.setWordWrap(True); layout.addWidget(reason)
        if other:
            self.add_group(layout, 'Outros volumes\nDisco físico não\nidentificado', other, letters)
        network = [(i, r) for i, r in enumerate(rows) if r.get('url')]
        if network: self.add_group(layout, 'Unidades de rede', network, letters)
        if not groups and not other and not network: layout.addWidget(QLabel('Nenhum dispositivo disponível.'))
        legend = QLabel('■ Volume   ·   Sistema e volumes protegidos são identificados nos blocos.\n'
                        'Larguras aproximadas; volumes pequenos têm largura mínima para leitura. '
                        'Preto: espaço não alocado utilizável (alinhado a MiB, com margens reservadas à tabela).')
        legend.setWordWrap(True); layout.addWidget(legend); layout.addStretch()
        old = self.takeWidget()
        self.setWidget(body)
        if old: old.deleteLater()

    def add_group(self, layout, label, volumes, letters):
        row = QHBoxLayout(); row.setSpacing(6)
        heading = QLabel(label); heading.setFixedWidth(150); heading.setWordWrap(True)
        row.addWidget(heading)
        total = sum(v.get('size', 0) for _, v in volumes) or 1
        for index, volume in volumes:
            letter = 'C' if volume['key'] == 'system' else letters.get(volume['key'], '')
            name = volume['name'] + (f' ({letter}:)' if letter else '')
            state = 'Disponível' if volume.get('unallocated') else 'Sistema' if volume['key'] == 'system' else 'Protegido' if volume.get('protected') else 'Montado' if volume.get('mounts') else 'Rede' if volume.get('url') else 'Não montado'
            text = f"{name}\n{size_text(volume['size'])} · {volume.get('fs') or '—'}\n{state}"
            button = QPushButton(text); button.setCheckable(True)
            button.setMinimumSize(150, 104)
            button.setAccessibleName(text.replace('\n', ', '))
            button.setToolTip(text + '\n' + volume.get('device', volume.get('url', '')))
            button.setStyleSheet('QPushButton {text-align: left; padding: 8px; border: 1px solid palette(mid); border-top: 5px solid palette(highlight); border-radius: 0; background: palette(base); color: palette(text);} QPushButton:checked {background: palette(highlight); color: palette(highlighted-text);} QPushButton:focus {border-bottom: 3px solid palette(highlight);}')
            if volume.get('unallocated'):
                button.setStyleSheet(button.styleSheet() + 'QPushButton {border-top-color: #303030;}')
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, i=index, b=button: self.context_requested.emit(i, b.mapToGlobal(pos)))
            button.clicked.connect(lambda checked=False, i=index: self.selected.emit(i))
            self.buttons[index] = button
            row.addWidget(button, max(1, round(volume.get('size', 0) / total * 100)))
        layout.addLayout(row)

    def select(self, index):
        for i, button in self.buttons.items(): button.setChecked(i == index)
