// SPDX-License-Identifier: GPL-3.0-or-later
#include <KPropertiesDialog>
#include <QApplication>
#include <QCheckBox>
#include <QDir>
#include <QLabel>
#include <QTemporaryDir>
#include <QTimer>
#include <cstdio>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QTemporaryDir directory;
    QDir root(directory.path());
    if (!root.mkdir(QStringLiteral("primeira")) || !root.mkdir(QStringLiteral("segunda"))) return 10;
    QList<QUrl> selection{QUrl::fromLocalFile(directory.filePath(QStringLiteral("primeira"))),
                          QUrl::fromLocalFile(directory.filePath(QStringLiteral("segunda")))};
    auto *dialog = new KPropertiesDialog(selection);
    dialog->show();
    int code = 1;
    QTimer::singleShot(400, &app, [&]() {
        if (dialog->metaObject()->indexOfMethod("apply()") < 0) {
            code = qEnvironmentVariableIsSet("LINUXBR_REQUIRE_APPLY") ? 2 : 0;
            std::puts("native-dialog-multiple: opt-in unavailable in this KIO build");
        } else {
            auto *explanation = dialog->findChild<QLabel *>(QStringLiteral("linuxbr-multiple-security"));
            bool recursiveDisabled = false;
            if (explanation) {
                for (auto *check : explanation->parentWidget()->findChildren<QCheckBox *>(QString(), Qt::FindDirectChildrenOnly)) {
                    recursiveDisabled = !check->isChecked() && !check->isEnabled();
                }
            }
            const bool firstItemPagesAbsent = !dialog->findChild<QWidget *>(QStringLiteral("linuxbr-validation"))
                && !dialog->findChild<QWidget *>(QStringLiteral("linuxbr-location"))
                && !dialog->findChild<QWidget *>(QStringLiteral("linuxbr-compatibility"));
            code = explanation && recursiveDisabled && firstItemPagesAbsent && dialog->items().size() == 2 ? 0 : 3;
            std::printf("native-dialog-multiple: native selection preserved; recursion disabled; no first-item pages: %s\n", code ? "failed" : "ok");
        }
        dialog->reject();
        app.quit();
    });
    QTimer::singleShot(10000, &app, &QApplication::quit);
    app.exec();
    return code;
}
