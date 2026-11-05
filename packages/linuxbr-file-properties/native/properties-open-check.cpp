// SPDX-License-Identifier: GPL-3.0-or-later
#include <KPropertiesDialog>
#include <QApplication>
#include <QUrl>
#include <cstdio>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QApplication::setDesktopFileName(QStringLiteral("org.kde.dolphin"));
    if (argc < 2) {
        std::fputs("Uso: properties-open-check URL [URL...]\n", stderr);
        return 2;
    }
    QList<QUrl> urls;
    for (int index = 1; index < argc; ++index) {
        const QUrl url = QUrl::fromUserInput(QString::fromLocal8Bit(argv[index]), QString(), QUrl::AssumeLocalFile);
        if (!url.isValid() || url.isEmpty()) return 2;
        urls.append(url);
    }
    auto *dialog = new KPropertiesDialog(urls);
    dialog->resize(1000, 650);
    dialog->show();
    return app.exec();
}
