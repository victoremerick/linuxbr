// SPDX-License-Identifier: GPL-3.0-or-later
#include "Preflight.h"

#include <QComboBox>
#include <QFormLayout>
#include <QFrame>
#include <QHeaderView>
#include <QIcon>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QLocale>
#include <QPainter>
#include <QProcess>
#include <QPushButton>
#include <QTableWidget>
#include <QTabWidget>
#include <QTimer>
#include <QVBoxLayout>

namespace
{
const QString Helper = QStringLiteral("/usr/lib/linuxbr-installer/preflight.py");

QString bytes(qint64 size)
{
    return QLocale().formattedDataSize(size, 1);
}

QString protection(const QString& status)
{
    if (status == "bitlocker")
        return QStringLiteral("BitLocker. Use o Windows e confirme a chave de recuperação antes de migrar.");
    if (status == "luks")
        return QStringLiteral("LUKS. Confirme a chave do volume antes de migrar ou redimensionar.");
    if (status == "hibernated")
        return QStringLiteral("Windows hibernado. Retome e desligue o Windows por completo antes de alterar o volume.");
    if (status == "unknown")
        return QStringLiteral("NTFS. A hibernação não pôde ser verificada.");
    if (status == "inactive")
        return QStringLiteral("NTFS. Cabeçalho de hibernação inativo.");
    return {};
}

QComboBox* checkResult(QWidget* parent)
{
    auto* result = new QComboBox(parent);
    result->addItems({QStringLiteral("Não testado"), QStringLiteral("Funcionou"), QStringLiteral("Falhou")});
    return result;
}

QJsonValue selectedResult(const QComboBox* result)
{
    const auto index = result->currentIndex();
    return index == 0 ? QJsonValue(QJsonValue::Null) : QJsonValue(index == 1);
}

QLabel* plainLabel(const QString& text, QWidget* parent)
{
    auto* label = new QLabel(text, parent);
    label->setTextFormat(Qt::PlainText);
    label->setWordWrap(true);
    return label;
}
}

class VolumeMap final : public QWidget
{
public:
    using QWidget::QWidget;

    void setDisk(const QJsonObject& value)
    {
        disk = value;
        update();
    }

protected:
    void paintEvent(QPaintEvent*) override
    {
        const auto size = disk.value("size").toInteger();
        if (size < 1)
            return;
        QPainter painter(this);
        painter.fillRect(rect(), palette().alternateBase());
        const auto parts = disk.value("volumes").toArray();
        if (parts.isEmpty() && !disk.value("filesystem").toString().isEmpty())
            painter.fillRect(rect(), palette().highlight());
        for (const auto& value : parts)
        {
            const auto part = value.toObject();
            const auto start = part.value("start").toInteger();
            const auto end = start + part.value("size").toInteger();
            const auto left = qBound(0, qRound(width() * (double(start) / size)), width());
            const auto right = qBound(left, qRound(width() * (double(end) / size)), width());
            const auto status = part.value("protection").toString();
            const auto color = (status == "bitlocker" || status == "luks" || status == "hibernated")
                ? QColor("#a15b19") : palette().highlight().color();
            painter.fillRect(QRect(left, 0, right - left, height()), color);
            if (right - left > 1)
            {
                painter.setPen(palette().mid().color());
                painter.drawLine(right - 1, 0, right - 1, height());
            }
        }
        painter.setPen(palette().mid().color());
        painter.drawRect(rect().adjusted(0, 0, -1, -1));
    }

private:
    QJsonObject disk;
};

