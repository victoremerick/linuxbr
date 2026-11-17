// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "dolphin_generalsettings.h"

#include <KConfigGroup>
#include <KSharedConfig>
#include <QCheckBox>
#include <QComboBox>
#include <QDialog>
#include <QDialogButtonBox>
#include <QDir>
#include <QFormLayout>
#include <QGroupBox>
#include <QIcon>
#include <QLabel>
#include <QPushButton>
#include <QTabWidget>
#include <QVBoxLayout>

class LinuxBRFolderOptions : public QDialog
{
public:
    explicit LinuxBRFolderOptions(QWidget *parent)
        : QDialog(parent)
    {
        setWindowTitle(QStringLiteral("Opções de Pasta"));
        setWindowIcon(QIcon::fromTheme(QStringLiteral("folder")));
        auto *layout = new QVBoxLayout(this);
        auto *tabs = new QTabWidget(this);
        layout->addWidget(tabs);

        auto *general = new QWidget(tabs);
        auto *generalLayout = new QVBoxLayout(general);
        auto *navigation = new QGroupBox(QStringLiteral("Navegação"), general);
        auto *navigationLayout = new QFormLayout(navigation);
        m_home = new QComboBox(navigation);
        m_home->addItem(QStringLiteral("Este Computador"), QStringLiteral("linuxbr:/"));
        m_home->addItem(QStringLiteral("Pasta pessoal"), QDir::homePath());
        const QString currentHome = GeneralSettings::homeUrl();
        if (m_home->findData(currentHome) < 0 && !currentHome.isEmpty()) {
            m_home->addItem(currentHome, currentHome);
        }
        navigationLayout->addRow(QStringLiteral("Abrir o &Explorador em"), m_home);
        m_navigation = new QComboBox(navigation);
        m_navigation->addItems({QStringLiteral("Na mesma janela"), QStringLiteral("Em uma nova janela")});
        navigationLayout->addRow(QStringLiteral("Ao &abrir uma pasta"), m_navigation);
        generalLayout->addWidget(navigation);
        generalLayout->addStretch();
        tabs->addTab(general, QStringLiteral("&Geral"));

        auto *display = new QWidget(tabs);
        auto *displayLayout = new QVBoxLayout(display);
        auto *visibility = new QGroupBox(QStringLiteral("Arquivos e pastas"), display);
        auto *visibilityLayout = new QVBoxLayout(visibility);
        m_showHidden = new QCheckBox(QStringLiteral("Mostrar arquivos e &pastas ocultos"), visibility);
        m_hideSystem = new QCheckBox(QStringLiteral("Ocultar arquivos e pastas de &sistema protegidos"), visibility);
        auto *hint = new QLabel(QStringLiteral("Ctrl+H alterna os itens ocultos da pasta atual. A exibição de itens de sistema é independente."), visibility);
        hint->setWordWrap(true);
        visibilityLayout->addWidget(m_showHidden);
        visibilityLayout->addWidget(m_hideSystem);
        visibilityLayout->addWidget(hint);
        displayLayout->addWidget(visibility);
        m_fullPath = new QCheckBox(QStringLiteral("Mostrar o caminho &completo na barra de título"), display);
        displayLayout->addWidget(m_fullPath);
        displayLayout->addStretch();
        tabs->addTab(display, QStringLiteral("&Modo de Exibição"));

        auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel | QDialogButtonBox::Apply | QDialogButtonBox::RestoreDefaults, this);
        layout->addWidget(buttons);
        buttons->button(QDialogButtonBox::Cancel)->setText(QStringLiteral("Cancelar"));
        buttons->button(QDialogButtonBox::RestoreDefaults)->setText(QStringLiteral("Restaurar padrões"));
        m_apply = buttons->button(QDialogButtonBox::Apply);
        m_apply->setText(QStringLiteral("Aplicar"));
        for (auto *combo : {m_home, m_navigation}) {
            connect(combo, &QComboBox::currentIndexChanged, this, [this] { updateApply(); });
        }
        for (auto *check : {m_showHidden, m_hideSystem, m_fullPath}) {
            connect(check, &QCheckBox::toggled, this, [this] { updateApply(); });
        }
        connect(buttons->button(QDialogButtonBox::RestoreDefaults), &QPushButton::clicked, this, [this] {
            load({QStringLiteral("linuxbr:/"), false, false, true, false});
        });
        connect(m_apply, &QPushButton::clicked, this, [this] { apply(); });
        connect(buttons, &QDialogButtonBox::accepted, this, [this] { apply(); accept(); });
        connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);

        m_saved = {currentHome.isEmpty() ? QDir::homePath() : currentHome,
                   GeneralSettings::linuxBrOpenFoldersInNewWindow(),
                   GeneralSettings::linuxBrShowHiddenFiles(),
                   GeneralSettings::linuxBrHideSystemFiles(),
                   GeneralSettings::showFullPathInTitlebar()};
        load(m_saved);
    }

private:
    struct Options {
        QString home;
        bool newWindow;
        bool showHidden;
        bool hideSystem;
        bool fullPath;
        bool operator==(const Options &) const = default;
    };

    Options current() const
    {
        return {m_home->currentData().toString(), m_navigation->currentIndex() == 1,
                m_showHidden->isChecked(), m_hideSystem->isChecked(), m_fullPath->isChecked()};
    }

    void load(const Options &opts)
    {
        m_home->setCurrentIndex(m_home->findData(opts.home));
        m_navigation->setCurrentIndex(opts.newWindow ? 1 : 0);
        m_showHidden->setChecked(opts.showHidden);
        m_hideSystem->setChecked(opts.hideSystem);
        m_fullPath->setChecked(opts.fullPath);
        updateApply();
    }

    void updateApply()
    {
        m_apply->setEnabled(current() != m_saved);
    }

    void apply()
    {
        const auto opts = current();
        if (opts == m_saved) {
            return;
        }
        KConfigGroup config(KSharedConfig::openConfig(QStringLiteral("dolphinrc")), QStringLiteral("General"));
        const auto flags = KConfig::Persistent | KConfig::Notify;
        if (opts.home != m_saved.home) {
            config.writeEntry("HomeUrl", opts.home, flags);
            config.writeEntry("RememberOpenedTabs", false, flags);
            config.writeEntry("ModifiedStartupSettings", true, flags);
        }
        if (opts.newWindow != m_saved.newWindow) {
            config.writeEntry("LinuxBrOpenFoldersInNewWindow", opts.newWindow, flags);
        }
        if (opts.showHidden != m_saved.showHidden) {
            config.writeEntry("LinuxBrShowHiddenFiles", opts.showHidden, flags);
        }
        if (opts.hideSystem != m_saved.hideSystem) {
            config.writeEntry("LinuxBrHideSystemFiles", opts.hideSystem, flags);
        }
        if (opts.fullPath != m_saved.fullPath) {
            config.writeEntry("ShowFullPathInTitlebar", opts.fullPath, flags);
        }
        config.sync();
        m_saved = opts;
        updateApply();
    }

    QComboBox *m_home;
    QComboBox *m_navigation;
    QCheckBox *m_showHidden;
    QCheckBox *m_hideSystem;
    QCheckBox *m_fullPath;
    QPushButton *m_apply;
    Options m_saved{};
};
