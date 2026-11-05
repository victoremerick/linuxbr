"""Read-only system properties; values always come from the running system."""
import os
import platform
import json
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, QPushButton, QScrollArea, QFrame, QToolButton, QGridLayout, QDialog, QDialogButtonBox, QTextBrowser, QFileDialog, QMessageBox


RELEASE_INFO = Path('/usr/share/linuxbr/release-info.json')
RELEASE_NOTES = Path('/usr/share/doc/linuxbr-system/README.md')


def release_summary(path=None):
    try:
        value = json.loads((path or RELEASE_INFO).read_text(encoding='utf-8'))
        if isinstance(value, dict):
            version = value.get('display_version') or value.get('version')
            if isinstance(version, str) and len(version) < 200:
                return version, value.get('channel', '')
    except (OSError, ValueError):
        pass
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    return release.get('VERSION', release.get('VERSION_ID', 'Versão indisponível')), ''


class ReleaseNotes(QDialog):
    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        self.setWindowTitle('Notas de lançamento — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('view-history'))
        self.resize(880, 620)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setAccessibleName('Histórico das versões do Linux BR')
        self.browser.anchorClicked.connect(self.follow_link)
        try:
            content = (path or RELEASE_NOTES).read_text(encoding='utf-8')
        except OSError:
            content = '# Notas de lançamento indisponíveis\n\nReinstale o pacote linuxbr-system para recuperar a documentação desta versão.'
        self.browser.setMarkdown(content)
        layout.addWidget(self.browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('Fechar')
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def follow_link(self, url):
        if not url.scheme() and not url.path() and url.fragment():
            self.browser.scrollToAnchor(url.fragment())
        elif url.scheme() == 'https' and url.host() and not url.userInfo():
            QDesktopServices.openUrl(url)


def export_diagnostic(parent):
    from welcome import support_report
    filename, _ = QFileDialog.getSaveFileName(parent, 'Salvar diagnóstico',
                                             str(Path.home() / 'linuxbr-diagnostico.txt'), 'Texto (*.txt)')
    if not filename:
        return
    try:
        Path(filename).write_text(support_report(), encoding='utf-8')
    except OSError as error:
        QMessageBox.warning(parent, 'Não foi possível salvar', str(error))
    else:
        QMessageBox.information(parent, 'Diagnóstico salvo',
                                'O arquivo foi salvo no local escolhido. Revise-o antes de compartilhar com o suporte.')


def system_details():
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    cpu = platform.machine()
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            key, _, value = line.partition(':')
            if key.strip() in ('model name', 'Hardware') and value.strip():
                cpu = value.strip()
                break
    except OSError:
        pass
    memory = 'Indisponível'
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                memory = f'{int(line.split()[1]) / 1024**2:.1f} GiB utilizáveis'
    except (OSError, ValueError, IndexError):
        pass
    return [
        ('Especificações do dispositivo', [
            ('Nome do dispositivo', platform.node()), ('Processador', cpu),
            ('Memória RAM', memory), ('Arquitetura', platform.machine())]),
        ('Especificações do sistema', [
            ('Edição', release.get('PRETTY_NAME', 'Indisponível')),
            ('Versão', release.get('VERSION', release.get('VERSION_ID', 'Indisponível'))),
            ('Kernel', platform.release()),
            ('Ambiente de trabalho', os.environ.get('XDG_CURRENT_DESKTOP', 'Indisponível')),
            ('Sessão gráfica', os.environ.get('XDG_SESSION_TYPE', 'Indisponível'))])]


class About(QScrollArea):
    def __init__(self, launch, navigate):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(); self.setWidget(content)
        body = QVBoxLayout(content); body.setContentsMargins(32, 28, 32, 28); body.setSpacing(24)
        header = QHBoxLayout()
        heading = QLabel('Sistema'); heading.setStyleSheet('font-size:26px; font-weight:600')
        header.addWidget(heading); header.addStretch()
        copy = QPushButton('Copiar especificações')
        copy.setIcon(QIcon.fromTheme('edit-copy')); copy.clicked.connect(self.copy_details)
        header.addWidget(copy); body.addLayout(header)
        brand = QHBoxLayout(); brand.setSpacing(16)
        logo = QLabel(); logo.setAccessibleName('Logo Linux BR')
        logo.setPixmap(QIcon('/usr/share/linuxbr/identity/symbol-color.svg').pixmap(56, 56))
        brand.addWidget(logo)
        version, channel = release_summary()
        title = QLabel('Linux BR\n' + version); title.setStyleSheet('font-size:24px; font-weight:600')
        title.setTextFormat(Qt.TextFormat.PlainText)
        brand.addWidget(title); brand.addStretch(); body.addLayout(brand)
        if channel in ('alpha', 'beta', 'rc'):
            warning = QLabel('Versão em desenvolvimento. Alguns recursos ainda precisam de homologação. Consulte as notas de lançamento e as limitações conhecidas.')
            warning.setWordWrap(True); body.addWidget(warning)
        release_actions = QHBoxLayout()
        self.notes_button = QPushButton('Notas de lançamento')
        self.notes_button.setIcon(QIcon.fromTheme('view-history'))
        self.notes_button.clicked.connect(self.show_release_notes)
        self.diagnostic_button = QPushButton('Salvar diagnóstico…')
        self.diagnostic_button.setIcon(QIcon.fromTheme('document-save'))
        self.diagnostic_button.clicked.connect(lambda: export_diagnostic(self))
        release_actions.addWidget(self.notes_button); release_actions.addWidget(self.diagnostic_button)
        release_actions.addStretch(); body.addLayout(release_actions)
        self.details = system_details()
        label_width = max(self.fontMetrics().horizontalAdvance(key) for _, rows in self.details for key, _ in rows) + 8
        for caption, rows in self.details:
            section = QWidget(); section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0); section_layout.setSpacing(12)
            label = QLabel(caption); label.setStyleSheet('font-size:15px; font-weight:600')
            section_layout.addWidget(label)
            form = QFormLayout(); form.setHorizontalSpacing(28); form.setVerticalSpacing(10)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            for key, value in rows:
                label = QLabel(value); label.setTextFormat(Qt.TextFormat.PlainText)
                label.setWordWrap(True); label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                key_label = QLabel(key); key_label.setMinimumWidth(label_width)
                form.addRow(key_label, label)
            section_layout.addLayout(form); body.addWidget(section)
        divider = QFrame(); divider.setFrameShape(QFrame.Shape.HLine); body.addWidget(divider)
        heading = QLabel('Configurações relacionadas'); heading.setStyleSheet('font-weight:600')
        body.addWidget(heading)
        links = QGridLayout(); links.setHorizontalSpacing(24); links.setVerticalSpacing(8); links.setColumnStretch(2,1)
        for index, (caption, icon, target) in enumerate([
                ('Dispositivos e drivers', 'computer', 'Dispositivos'),
                ('Discos e unidades', 'drive-harddisk', 'Armazenamento'),
                ('Atualizações', 'system-software-update', 'Administração'),
                ('Informações avançadas', 'dialog-information', None)]):
            button = QToolButton(); button.setText(caption); button.setIcon(QIcon.fromTheme(icon))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); button.setAutoRaise(True)
            if target:
                button.clicked.connect(lambda checked=False, target=target: navigate(target))
            else:
                button.clicked.connect(lambda: launch(['kinfocenter']))
            links.addWidget(button, index // 2, index % 2, Qt.AlignmentFlag.AlignLeft)
        body.addLayout(links); body.addStretch()

    def show_release_notes(self):
        ReleaseNotes(self).exec()

    def copy_details(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText('\n\n'.join(title + '\n' + '\n'.join(f'{key}: {value}' for key, value in rows) for title, rows in self.details))
