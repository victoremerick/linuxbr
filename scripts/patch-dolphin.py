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