PreflightPage::PreflightPage(std::function<void()> callback, QWidget* parent)
    : QWidget(parent)
    , finished(std::move(callback))
{
    auto* layout = new QVBoxLayout(this);
    auto* title = plainLabel(QStringLiteral("Verificar o computador"), this);
    auto font = title->font();
    font.setPointSize(font.pointSize() + 5);
    font.setBold(true);
    title->setFont(font);
    layout->addWidget(title);
    notice = plainLabel(QStringLiteral("Consultando armazenamento e firmware…"), this);
    layout->addWidget(notice);

    auto* tabs = new QTabWidget(this);
    tabs->addTab(storagePage(), QIcon::fromTheme("drive-harddisk"), QStringLiteral("Armazenamento"));
    tabs->addTab(firmwarePage(), QIcon::fromTheme("preferences-system"), QStringLiteral("Firmware"));
    tabs->addTab(peripheralsPage(), QIcon::fromTheme("input-touchpad"), QStringLiteral("Periféricos"));
    layout->addWidget(tabs, 1);
    layout->addWidget(plainLabel(
        QStringLiteral("Escolha o disco na próxima etapa. O resumo mostrará o mapa atual, o resultado previsto e as operações antes da confirmação."),
        this));
}

QWidget* PreflightPage::storagePage()
{
    auto* page = new QWidget(this);
    auto* layout = new QVBoxLayout(page);
    diskSelector = new QComboBox(page);
    diskSelector->setAccessibleName(QStringLiteral("Disco para consultar"));
    diskSelector->setSizeAdjustPolicy(QComboBox::AdjustToMinimumContentsLengthWithIcon);
    layout->addWidget(diskSelector);

    map = new VolumeMap(page);
    map->setMinimumHeight(18);
    map->setAccessibleName(QStringLiteral("Mapa proporcional do disco selecionado"));
    layout->addWidget(map);
    layout->addWidget(plainLabel(
        QStringLiteral("O mapa mostra o espaço reservado a volumes, os volumes protegidos em laranja e as áreas fora dos volumes."), page));

    volumes = new QTableWidget(page);
    volumes->setColumnCount(4);
    volumes->setHorizontalHeaderLabels({QStringLiteral("Dispositivo"), QStringLiteral("Formato"),
                                        QStringLiteral("Capacidade"), QStringLiteral("Estado")});
    volumes->setEditTriggers(QAbstractItemView::NoEditTriggers);
    volumes->setSelectionBehavior(QAbstractItemView::SelectRows);
    volumes->verticalHeader()->hide();
    volumes->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    volumes->horizontalHeader()->setStretchLastSection(true);
    layout->addWidget(volumes, 1);
    connect(diskSelector, &QComboBox::currentIndexChanged, this, &PreflightPage::showDisk);
    return page;
}

QWidget* PreflightPage::firmwarePage()
{
    auto* page = new QWidget(this);
    auto* layout = new QVBoxLayout(page);
    firmwareInfo = plainLabel(QStringLiteral("Consultando o modo de inicialização…"), page);
    firmwareInfo->setTextInteractionFlags(Qt::TextSelectableByMouse | Qt::TextSelectableByKeyboard);
    layout->addWidget(firmwareInfo);
    layout->addStretch();
    return page;
}

