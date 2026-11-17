"""Auditoria de autoridades certificadoras da confiança local do sistema."""
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from desktop_jobs import Query


TRUST = Path('/etc/ssl/certs')
ADMIN = Path('/usr/local/share/ca-certificates')
ORGANIZATION = ADMIN/'linuxbr-organizacao'
DISTRIBUTION = Path('/usr/share/ca-certificates')


def inventory(folder=TRUST, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        bundle = (folder/'ca-certificates.crt').read_bytes()
        trusted = {certificate.fingerprint(hashes.SHA256()) for certificate in x509.load_pem_x509_certificates(bundle)}
    except (OSError, ValueError):
        return []
    rows = {}
    for link in folder.glob('*.pem'):
        try:
            source = link.resolve(strict=True)
            if not source.is_file() or source.stat().st_size > 512 * 1024:
                continue
            certificates = x509.load_pem_x509_certificates(source.read_bytes())
        except (OSError, RuntimeError, ValueError):
            continue
        if source.is_relative_to(ORGANIZATION):
            origin = 'Pasta da organização'
        elif source.is_relative_to(ADMIN):
            origin = 'Administração local'
        elif source.is_relative_to(DISTRIBUTION):
            origin = 'Distribuição'
        else:
            origin = 'Confiança local do sistema'
        for certificate in certificates:
            fingerprint = certificate.fingerprint(hashes.SHA256())
            if fingerprint not in trusted:
                continue
            key = fingerprint.hex()
            active = certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
            status = 'Em vigor' if active else 'Fora da validade'
            row = dict(subject=certificate.subject.rfc4514_string(),
                       issuer=certificate.issuer.rfc4514_string(), source=str(source),
                       origin=origin, start=certificate.not_valid_before_utc.date().isoformat(),
                       end=certificate.not_valid_after_utc.date().isoformat(),
                       status=status, digest=key)
            rows[key] = max(rows.get(key, row), row, key=lambda value:
                ('Distribuição', 'Confiança local do sistema', 'Administração local',
                 'Pasta da organização').index(value['origin']))
    return sorted(rows.values(), key=lambda row: (row['origin'], row['subject'].casefold()))


class LocalCertificates(QWidget):
    def __init__(self):
        super().__init__()
        self.jobs = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        title = QLabel('Certificados locais')
        title.setStyleSheet('font-size:26px;font-weight:600')
        layout.addWidget(title)
        note = QLabel('Consulte certificados de confiança do Debian e certificados incluídos pela administração local.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.list = QTreeWidget()
        self.list.setHeaderLabels(['Assunto', 'Emissor', 'Válido desde', 'Expira em', 'Origem', 'Estado'])
        self.list.setRootIsDecorated(False)
        self.list.setSortingEnabled(True)
        self.list.setAccessibleName('Certificados de confiança')
        self.list.currentItemChanged.connect(self.select)
        layout.addWidget(self.list, 1)
        self.details = QLabel('')
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.details)
        self.refresh_button = QPushButton('Atualizar certificados')
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.status = QLabel('')
        self.status.setAccessibleName('Resultado da inspeção')
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self):
        if self.jobs:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText('Consultando o repositório do sistema…')
        job = Query(inventory, self)
        self.jobs.add(job)
        job.result.connect(self.loaded)
        job.failed.connect(lambda _: self.status.setText('Não foi possível consultar os certificados deste sistema.'))
        job.finished.connect(lambda: self.jobs.discard(job))
        job.finished.connect(lambda: self.refresh_button.setEnabled(True))
        job.finished.connect(job.deleteLater)
        job.start()

    def loaded(self, rows):
        self.list.clear()
        for row in rows:
            item = QTreeWidgetItem([row[key] for key in ('subject','issuer','start','end','origin','status')])
            item.setData(0, Qt.ItemDataRole.UserRole, row)
            self.list.addTopLevelItem(item)
        if rows:
            self.list.setCurrentItem(self.list.topLevelItem(0))
        self.status.setText(f'{len(rows)} certificados encontrados no repositório do sistema.')

    def select(self, item, _):
        row = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.details.setText(f"Arquivo\n{row['source']}\n\nImpressão digital SHA-256\n{row['digest']}" if row else '')
