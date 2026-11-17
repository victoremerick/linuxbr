// SPDX-License-Identifier: GPL-3.0-or-later

#include "Branding.h"
#include "GlobalStorage.h"
#include "JobQueue.h"
#include "Preflight.h"
#include "ViewManager.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"

#include <QCheckBox>
#include <QFrame>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QIcon>
#include <QJsonDocument>
#include <QLabel>
#include <QPlainTextEdit>
#include <QPointer>
#include <QPushButton>
#include <QStackedWidget>
#include <QVBoxLayout>

namespace
{
QLabel* heading(const QString& text, int extraPoints, QWidget* parent)
{
    auto* label = new QLabel(text, parent);
    auto font = label->font();
    font.setPointSize(font.pointSize() + extraPoints);
    font.setBold(true);
    label->setFont(font);
    label->setWordWrap(true);
    return label;
}

void prepareWindow(Calamares::ViewManager* manager)
{
    auto* central = manager->centralWidget();
    auto* window = central->window();
    auto* stack = central->findChild<QStackedWidget*>("viewManagerStack");
    if (window->objectName() != "mainApp" || !window->layout() || !stack)
        qFatal("A janela do instalador não está disponível.");

    auto* panel = new QFrame(window);
    panel->setObjectName("linuxbrInstallPanel");
    panel->setFrameShape(QFrame::StyledPanel);
    panel->setMaximumSize(1080, 704);
    panel->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    auto* panelLayout = new QVBoxLayout(panel);
    panelLayout->setContentsMargins(22, 16, 22, 16);
    panelLayout->setSpacing(10);

    auto* header = new QHBoxLayout;
    header->addWidget(heading(
        QStringLiteral("Instalar %1").arg(Calamares::Branding::instance()->productName()), 3, panel), 1);
    auto* close = new QPushButton(QIcon::fromTheme("window-close"), QStringLiteral("Fechar"), panel);
    close->setObjectName("linuxbrInstallClose");
    close->setAutoDefault(false);
    close->setToolTip(QStringLiteral("Cancelar a instalação e voltar ao ambiente Live"));
    header->addWidget(close);
    panelLayout->addLayout(header);

    auto* body = new QWidget(panel);
    body->setLayout(window->layout());
    panelLayout->addWidget(body, 1);

    auto* outer = new QGridLayout(window);
    outer->setContentsMargins(24, 24, 24, 24);
    outer->addWidget(panel, 0, 0);
    outer->setColumnStretch(0, 1);
    outer->setRowStretch(0, 1);

    window->setStyleSheet(window->styleSheet() + QStringLiteral(
        " #mainApp { background: #10191f; }"
        " #linuxbrInstallPanel { background: palette(window); border: 1px solid palette(mid); border-radius: 10px; }"));
    window->setWindowFlag(Qt::FramelessWindowHint);
    window->setWindowState(Qt::WindowFullScreen);

    // The stack changes before the installation step starts its jobs. Handle
    // this signal as well as the regular navigation updates from Calamares.
    auto syncClose = [manager, close]() {
        auto* step = manager->currentStep();
        const bool installing = step && step->inherits("Calamares::ExecutionViewStep");
        close->setEnabled(!installing && manager->quitEnabled());
        close->setToolTip(installing
            ? QStringLiteral("Aguarde a conclusão das operações de instalação")
            : QStringLiteral("Fechar o instalador"));
    };
    QObject::connect(stack, &QStackedWidget::currentChanged, close, syncClose);
    QObject::connect(manager, &Calamares::ViewManager::quitEnabledChanged, close, syncClose);
    QObject::connect(manager, &Calamares::ViewManager::currentStepChanged, close, syncClose);
    QObject::connect(close, &QPushButton::clicked, manager, &Calamares::ViewManager::quit);
    syncClose();
}
}

class PLUGINDLLEXPORT InstallationViewStep final : public Calamares::ViewStep
{
    Q_OBJECT

public:
    explicit InstallationViewStep(QObject* parent = nullptr)
        : Calamares::ViewStep(parent)
        , pages(new QStackedWidget)
    {
        prepareWindow(Calamares::ViewManager::instance());
        auto* page = new QWidget(pages);
        auto* layout = new QVBoxLayout(page);
        layout->addWidget(heading(QStringLiteral("Termos da instalação"), 5, page));

        auto* terms = new QPlainTextEdit(page);
        terms->setAccessibleName(QStringLiteral("Termos da instalação"));
        terms->setReadOnly(true);
        auto termsFont = terms->font();
        termsFont.setPointSize(qMax(11, termsFont.pointSize()));
        terms->setFont(termsFont);
        terms->document()->setDocumentMargin(14);
        terms->setPlainText(QStringLiteral(
            "O Linux BR reúne programas distribuídos sob suas respectivas licenças. "
            "Os textos e avisos dos componentes instalados podem ser consultados em /usr/share/doc.\n\n"
            "Confira o modelo e a capacidade do disco na próxima etapa. A tela de resumo lista "
            "os volumes que serão criados, formatados ou preservados. A gravação começa após a confirmação final.\n\n"
            "A instalação prepara os arquivos do sistema. Depois do primeiro reinício, "
            "a configuração inicial orienta a escolha do teclado, da rede e da conta de acesso."));
        layout->addWidget(terms, 1);
        accepted = new QCheckBox(QStringLiteral("Li e aceito as condições da instalação"), page);
        layout->addWidget(accepted);
        connect(accepted, &QCheckBox::toggled, this, &Calamares::ViewStep::nextStatusChanged);
        pages->addWidget(page);
        preflight = new PreflightPage([this] { emit nextStatusChanged(isNextEnabled()); }, pages);
        pages->addWidget(preflight);
    }

    ~InstallationViewStep() override
    {
        if (pages && !pages->parent())
            delete pages;
    }

    QString prettyName() const override { return QStringLiteral("Termos e verificação"); }
    QWidget* widget() override { return pages; }
    bool isNextEnabled() const override { return isAtBeginning() ? accepted->isChecked() : preflight->ready(); }
    bool isBackEnabled() const override { return true; }
    bool isAtBeginning() const override { return pages->currentIndex() == 0; }
    bool isAtEnd() const override { return pages->currentIndex() == 1; }
    Calamares::JobList jobs() const override { return {}; }

    void onActivate() override { preflight->scan(); }
    void onLeave() override
    {
        Calamares::JobQueue::instance()->globalStorage()->insert(
            QStringLiteral("linuxbrLiveChecks"),
            QString::fromUtf8(QJsonDocument(preflight->liveChecks()).toJson(QJsonDocument::Compact)));
    }
    void next() override
    {
        if (accepted->isChecked())
            pages->setCurrentWidget(preflight);
    }
    void back() override { pages->setCurrentIndex(0); }

private:
    QPointer<QStackedWidget> pages;
    QCheckBox* accepted;
    PreflightPage* preflight;
};

CALAMARES_PLUGIN_FACTORY_DECLARATION(InstallationViewStepFactory)
CALAMARES_PLUGIN_FACTORY_DEFINITION(InstallationViewStepFactory, registerPlugin<InstallationViewStep>();)

#include "Installation.moc"
