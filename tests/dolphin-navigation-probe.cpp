// Run against the patched Dolphin and the fixture session service, in a container.
#include "kitemviews/kfileitemmodel.h"
#include <QApplication>
#include <QEventLoop>
#include <QTimer>
#include <iostream>
int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    KFileItemModel model;
    model.setShowDirectoriesOnly(true);
    model.setRoles({"text", "isDir", "isExpanded", "isExpandable", "expandedParentsCount"});
    model.setGroupedSorting(true);
    model.setSortRole("type");
    QEventLoop loop;
    QObject::connect(&model, &KFileItemModel::directoryLoadingCompleted, &loop, &QEventLoop::quit);
    QTimer::singleShot(15000, &loop, &QEventLoop::quit);
    model.loadDirectory(QUrl("linuxbr:/"));
    loop.exec();
    QStringList letters;
    for (int i = 0; i < model.count(); ++i) letters << model.fileItem(i).url().path();
    if (letters != QStringList({"/C", "/D", "/E", "/Z"})) {
        std::cerr << "Unexpected order: " << letters.join(",").toStdString() << '\n';
        return 1;
    }
    // The sidebar uses name sorting; aliases must retain letter order there too.
    model.setSortRole("text");
    QEventLoop settle;
    QTimer::singleShot(500, &settle, &QEventLoop::quit);
    settle.exec();
    for (int i = 0; i < letters.size(); ++i)
        if (model.fileItem(i).url().path() != letters[i]) return 2;
    if (!model.setExpanded(0, true)) return 3;
    QEventLoop expanded;
    QObject::connect(&model, &KFileItemModel::directoryLoadingCompleted, &expanded, &QEventLoop::quit);
    QTimer::singleShot(10000, &expanded, &QEventLoop::quit);
    expanded.exec();
    if (model.count() <= 4) { std::cerr << "Tree did not expand C"; return 4; }
    if (!model.setExpanded(0, false) || model.count() != 4) return 5;
    std::cout << "PASS: native Dolphin model orders grouped cards and tree by letter\n";
    return 0;
}
