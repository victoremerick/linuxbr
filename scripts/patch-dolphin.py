#!/usr/bin/env python3
"""Small guarded downstream patch for Debian Dolphin 25.04.x. Fail on drift."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
source=Path(__file__).resolve().parents[1]/'packages/linuxbr-dolphin/cards.cpp.inc'
def replace(file, old, new):
    path=root/file; text=path.read_text()
    if text.count(old)!=1: raise SystemExit(f'Contexto Dolphin mudou: {file}: {old[:60]}')
    path.write_text(text.replace(old,new))
replace('src/views/dolphinfileitemlistwidget.h','    void refreshCache() override;', '''    void refreshCache() override;
    void paint(QPainter *, const QStyleOptionGraphicsItem *, QWidget *) override;
    QRectF iconRect() const override;
    QRectF textRect() const override;
    QRectF textFocusRect() const override;
    QRectF selectionRect() const override;
    QVariantMap linuxbrCard() const;''')
path=root/'src/views/dolphinfileitemlistwidget.cpp'
path.write_text(path.read_text()+'\n'+source.read_text())
replace('src/kitemviews/kfileitemmodel.cpp','#include "kfileitemmodel.h"','#include "kfileitemmodel.h"\n#include <QJsonDocument>\n#include <QJsonObject>')
replace('src/kitemviews/kfileitemmodel.cpp','    data.insert(sharedValue("url"), item.url());','''    data.insert(sharedValue("url"), item.url());
    if (item.url().scheme() == QLatin1String("linuxbr")) {
        data.insert("linuxbrCard", QJsonDocument::fromJson(item.entry().stringValue(KIO::UDSEntry::UDS_EXTRA).toUtf8()).object().toVariantMap());
    }''')
replace('src/views/dolphinitemlistview.h','    void updateFont() override;', '    void updateFont() override;\n    void onModelChanged(KItemModelBase *current, KItemModelBase *previous) override;\n    QMetaObject::Connection m_linuxbrLoaded;')
replace('src/views/dolphinitemlistview.cpp','#include "dolphinitemlistview.h"','#include "dolphinitemlistview.h"\n#include "kitemviews/kfileitemmodel.h"')
path=root/'src/views/dolphinitemlistview.cpp'
path.write_text(path.read_text()+'''
void DolphinItemListView::onModelChanged(KItemModelBase *current, KItemModelBase *previous)
{
    disconnect(m_linuxbrLoaded);
    KFileItemListView::onModelChanged(current, previous);
    if (auto files = qobject_cast<KFileItemModel *>(current)) {
        m_linuxbrLoaded = connect(files, &KFileItemModel::directoryLoadingCompleted, this, [this]() { updateGridSize(); });
    }
}
''')
replace('src/views/dolphinitemlistview.cpp','    // Apply the calculated values','''    if (model() && model()->directory().scheme() == QLatin1String("linuxbr")
        && itemLayout() == KFileItemListView::IconsLayout) {
        itemWidth = qMax(360, option.fontMetrics.averageCharWidth()*48);
        itemHeight = qMax(112, option.fontMetrics.lineSpacing()*6);
        maxTextLines = 1;
    }
    // Apply the calculated values''')
replace('src/views/viewproperties.cpp','    const bool useGlobalViewProps = settings->globalViewProps() || url.isEmpty();','''    const bool linuxbrComputer = url.scheme() == QLatin1String("linuxbr") && (url.path().isEmpty() || url.path() == QLatin1String("/"));
    const bool useGlobalViewProps = !linuxbrComputer && (settings->globalViewProps() || url.isEmpty());''')
replace('src/views/viewproperties.cpp','    } else if (useGlobalViewProps) {','''    } else if (linuxbrComputer) {
        m_filePath = destinationDir(QStringLiteral("linuxbr-computer"));
    } else if (useGlobalViewProps) {''')
replace('src/views/viewproperties.cpp','    if (m_node->version() < CurrentViewPropertiesVersion) {','''    if (linuxbrComputer) {
        setViewMode(DolphinView::IconsView);
        setGroupedSorting(true);
        setSortRole(QByteArrayLiteral("type"));
        setSortOrder(Qt::AscendingOrder);
        setVisibleRoles({"text"});
    }
    if (m_node->version() < CurrentViewPropertiesVersion) {''')

replace('src/kitemviews/kstandarditemlistwidget.cpp',
        '    const QFont &normalFont = option.font;\n    const int additionalRolesCount = qMax(view->visibleRoles().count() - 1, 0);',
        '''    const QFont &normalFont = option.font;
    if (view->model()->directory().scheme() == QLatin1String("linuxbr")) {
        logicalHeightHints.fill(std::make_pair(qreal(qMax(112, option.fontMetrics.lineSpacing()*6)), false));
        logicalWidthHint = view->itemSize().width();
        return;
    }
    const int additionalRolesCount = qMax(view->visibleRoles().count() - 1, 0);''')

# Compare unit identifiers, never the localized label or changing free-space text.
# Keep the existing ancestry handling above this insertion for expanded folders.
replace('src/kitemviews/kfileitemmodel.cpp', '    // Show hidden files and folders last', '''    if (a->item.url().scheme() == QLatin1String("linuxbr")
        && b->item.url().scheme() == QLatin1String("linuxbr")
        && a->item.url().path().size() == 2 && b->item.url().path().size() == 2) {
        const auto groupRank = [](const KFileItem &item) {
            const QString group = item.entry().stringValue(KIO::UDSEntry::UDS_DISPLAY_TYPE);
            if (group == QLatin1String("Discos locais")) return 0;
            if (group == QStringLiteral("Dispositivos removíveis")) return 1;
            if (group == QLatin1String("Unidades de rede")) return 2;
            return 3;
        };
        const int groupA = groupRank(a->item);
        const int groupB = groupRank(b->item);
        if (groupA != groupB) return groupA < groupB;
        return a->item.url().path() < b->item.url().path();
    }

    // Show hidden files and folders last''')

# Apply the new sidebar default once, after restoring the saved dock layout.
# Subsequent starts respect the user's panel choices; bookmarks remain intact.
replace('src/dolphinmainwindow.cpp', '    stateChanged(QStringLiteral("new_file"));', '''    KConfigGroup linuxbrNavigation(KSharedConfig::openConfig(), QStringLiteral("LinuxBRNavigation"));
    if (!usePhoneUi && !linuxbrNavigation.readEntry("GroupedSidebarInitialized", false)) {
        if (auto *tree = findChild<QDockWidget *>(QStringLiteral("foldersDock"))) {
            tree->show();
            m_placesPanel->parentWidget()->hide();
            linuxbrNavigation.writeEntry("GroupedSidebarInitialized", true);
            linuxbrNavigation.sync();
        }
    }
    stateChanged(QStringLiteral("new_file"));''')
replace('src/dolphinmainwindow.cpp', '#include <QApplication>', '#include <KConfigGroup>\n#include <KSharedConfig>\n#include <QApplication>')

# KIO resolves drive aliases to file:/ or smb:/. Keep redirected children under
# their virtual drive instead of inserting them as additional root entries.
replace('src/kitemviews/kfileitemmodel.cpp',
        '    connect(m_dirLister, &KCoreDirLister::redirection, this, &KFileItemModel::directoryRedirection);', '''    connect(m_dirLister, &KCoreDirLister::redirection, this, [this](const QUrl &oldUrl, const QUrl &newUrl) {
        if (m_expandedDirs.contains(oldUrl) && m_expandedDirs.value(oldUrl).scheme() == QLatin1String("linuxbr")) {
            const QUrl alias = m_expandedDirs.take(oldUrl);
            m_expandedDirs.insert(newUrl, alias);
        } else {
            Q_EMIT directoryRedirection(oldUrl, newUrl);
        }
    });''')
replace('src/kitemviews/kfileitemmodel.cpp',
        '    const QUrl targetUrl = item.targetUrl();\n    if (expanded) {', '''    QUrl targetUrl = item.targetUrl();
    if (!expanded && url.scheme() == QLatin1String("linuxbr")) {
        for (auto it = m_expandedDirs.cbegin(); it != m_expandedDirs.cend(); ++it) {
            if (it.value() == url) { targetUrl = it.key(); break; }
        }
    }
    if (expanded) {''')
replace('src/kitemviews/kfileitemmodel.cpp',
        '        m_dirLister->stop(url);\n        m_dirLister->forgetDirs(url);', '''        const QUrl listedUrl = url.scheme() == QLatin1String("linuxbr") ? targetUrl : url;
        m_dirLister->stop(listedUrl);
        m_dirLister->forgetDirs(listedUrl);''')

# Keep the narrow tree readable; capacity remains on the large cards.
replace('src/kitemviews/kfileitemmodel.cpp',
        '        data.insert(sharedValue("text"), item.text());', '''        const QString driveTitle = data.value("linuxbrCard").toMap().value("title").toString();
        data.insert(sharedValue("text"), showDirectoriesOnly() && !driveTitle.isEmpty() ? driveTitle : item.text());''')

# Four persistent navigation groups inside the existing F7 dock.
for name in ("sidebar.h", "sidebar-state.h"):
    (root / "src" / ("linuxbr-" + name)).write_text((source.parent / name).read_text())
replace('src/dolphinmainwindow.cpp', '#include <QApplication>', '#include "linuxbr-sidebar.h"\n#include <QApplication>')
replace('src/dolphinmainwindow.cpp', '#include <QApplication>', '#include <QApplication>\n#include <QProcess>')
replace('src/dolphinmainwindow.cpp',
        '    setupGUI(Save | Create | ToolBar, usePhoneUi ? QStringLiteral("dolphinuiforphones.rc") : QString() /* load the default dolphinui.rc file */);',
        '''    setupGUI(Save | Create | ToolBar, usePhoneUi ? QStringLiteral("dolphinuiforphones.rc") : QString() /* load the default dolphinui.rc file */);
    if (!QStandardPaths::findExecutable(QStringLiteral("linuxbr-wiki")).isEmpty()) {
        auto *help = actionCollection()->action(KStandardAction::name(KStandardAction::HelpContents));
        if (help) {
            disconnect(help, &QAction::triggered, nullptr, nullptr);
            help->setText(QStringLiteral("Ajuda do Explorador"));
            connect(help, &QAction::triggered, this, [this] {
                const auto guide = m_activeViewContainer && m_activeViewContainer->isSearchModeEnabled()
                    ? QStringLiteral("pesquisa-arquivos") : QStringLiteral("copiar-arquivos");
                if (!QProcess::startDetached(QStringLiteral("linuxbr-wiki"), {guide})) {
                    showErrorMessage(QStringLiteral("Não foi possível abrir a Wiki do Linux BR."));
                }
            });
        }
    }''')
replace('src/dolphinmainwindow.cpp', '    FoldersPanel *foldersPanel = new FoldersPanel(foldersDock);\n    foldersPanel->setCustomContextMenuActions({lockLayoutAction});', '''    auto *foldersPanel = new LinuxBRSidebar(foldersDock, [this](const QUrl &url, bool newTab) {
        if (newTab) openNewTab(url); else changeUrl(url);
    });''')
replace('src/dolphinmainwindow.cpp', '    connect(this, &DolphinMainWindow::urlChanged, foldersPanel, &FoldersPanel::setUrl);\n    connect(foldersPanel, &FoldersPanel::folderActivated, this, &DolphinMainWindow::changeUrl);\n    connect(foldersPanel, &FoldersPanel::folderInNewTab, this, &DolphinMainWindow::openNewTab);\n    connect(foldersPanel, &FoldersPanel::folderInNewActiveTab, this, &DolphinMainWindow::openNewTabAndActivate);\n    connect(foldersPanel, &FoldersPanel::errorMessage, this, &DolphinMainWindow::showErrorMessage);',
        '    connect(this, &DolphinMainWindow::urlChanged, foldersPanel, &LinuxBRSidebar::setLocation);')

replace('src/dolphinmainwindow.cpp', 'new DolphinDockWidget(i18nc("@title:window", "Folders"))', 'new DolphinDockWidget(QStringLiteral("Navegação"))')

# Record successful listings, not every attempted navigation or tree expansion.
replace('src/dolphinmainwindow.cpp',
        '    connect(view, &DolphinView::directoryLoadingCompleted, this, &DolphinMainWindow::slotDirectoryLoadingCompleted);', '''    connect(view, &DolphinView::directoryLoadingCompleted, this, &DolphinMainWindow::slotDirectoryLoadingCompleted);
    connect(view, &DolphinView::directoryLoadingCompleted, this, [this, view]() {
        if (auto *tree = findChild<QTreeWidget *>(QStringLiteral("linuxbrSidebar"))) {
            static_cast<LinuxBRSidebar *>(tree)->recordVisit(view->url());
        }
    });''')

for name in ("folder-options.h", "folder-visibility.h", "file-ribbon.h"):
    (root / "src" / ("linuxbr-" + name)).write_text((source.parent / name).read_text())
replace('src/settings/dolphin_generalsettings.kcfg', '    <group name="General">', '''    <group name="General">
        <entry name="LinuxBrShowHiddenFiles" type="Bool">
            <default>false</default>
        </entry>
        <entry name="LinuxBrHideSystemFiles" type="Bool">
            <default>true</default>
        </entry>
        <entry name="LinuxBrOpenFoldersInNewWindow" type="Bool">
            <default>false</default>
        </entry>''')

replace('src/dolphinmainwindow.h', '#include <KActionMenu>', '#include <KActionMenu>\n#include <KConfigWatcher>')
replace('src/dolphinmainwindow.h', '    QPointer<DolphinSettingsDialog> m_settingsDialog;',
        '    QPointer<DolphinSettingsDialog> m_settingsDialog;\n    KConfigWatcher::Ptr m_linuxbrFolderWatcher;')
replace('src/dolphinmainwindow.cpp', '#include "linuxbr-sidebar.h"',
        '#include "linuxbr-sidebar.h"\n#include "linuxbr-folder-options.h"')
replace('src/dolphinmainwindow.cpp', "    // setup 'File' menu", '''    auto *folderOptions = actionCollection()->addAction(QStringLiteral("linuxbr_folder_options"));
    folderOptions->setText(QStringLiteral("Opções de &Pasta"));
    folderOptions->setIcon(QIcon::fromTheme(QStringLiteral("folder")));
    connect(folderOptions, &QAction::triggered, this, [this] {
        auto *dialog = new LinuxBRFolderOptions(this);
        dialog->setAttribute(Qt::WA_DeleteOnClose);
        dialog->open();
    });

    m_linuxbrFolderWatcher = KConfigWatcher::create(KSharedConfig::openConfig(QStringLiteral("dolphinrc")));
    connect(m_linuxbrFolderWatcher.data(), &KConfigWatcher::configChanged, this,
            [this](const KConfigGroup &group, const QByteArrayList &keys) {
        if (group.name() != QLatin1String("General")) {
            return;
        }
        GeneralSettings::self()->load();
        if (keys.contains("LinuxBrShowHiddenFiles") || keys.contains("LinuxBrHideSystemFiles")) {
            for (auto *view : findChildren<DolphinView *>()) {
                view->resetLinuxBrFolderVisibility();
            }
        }
        if (keys.contains("ShowFullPathInTitlebar") || keys.contains("HomeUrl")) {
            refreshViews();
            DolphinUrlNavigatorsController::slotReadSettings();
        }
    });

    // setup 'File' menu''')
replace('src/dolphinmainwindow.cpp', '    menu->addAction(ac->action(QStringLiteral("show_hidden_files")));',
        '    menu->addAction(ac->action(QStringLiteral("show_hidden_files")));\n'
        '    menu->addAction(ac->action(QStringLiteral("linuxbr_folder_options")));')
for file, version in (('src/dolphinui.rc', 43), ('src/dolphinuiforphones.rc', 1)):
    replace(file, f'<gui name="dolphin" version="{version}">', f'<gui name="dolphin" version="{version + 2}">')
    replace(file, '            <Action name="show_hidden_files" />',
            '            <Action name="show_hidden_files" />\n            <Action name="linuxbr_folder_options" />')
    replace(file, '        <Action name="toggle_search" />', '        <Action name="linuxbr_search_field" />')

replace('src/dolphinmainwindow.h', 'class DolphinViewContainer;', 'class DolphinViewContainer;\nclass LinuxBRFileRibbon;')
replace('src/dolphinmainwindow.h', '    KConfigWatcher::Ptr m_linuxbrFolderWatcher;',
        '''    KConfigWatcher::Ptr m_linuxbrFolderWatcher;
    LinuxBRFileRibbon *m_linuxbrFileRibbon = nullptr;
    QWidget *m_linuxbrSearchHost = nullptr;
    QPointer<DolphinSearchBox> m_linuxbrHostedSearch;''')
replace('src/dolphinmainwindow.h', 'class LinuxBRFileRibbon;', 'class LinuxBRFileRibbon;\nclass DolphinSearchBox;')
replace('src/dolphinmainwindow.cpp', '#include "linuxbr-folder-options.h"',
        '#include "linuxbr-folder-options.h"\n#include "linuxbr-file-ribbon.h"')
replace('src/dolphinmainwindow.cpp', '    KConfigGroup linuxbrNavigation(KSharedConfig::openConfig(), QStringLiteral("LinuxBRNavigation"));',
        '''    auto *commands = new QToolBar(QStringLiteral("Abas do Explorador"), this);
    commands->setObjectName(QStringLiteral("linuxbrFileRibbon"));
    commands->setAllowedAreas(Qt::TopToolBarArea);
    commands->setFloatable(false);
    commands->setMovable(false);
    m_linuxbrFileRibbon = new LinuxBRFileRibbon(actionCollection(), commands);
    m_linuxbrFileRibbon->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    commands->addWidget(m_linuxbrFileRibbon);
    if (toolBarArea(toolBar()) != Qt::TopToolBarArea) {
        addToolBar(Qt::TopToolBarArea, toolBar());
    }
    insertToolBar(toolBar(), commands);
    insertToolBarBreak(toolBar());
    connect(this, &DolphinMainWindow::urlChanged, this, &DolphinMainWindow::updateSearchAction);

    KConfigGroup linuxbrNavigation(KSharedConfig::openConfig(), QStringLiteral("LinuxBRNavigation"));''')
replace('src/dolphinmainwindow.cpp',
        '    toggleSearchAction->setChecked(m_activeViewContainer->isSearchModeEnabled());',
        '''    toggleSearchAction->setChecked(m_activeViewContainer->isSearchModeEnabled());
    if (m_linuxbrSearchHost) {
        auto *searchBox = m_activeViewContainer->addressBarSearchBox();
        if (m_linuxbrHostedSearch != searchBox) {
            if (m_linuxbrHostedSearch) {
                m_linuxbrHostedSearch->setRibbonInputHost(nullptr);
            }
            m_linuxbrHostedSearch = searchBox;
            searchBox->setRibbonInputHost(m_linuxbrSearchHost);
        }
        searchBox->syncRibbonInput(m_activeViewContainer->url(), m_activeViewContainer->isSearchModeEnabled());
    }
    if (m_linuxbrFileRibbon) {
        m_linuxbrFileRibbon->setSearchContext(m_activeViewContainer->searchBoxForRibbon());
    }''')
replace('src/dolphinviewcontainer.h', '    bool isSearchModeEnabled() const;',
        '''    bool isSearchModeEnabled() const;
    DolphinSearchBox *searchBoxForRibbon() const;
    DolphinSearchBox *addressBarSearchBox() const { return m_searchBox; }''')
replace('src/dolphinviewcontainer.h', '    bool isSearchUrl(const QUrl &url) const;',
        '    bool isSearchUrl(const QUrl &url) const;\n    QUrl addressBarLocation(const QUrl &url) const;')
replace('src/dolphinmainwindow.cpp',
        '    auto hamburgerMenuAction = KStandardAction::hamburgerMenu(nullptr, nullptr, actionCollection());',
        '''    auto hamburgerMenuAction = KStandardAction::hamburgerMenu(nullptr, nullptr, actionCollection());
    m_linuxbrSearchHost = new QWidget(this);
    m_linuxbrSearchHost->setObjectName(QStringLiteral("linuxbrSearchHost"));
    m_linuxbrSearchHost->setMinimumWidth(140);
    m_linuxbrSearchHost->setMaximumWidth(270);
    auto *searchLayout = new QHBoxLayout(m_linuxbrSearchHost);
    searchLayout->setContentsMargins(4, 0, 2, 0);
    auto *searchFieldAction = new QWidgetAction(actionCollection());
    searchFieldAction->setText(QStringLiteral("Pesquisar"));
    searchFieldAction->setDefaultWidget(m_linuxbrSearchHost);
    actionCollection()->addAction(QStringLiteral("linuxbr_search_field"), searchFieldAction);''')
replace('src/dolphinviewcontainer.cpp', 'bool DolphinViewContainer::isSearchModeEnabled() const',
        '''DolphinSearchBox *DolphinViewContainer::searchBoxForRibbon() const
{
    return isSearchModeEnabled() && isSearchUrl(url()) ? m_searchBox : nullptr;
}

bool DolphinViewContainer::isSearchModeEnabled() const''')
replace('src/dolphinviewcontainer.cpp',
        '        if (m_urlNavigatorConnected) {\n            m_urlNavigatorConnected->setLocationUrl(url);\n        }\n    }\n\n    m_searchModeEnabled = enabled;',
        '''        if (isSearchUrl(m_urlNavigator->locationUrl())) {
            m_urlNavigator->setLocationUrl(url);
        }
    }

    m_searchModeEnabled = enabled;''')
replace('src/dolphinviewcontainer.cpp', '#include "dolphinviewcontainer.h"', '#include "dolphinviewcontainer.h"\n#include <QSignalBlocker>')
replace('src/dolphinviewcontainer.cpp',
        '        const QString title = query.queryItemValue(QStringLiteral("title"));',
        '''        const auto titleFormat = isSearchUrl(url()) ? QUrl::FullyDecoded : QUrl::PrettyDecoded;
        const QString title = query.queryItemValue(QStringLiteral("title"), titleFormat);''')
replace('src/dolphinviewcontainer.cpp', '    urlNavigator->setLocationUrl(m_view->url());',
        '    urlNavigator->setLocationUrl(addressBarLocation(m_view->url()));')
replace('src/dolphinviewcontainer.cpp',
        '    connect(m_view, &DolphinView::urlChanged, urlNavigator, &DolphinUrlNavigator::setLocationUrl);',
        '''    connect(m_view, &DolphinView::urlChanged, urlNavigator, [this, urlNavigator](const QUrl &url) {
        const QSignalBlocker blocker(urlNavigator);
        urlNavigator->setLocationUrl(addressBarLocation(url));
    });''')
replace('src/dolphinviewcontainer.cpp',
        '    disconnect(m_view, &DolphinView::urlChanged, m_urlNavigatorConnected, &DolphinUrlNavigator::setLocationUrl);',
        '    disconnect(m_view, &DolphinView::urlChanged, m_urlNavigatorConnected, nullptr);')
replace('src/dolphinviewcontainer.cpp', 'bool DolphinViewContainer::isSearchUrl(const QUrl &url) const',
        '''QUrl DolphinViewContainer::addressBarLocation(const QUrl &url) const
{
    if (!isSearchUrl(url)) {
        return url;
    }
    const QUrl path = m_searchBox->searchPath();
    return path.isValid() && !path.isEmpty() ? path : Dolphin::homeUrl();
}

bool DolphinViewContainer::isSearchUrl(const QUrl &url) const''')
replace('src/dolphinviewcontainer.cpp', '    Q_CHECK_PTR(m_urlNavigatorConnected);\n    const QUrl url = m_searchBox->urlForSearching();',
        '    const QUrl url = m_searchBox->urlForSearching();')
replace('src/dolphinviewcontainer.cpp', '''        // If we open a new tab that has a search assigned to it, we can't
        // update the urlNavigator, since there is none connected to that tab.
        // See BUG:500101
        if (m_urlNavigatorConnected) {
            m_urlNavigatorConnected->setLocationUrl(url);
        }''', '''        m_urlNavigator->setLocationUrl(url);''')
replace('src/search/dolphinsearchbox.h', '    bool isActive() const;', '''    bool isActive() const;

    enum class RibbonOption { FileName, Content, CurrentFolder, Home };
    QToolButton *ribbonButton(RibbonOption option) const;
    void setRibbonOptionsActive(bool active);
    void setRibbonInputHost(QWidget *host);
    void syncRibbonInput(const QUrl &location, bool searching);''')
replace('src/search/dolphinsearchbox.h', '    bool m_initialized;', '    bool m_initialized;\n    QPointer<QWidget> m_ribbonInputRow;\n    QToolButton *m_ribbonCloseButton = nullptr;')
replace('src/search/dolphinsearchbox.h', '#include "animatedheightwidget.h"', '#include "animatedheightwidget.h"\n#include <QPointer>')
replace('src/search/dolphinsearchbox.h', '    bool m_initialized;', '    bool m_initialized;\n    bool m_hasExternalSearchTool = false;')
replace('src/search/dolphinsearchbox.cpp', '#include "dolphinsearchbox.h"', '#include "dolphinsearchbox.h"\n#include <QSignalBlocker>')
replace('src/search/dolphinsearchbox.cpp', 'DolphinSearchBox::~DolphinSearchBox()\n{\n    saveSettings();',
        'DolphinSearchBox::~DolphinSearchBox()\n{\n    saveSettings();\n    delete m_ribbonInputRow.data();')
replace('src/search/dolphinsearchbox.cpp', '    QHBoxLayout *searchInputLayout = new QHBoxLayout();',
        '''    m_ribbonCloseButton = closeButton;
    m_ribbonInputRow = new QWidget(contentsContainer);
    QHBoxLayout *searchInputLayout = new QHBoxLayout(m_ribbonInputRow);''')
replace('src/search/dolphinsearchbox.cpp', '    m_topLayout->addLayout(searchInputLayout);', '    m_topLayout->addWidget(m_ribbonInputRow);')
replace('src/search/dolphinsearchbox.cpp',
        '        m_searchInput->setFocus();\n        m_startedSearching = false;',
        '''        m_searchInput->setFocus();
        if (m_ribbonInputRow->parentWidget() == m_topLayout->parentWidget()) {
            m_startedSearching = false;
        }''')
replace('src/search/dolphinsearchbox.cpp',
        '    m_saveSearchAction->setEnabled(false);\n    m_searchInput->addAction(m_saveSearchAction, QLineEdit::TrailingPosition);',
        '''    m_saveSearchAction->setEnabled(false);
    m_saveSearchAction->setVisible(false);
    connect(m_saveSearchAction, &QAction::enabledChanged, m_saveSearchAction, &QAction::setVisible);
    m_searchInput->addAction(m_saveSearchAction, QLineEdit::TrailingPosition);''')
replace('src/search/dolphinsearchbox.cpp', '    m_searchInput->setClearButtonEnabled(true);',
        '''    m_searchInput->setClearButtonEnabled(true);
    auto *runSearch = m_searchInput->addAction(QIcon::fromTheme(QStringLiteral("edit-find")), QLineEdit::LeadingPosition);
    runSearch->setText(QStringLiteral("Pesquisar"));
    connect(runSearch, &QAction::triggered, this, &DolphinSearchBox::slotReturnPressed);''')
replace('src/search/dolphinsearchbox.cpp', '    switch (event->type()) {', '''    if (event->type() == QEvent::KeyRelease && obj == m_searchInput && m_ribbonInputRow
        && m_ribbonInputRow->parentWidget() != m_topLayout->parentWidget()) {
        auto *keyEvent = static_cast<QKeyEvent *>(event);
        if (keyEvent->key() == Qt::Key_Escape || keyEvent->key() == Qt::Key_Down) {
            keyReleaseEvent(keyEvent);
            return true;
        }
    }
    switch (event->type()) {''')
replace('src/search/dolphinsearchbox.cpp', '    // Create "Facets" widget',
        '    m_hasExternalSearchTool = kfindToolsButton != nullptr;\n\n    // Create "Facets" widget')
replace('src/search/dolphinsearchbox.cpp', 'void DolphinSearchBox::saveSettings()', '''QToolButton *DolphinSearchBox::ribbonButton(RibbonOption option) const
{
    if (!m_initialized) {
        return nullptr;
    }
    switch (option) {
    case RibbonOption::FileName:
        return m_fileNameButton;
    case RibbonOption::Content:
        return m_contentButton;
    case RibbonOption::CurrentFolder:
        return m_fromHereButton;
    case RibbonOption::Home:
        return m_everywhereButton;
    }
    return nullptr;
}

void DolphinSearchBox::setRibbonOptionsActive(bool active)
{
    if (!m_initialized) {
        return;
    }
    if (active) {
        m_startedSearching = true;
    }
    for (auto *button : {m_fileNameButton, m_contentButton, m_fromHereButton, m_everywhereButton}) {
        button->setVisible(!active);
    }
    m_separator->setVisible(!active);
    m_optionsScrollArea->setVisible(!active || m_hasExternalSearchTool);
    if (isVisible() && isEnabled()) {
        setVisible(true, WithAnimation);
    }
}

void DolphinSearchBox::setRibbonInputHost(QWidget *host)
{
    init();
    if (host) {
        host->layout()->addWidget(m_ribbonInputRow);
        m_searchInput->setPlaceholderText(QStringLiteral("Pesquisar nesta pasta"));
        m_searchInput->setAccessibleName(QStringLiteral("Pesquisar arquivos"));
    } else {
        m_topLayout->insertWidget(0, m_ribbonInputRow);
    }
    m_ribbonInputRow->show();
}

void DolphinSearchBox::syncRibbonInput(const QUrl &location, bool searching)
{
    if (!searching) {
        const QSignalBlocker blocker(m_searchInput);
        m_searchInput->clear();
        m_saveSearchAction->setEnabled(false);
        m_searchPath = QUrl();
        setSearchPath(location);
    }
    m_ribbonCloseButton->setVisible(searching);
}

void DolphinSearchBox::saveSettings()''')
replace('src/dolphinviewcontainer.cpp',
        '        } else if (modifiers & Qt::ShiftModifier) {\n            Dolphin::openNewWindow({KFilePlacesModel::convertedUrl(url)}, this);',
        '        } else if ((modifiers & Qt::ShiftModifier) || GeneralSettings::linuxBrOpenFoldersInNewWindow()) {\n'
        '            Dolphin::openNewWindow({KFilePlacesModel::convertedUrl(url)}, this);')

replace('src/views/dolphinview.h', '#include <memory>', '#include <memory>\n#include <optional>')
replace('src/views/dolphinview.h', '    bool hiddenFilesShown() const;',
        '    bool hiddenFilesShown() const;\n    void resetLinuxBrFolderVisibility();')
replace('src/views/dolphinview.h', '    QUrl m_url;',
        '    QUrl m_url;\n    std::optional<bool> m_linuxbrHiddenOverride;')
replace('src/views/dolphinview.cpp', '''    ViewProperties props(viewPropertiesUrl());
    props.setHiddenFilesShown(show);

    m_model->setShowHiddenFiles(show);''', '''    m_linuxbrHiddenOverride = show;
    m_model->setLinuxBrFolderVisibility(show, GeneralSettings::linuxBrHideSystemFiles());
    m_model->setShowHiddenFiles(show);''')
replace('src/views/dolphinview.cpp', 'bool DolphinView::hiddenFilesShown() const', '''void DolphinView::resetLinuxBrFolderVisibility()
{
    GeneralSettings::self()->load();
    m_linuxbrHiddenOverride.reset();
    if (!m_url.isEmpty()) {
        m_model->clear();
        applyViewProperties();
        loadDirectory(m_url, true);
    }
}

bool DolphinView::hiddenFilesShown() const''')
replace('src/views/dolphinview.cpp', '    m_url = url;',
        '    m_url = url;\n    m_linuxbrHiddenOverride.reset();')
replace('src/views/dolphinview.cpp', '    const bool hiddenFilesShown = props.hiddenFilesShown();', '''    const bool hiddenFilesShown = m_linuxbrHiddenOverride.value_or(GeneralSettings::linuxBrShowHiddenFiles());
    m_model->setLinuxBrFolderVisibility(hiddenFilesShown, GeneralSettings::linuxBrHideSystemFiles());''')
replace('src/settings/viewpropertiesdialog.cpp', '    m_showHiddenFiles->setChecked(m_viewProps->hiddenFilesShown());',
        '    m_showHiddenFiles->setChecked(m_dolphinView->hiddenFilesShown());')
replace('src/settings/viewpropertiesdialog.cpp', '    m_dolphinView->setHiddenFilesShown(m_viewProps->hiddenFilesShown());',
        '    m_dolphinView->setHiddenFilesShown(m_showHiddenFiles->isChecked());')

replace('src/kitemviews/kfileitemmodel.h', '    void setShowHiddenFiles(bool show);',
        '    void setShowHiddenFiles(bool show);\n    void setLinuxBrFolderVisibility(bool showHidden, bool hideSystem);')
replace('src/kitemviews/kfileitemmodel.cpp', 'bool KFileItemModel::showHiddenFiles() const', '''void KFileItemModel::setLinuxBrFolderVisibility(bool showHidden, bool hideSystem)
{
    if (m_filter.setLinuxBrFolderVisibility(showHidden, hideSystem)) {
        applyFilters();
    }
}

bool KFileItemModel::showHiddenFiles() const''')
replace('src/kitemviews/private/kfileitemmodelfilter.h', '    bool hasSetFilters() const;',
        '    bool hasSetFilters() const;\n    bool setLinuxBrFolderVisibility(bool showHidden, bool hideSystem);')
replace('src/kitemviews/private/kfileitemmodelfilter.h', '    QString m_pattern;',
        '    bool m_linuxbrShowHidden = true;\n    bool m_linuxbrHideSystem = false;\n    QString m_pattern;')
replace('src/kitemviews/private/kfileitemmodelfilter.cpp', '#include "kfileitemmodelfilter.h"',
        '#include "kfileitemmodelfilter.h"\n#include "linuxbr-folder-visibility.h"')
replace('src/kitemviews/private/kfileitemmodelfilter.cpp', 'bool KFileItemModelFilter::hasSetFilters() const', '''bool KFileItemModelFilter::setLinuxBrFolderVisibility(bool showHidden, bool hideSystem)
{
    if (m_linuxbrShowHidden == showHidden && m_linuxbrHideSystem == hideSystem) {
        return false;
    }
    m_linuxbrShowHidden = showHidden;
    m_linuxbrHideSystem = hideSystem;
    return true;
}

bool KFileItemModelFilter::hasSetFilters() const''')
replace('src/kitemviews/private/kfileitemmodelfilter.cpp',
        '    return (!m_pattern.isEmpty() || !m_mimeTypes.isEmpty() || !m_excludeMimeTypes.isEmpty());',
        '    return !m_linuxbrShowHidden || m_linuxbrHideSystem || !m_pattern.isEmpty() || !m_mimeTypes.isEmpty() || !m_excludeMimeTypes.isEmpty();')
replace('src/kitemviews/private/kfileitemmodelfilter.cpp', '    const bool hasPatternFilter = !m_pattern.isEmpty();', '''    if ((!m_linuxbrShowHidden || m_linuxbrHideSystem) && item.url().isLocalFile()
        && !LinuxBRFolderVisibility::showLocalItem(item.localPath(), m_linuxbrShowHidden, m_linuxbrHideSystem)) {
        return false;
    }
    const bool hasPatternFilter = !m_pattern.isEmpty();''')

# User-facing application name; preserve desktop ID, executable and KDE credits.
replace('src/main.cpp', '                         i18n("Dolphin"),', '                         QStringLiteral("Explorador de arquivos"),')
path = root / 'src/org.kde.dolphin.desktop'
lines = path.read_text().splitlines()
section = ''
for index, line in enumerate(lines):
    if line.startswith('['): section = line
    if section == '[Desktop Entry]' and (line.startswith('Name=') or line.startswith('Name[') or line.startswith('GenericName=') or line.startswith('GenericName[')):
        lines[index] = line.split('=', 1)[0] + '=Explorador de arquivos'
path.write_text('\n'.join(lines) + '\n')