QWidget* PreflightPage::peripheralsPage()
{
    auto* page = new QWidget(this);
    auto* layout = new QVBoxLayout(page);
    auto* form = new QFormLayout;
    form->setFieldGrowthPolicy(QFormLayout::ExpandingFieldsGrow);

    auto* keyTest = new QLineEdit(page);
    keyTest->setAccessibleName(QStringLiteral("Campo de teste do teclado"));
    keyTest->setPlaceholderText(QStringLiteral("Digite alguns caracteres neste campo"));
    form->addRow(QStringLiteral("Teclado"), keyTest);
    keyboard = checkResult(page);
    form->addRow(QStringLiteral("Resultado do teclado"), keyboard);

    auto* touchTest = new QPushButton(QIcon::fromTheme("input-touchpad"),
        QStringLiteral("Use o touchpad para clicar aqui"), page);
    connect(touchTest, &QPushButton::clicked, touchTest, [touchTest] {
        touchTest->setText(QStringLiteral("Clique recebido"));
    });
    form->addRow(QStringLiteral("Touchpad"), touchTest);
    touchpad = checkResult(page);
    form->addRow(QStringLiteral("Resultado do touchpad"), touchpad);

    auto* tone = new QPushButton(QIcon::fromTheme("audio-volume-high"), QStringLiteral("Ouvir som de teste"), page);
    auto* toneStatus = plainLabel({}, page);
    connect(tone, &QPushButton::clicked, page, [page, tone, toneStatus] {
        auto* sound = new QProcess(page);
        tone->setEnabled(false);
        toneStatus->setText(QStringLiteral("Enviando som à saída ativa…"));
        const auto done = [tone, toneStatus, sound](bool success) {
            toneStatus->setText(success ? QStringLiteral("Indique abaixo se ouviu o som.")
                                        : QStringLiteral("Não foi possível reproduzir o som de teste."));
            tone->setEnabled(true);
            sound->deleteLater();
        };
        QObject::connect(sound, &QProcess::finished, tone, [done](int code, QProcess::ExitStatus status) {
            done(code == 0 && status == QProcess::NormalExit);
        });
        QObject::connect(sound, &QProcess::errorOccurred, tone, [done](QProcess::ProcessError error) {
            if (error == QProcess::FailedToStart)
                done(false);
        });
        sound->start(QStringLiteral("/usr/bin/python3"), {Helper, QStringLiteral("tone")});
    });
    form->addRow(QStringLiteral("Áudio"), tone);
    form->addRow(QString{}, toneStatus);
    audio = checkResult(page);
    form->addRow(QStringLiteral("Resultado do áudio"), audio);

    auto* pattern = new QWidget(page);
    pattern->setAccessibleName(QStringLiteral("Faixas de teste nas cores vermelha, verde, azul e branca"));
    auto* colors = new QHBoxLayout(pattern);
    colors->setContentsMargins(0, 0, 0, 0);
    colors->setSpacing(0);
    for (const auto* color : {"#d7263d", "#239754", "#2474d2", "#f5f5f5"})
    {
        auto* band = new QFrame(pattern);
        band->setMinimumHeight(24);
        band->setStyleSheet(QStringLiteral("background: %1").arg(color));
        colors->addWidget(band, 1);
    }
    form->addRow(QStringLiteral("Vídeo"), pattern);
    video = checkResult(page);
    form->addRow(QStringLiteral("As quatro faixas aparecem?"), video);
    layout->addLayout(form);
    layout->addStretch();
    return page;
}

QJsonObject PreflightPage::liveChecks() const
{
    return {{"schema", 1}, {"keyboard", selectedResult(keyboard)}, {"touchpad", selectedResult(touchpad)},
            {"audio", selectedResult(audio)}, {"video", selectedResult(video)}};
}

void PreflightPage::scan()
{
    if (started)
        return;
    started = true;
    auto* process = new QProcess(this);
    const auto complete = [this, process](const QJsonObject& report) {
        showReport(report);
        loaded = true;
        finished();
        process->deleteLater();
    };
    connect(process, &QProcess::finished, this, [complete, process](int code, QProcess::ExitStatus status) {
        const auto report = code == 0 && status == QProcess::NormalExit
            ? QJsonDocument::fromJson(process->readAllStandardOutput()).object() : QJsonObject{};
        complete(report);
    });
    connect(process, &QProcess::errorOccurred, this, [complete](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart)
            complete({});
    });
    QTimer::singleShot(25'000, process, [process] {
        if (process->state() != QProcess::NotRunning)
            process->kill();
    });
    process->start(QStringLiteral("/usr/bin/python3"), {Helper});
}

