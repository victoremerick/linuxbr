// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "search/dolphinsearchbox.h"

#include <KActionCollection>
#include <QAction>
#include <QIcon>
#include <QPointer>
#include <QStackedWidget>
#include <QTabBar>
#include <QToolBar>
#include <QToolButton>
#include <QVBoxLayout>

#include <array>
#include <initializer_list>
#include <utility>

class LinuxBRFileRibbon : public QWidget
{
public:
    LinuxBRFileRibbon(KActionCollection *actions, QWidget *parent)
        : QWidget(parent)
        , m_tabs(new QTabBar(this))
        , m_pages(new QStackedWidget(this))
    {
        auto *layout = new QVBoxLayout(this);
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(0);
        m_tabs->setObjectName(QStringLiteral("linuxbrRibbonTabs"));
        m_tabs->setAccessibleName(QStringLiteral("Comandos do Explorador de arquivos"));
        m_tabs->setExpanding(false);
        m_tabs->setDrawBase(true);
        layout->addWidget(m_tabs);
        layout->addWidget(m_pages);

        auto *home = addPage(QStringLiteral("&Início"), QStringLiteral("linuxbrHomeActions"));
        addActions(home, actions, {{"new_menu", "Novo"}});
        home->addSeparator();
        addActions(home, actions, {{"edit_cut", "Recortar"}, {"edit_copy", "Copiar"}, {"edit_paste", "Colar"}, {"edit_undo", "Desfazer"}});
        addActions(home, actions, {{"linuxbr_paste_special", "Colar especial"}, {"undo_close_tab", "Reabrir aba"}});
        home->addSeparator();
        addActions(home, actions, {{"renamefile", "Renomear"}, {"movetotrash", "Lixeira"}, {"properties", "Propriedades"}});
        addActions(home, actions, {{"linuxbr_file_workflows", "Ferramentas de arquivos"}});

        auto *view = addPage(QStringLiteral("&Visualização"), QStringLiteral("linuxbrViewActions"));
        addActions(view, actions, {{"icons", "Ícones"}, {"compact", "Compacto"}, {"details", "Detalhes"}});
        view->addSeparator();
        addActions(view, actions, {{"show_preview", "Prévia"}, {"show_hidden_files", "Itens ocultos"}, {"show_in_groups", "Agrupar"}});
        view->addSeparator();
        addActions(view, actions, {{"linuxbr_folder_options", "Opções de Pasta"}});
        addActions(view, actions, {{"linuxbr_block_previews", "Privacidade de prévias"}});
        view->addSeparator();
        addActions(view, actions, {{"copy_to_inactive_split_view", "Copiar para outro painel"},
                                   {"move_to_inactive_split_view", "Mover para outro painel"},
                                   {"linuxbr_compare_panels", "Comparar painéis"}});

        auto *search = addPage(QStringLiteral("&Pesquisar"), QStringLiteral("linuxbrSearchActions"));
        addSearchOption(search, 0, "edit-find", "Nome do arquivo");
        addSearchOption(search, 1, "document-preview", "Conteúdo");
        search->addSeparator();
        addSearchOption(search, 2, "folder", "Pasta atual");
        addSearchOption(search, 3, "user-home", "Meus arquivos");
        search->addSeparator();
        addActions(search, actions, {{"linuxbr_saved_searches", "Consultas salvas"}});
        auto *close = search->addAction(QIcon::fromTheme(QStringLiteral("dialog-close")), QStringLiteral("Encerrar pesquisa"));
        connect(close, &QAction::triggered, actions->action(QStringLiteral("toggle_search")), &QAction::trigger);
        m_tabs->setTabVisible(SearchPage, false);

        connect(m_tabs, &QTabBar::currentChanged, m_pages, &QStackedWidget::setCurrentIndex);
    }

    void setSearchContext(DolphinSearchBox *searchBox)
    {
        if (m_searchBox != searchBox) {
            if (m_searchBox) {
                m_searchBox->setRibbonOptionsActive(false);
            }
            m_searchBox = searchBox;
            if (m_searchBox) {
                m_searchBox->setRibbonOptionsActive(true);
            }
        }
        const bool wasVisible = m_tabs->isTabVisible(SearchPage);
        if (!searchBox && m_tabs->currentIndex() == SearchPage) {
            m_tabs->setCurrentIndex(0);
        }
        m_tabs->setTabVisible(SearchPage, searchBox != nullptr);
        if (searchBox && !wasVisible) {
            m_tabs->setCurrentIndex(SearchPage);
        }

        using Option = DolphinSearchBox::RibbonOption;
        constexpr Option options[] = {Option::FileName, Option::Content, Option::CurrentFolder, Option::Home};
        for (std::size_t index = 0; index < m_searchActions.size(); ++index) {
            auto &binding = m_searchActions[index];
            auto *button = searchBox ? searchBox->ribbonButton(options[index]) : nullptr;
            if (binding.button != button) {
                disconnect(binding.checkedConnection);
                binding.button = button;
                if (button) {
                    binding.checkedConnection = connect(button, &QToolButton::toggled, binding.action, &QAction::setChecked);
                }
            }
            binding.action->setEnabled(button && button->isEnabled());
            binding.action->setChecked(button && button->isChecked());
        }
    }

private:
    struct SearchBinding {
        QAction *action = nullptr;
        QPointer<QToolButton> button;
        QMetaObject::Connection checkedConnection;
    };

    static constexpr int SearchPage = 2;

    QToolBar *addPage(const QString &title, const QString &name)
    {
        auto *page = new QToolBar(m_pages);
        page->setObjectName(name);
        page->setAccessibleName(QString(title).remove(QLatin1Char('&')));
        page->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
        page->setIconSize(QSize(20, 20));
        page->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        m_pages->addWidget(page);
        m_tabs->addTab(title);
        return page;
    }

    static void addActions(QToolBar *bar, KActionCollection *actions,
                           std::initializer_list<std::pair<const char *, const char *>> entries)
    {
        for (const auto &[name, label] : entries) {
            auto *action = actions->action(QString::fromLatin1(name));
            action->setIconText(QString::fromUtf8(label));
            action->setPriority(QAction::NormalPriority);
            bar->addAction(action);
        }
    }

    void addSearchOption(QToolBar *bar, std::size_t index, const char *icon, const char *label)
    {
        auto &binding = m_searchActions[index];
        binding.action = bar->addAction(QIcon::fromTheme(QString::fromLatin1(icon)), QString::fromUtf8(label));
        binding.action->setCheckable(true);
        binding.action->setEnabled(false);
        connect(binding.action, &QAction::triggered, this, [this, index] {
            const auto &binding = m_searchActions[index];
            if (binding.button) {
                binding.button->click();
                binding.action->setChecked(binding.button->isChecked());
            }
        });
    }

    QTabBar *m_tabs;
    QStackedWidget *m_pages;
    QPointer<DolphinSearchBox> m_searchBox;
    std::array<SearchBinding, 4> m_searchActions;
};