void PreflightPage::showReport(const QJsonObject& report)
{
    disks = report.value("disks").toArray();
    if (report.value("storage_available").toBool())
        notice->setText(disks.isEmpty() ? QStringLiteral("Nenhum disco foi detectado.")
                                        : QStringLiteral("Confira a identificação, a capacidade e os avisos de cada disco."));
    else
        notice->setText(QStringLiteral("A verificação de armazenamento está indisponível. Confira o disco e as partições no resumo do Calamares."));

    QStringList warnings;
    for (const auto& value : disks)
    {
        const auto disk = value.toObject();
        const auto identity = QStringList{disk.value("vendor").toString(), disk.value("model").toString()}.join(' ').simplified();
        const auto transport = disk.value("transport").toString();
        diskSelector->addItem(QStringLiteral("%1 · %2 · %3 · %4").arg(
            disk.value("path").toString(), identity.isEmpty() ? QStringLiteral("Modelo não informado") : identity,
            bytes(disk.value("size").toInteger()), transport.isEmpty() ? QStringLiteral("Conexão não informada") : transport));

        auto entries = disk.value("volumes").toArray();
        entries.append(disk);
        for (const auto& entry : entries)
        {
            const auto volume = entry.toObject();
            const auto status = volume.value("protection").toString();
            if (status == "bitlocker" || status == "luks" || status == "hibernated")
                warnings.append(QStringLiteral("%1 — %2").arg(volume.value("path").toString(), protection(status)));
        }
    }
    if (!warnings.isEmpty())
        notice->setText(QStringLiteral("Volumes protegidos detectados (%1). %2 Consulte o estado dos demais discos na tabela.")
                            .arg(warnings.size()).arg(warnings.first()));

    const auto firmware = report.value("firmware").toObject();
    if (firmware.isEmpty())
    {
        firmwareInfo->setText(QStringLiteral("Não foi possível consultar o firmware."));
        return;
    }
    const bool uefi = firmware.value("mode").toString() == "uefi";
    QString mode = uefi ? QStringLiteral("Inicialização UEFI detectada.")
                        : QStringLiteral("Inicialização BIOS legada detectada. Em equipamento com UEFI, escolha a entrada UEFI do pendrive no menu de boot.");
    const auto secure = firmware.value("secure_boot").toString();
    QString secureBoot = !uefi ? QStringLiteral("Secure Boot depende do modo UEFI.")
        : secure == "enabled" ? QStringLiteral("Secure Boot ativado. Confira a assinatura dos componentes de inicialização ao instalar drivers adicionais.")
        : secure == "disabled" ? QStringLiteral("Secure Boot desativado. Consulte as opções de Segurança ou Inicialização do firmware se a política da máquina exigir ativação.")
        : QStringLiteral("Estado do Secure Boot indisponível. Consulte a opção no firmware.");
    const auto kvm = firmware.value("acceleration").toString();
    QString virtualization = kvm == "enabled" ? QStringLiteral("Aceleração KVM disponível.")
        : kvm == "no-kvm" ? QStringLiteral("O processador anuncia virtualização. A aceleração KVM não está disponível nesta sessão. Confira o firmware e o suporte do kernel.")
        : QStringLiteral("Virtualização não detectada. Procure Intel VT-x ou AMD SVM nas opções do processador no firmware.");
    firmwareInfo->setText(QStringList{mode, secureBoot, virtualization}.join(QStringLiteral("\n\n")));
}

void PreflightPage::showDisk(int index)
{
    if (index < 0 || index >= disks.size())
        return;
    const auto disk = disks.at(index).toObject();
    auto entries = disk.value("volumes").toArray();
    if (entries.isEmpty() && !disk.value("filesystem").toString().isEmpty())
        entries.append(disk);
    map->setDisk(disk);
    volumes->setRowCount(entries.size());
    for (qsizetype row = 0; row < entries.size(); ++row)
    {
        const auto volume = entries.at(row).toObject();
        const QStringList values{volume.value("path").toString(), volume.value("filesystem").toString(),
            bytes(volume.value("size").toInteger()), protection(volume.value("protection").toString())};
        for (int column = 0; column < values.size(); ++column)
            volumes->setItem(row, column, new QTableWidgetItem(values.at(column)));
    }
    QTimer::singleShot(0, volumes, &QTableWidget::resizeRowsToContents);
}
