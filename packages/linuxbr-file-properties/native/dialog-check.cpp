// SPDX-License-Identifier: GPL-3.0-or-later
#include <KFileItem>
#include <KPageWidget>
#include <KPageWidgetModel>
#include <KPropertiesDialog>
#include <KPropertiesDialogPlugin>
#include <QApplication>
#include <QClipboard>
#include <QComboBox>
#include <QFile>
#include <QDir>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLineEdit>
#include <QLabel>
#include <QPushButton>
#include <QPixmap>
#include <QTemporaryDir>
#include <QTimer>
#include <cstdio>
#include <memory>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QTemporaryDir directory;
    const QString filename = directory.filePath(QStringLiteral("acentos ação.txt"));
    QFile file(filename);
    if (!file.open(QIODevice::WriteOnly) || file.write("abc") != 3) return 10;
    file.close();
    auto *dialog = new KPropertiesDialog(QUrl::fromLocalFile(filename));
    dialog->show();
    int code = 1;
    QTimer::singleShot(400, &app, [&]() {
        const bool validation = dialog->findChild<QWidget *>(QStringLiteral("linuxbr-validation"));
        const bool location = dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-real-path"));
        auto *familiarField = dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-familiar-location"));
        const bool familiar = familiarField && familiarField->isReadOnly();
        const bool versions = dialog->findChild<QWidget *>(QStringLiteral("linuxbr-previous-versions"));
        QJsonArray names;
        auto *pages = dialog->findChild<KPageWidget *>();
        auto *model = pages ? qobject_cast<KPageWidgetModel *>(pages->model()) : nullptr;
        if (model) {
            for (int row = 0; row < model->rowCount(); ++row) names.append(model->item(model->index(row, 0))->name());
            const QString screenshots = qEnvironmentVariable("LINUXBR_PROPERTIES_SCREENSHOTS");
            if (!screenshots.isEmpty() && QDir::isAbsolutePath(screenshots) && QDir().mkpath(screenshots)) {
                dialog->resize(1000, 650);
                for (int row = 0; row < model->rowCount(); ++row) {
                    dialog->setCurrentPage(model->item(model->index(row, 0)));
                    QApplication::processEvents();
                    dialog->grab().save(QDir(screenshots).filePath(QStringLiteral("propriedades-%1.png").arg(row + 1)));
                }
                dialog->setCurrentPage(model->item(model->index(0, 0)));
            }
        }
        QJsonObject result{{QStringLiteral("validation"), validation}, {QStringLiteral("location"), location},
                           {QStringLiteral("familiarReadOnly"), familiar},
                           {QStringLiteral("versions"), versions}, {QStringLiteral("pages"), names},
                           {QStringLiteral("applyApi"), dialog->metaObject()->indexOfMethod("apply()") >= 0}};
        std::puts(QJsonDocument(result).toJson(QJsonDocument::Compact).constData());
        if (!(validation && location && familiar && versions)) {
            code = 1;
            dialog->reject();
            app.quit();
            return;
        }
        auto *start = dialog->findChild<QPushButton *>(QStringLiteral("linuxbr-hash-start"));
        start->click();
        auto *poll = new QTimer(&app);
        poll->setInterval(50);
        auto hashStage = std::make_shared<int>(0);
        QObject::connect(poll, &QTimer::timeout, &app, [&, poll, hashStage]() {
            const auto *result = dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-hash"));
            const QString sha256 = QStringLiteral("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
            const QString sha512 = QStringLiteral("ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f");
            if (result && result->text() == (*hashStage == 0 ? sha256 : sha512)) {
                if (*hashStage == 0) {
                    auto *reference = dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-hash-reference"));
                    auto *status = dialog->findChild<QLabel *>(QStringLiteral("linuxbr-hash-status"));
                    reference->setText(QString(64, QLatin1Char('0')));
                    if (!status->text().startsWith(QStringLiteral("Não corresponde"))) {
                        code = 7;
                        app.quit();
                        return;
                    }
                    reference->setText(sha256.toUpper());
                    if (!status->text().startsWith(QStringLiteral("Corresponde"))) {
                        code = 8;
                        app.quit();
                        return;
                    }
                    reference->clear();
                    *hashStage = 1;
                    dialog->findChild<QComboBox *>(QStringLiteral("linuxbr-hash-algorithm"))->setCurrentIndex(1);
                    dialog->findChild<QPushButton *>(QStringLiteral("linuxbr-hash-start"))->click();
                    return;
                }
                poll->stop();
                std::puts("native-dialog-sha256-sha512-reference-match-mismatch: ok");
                auto *familiar = dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-familiar-location"));
                if (!familiar || familiar->text().isEmpty() || familiar->cursorPosition() != 0) {
                    code = 9;
                    app.quit();
                    return;
                }
                familiar->selectAll();
                familiar->copy();
                if (QApplication::clipboard()->text() != familiar->text()) {
                    code = 11;
                    app.quit();
                    return;
                }
                familiar->deselect();
                familiar->setCursorPosition(0);
                std::puts("native-dialog-familiar-location: read-only, initial position and copy: ok");
                if (dialog->metaObject()->indexOfMethod("apply()") < 0) {
                    code = qEnvironmentVariableIsSet("LINUXBR_REQUIRE_APPLY") ? 2 : 0;
                    std::puts("native-dialog-apply: unavailable in this KIO build");
                    dialog->reject();
                    app.quit();
                    return;
                }
                auto applied = std::make_shared<int>(0);
                QObject::connect(dialog, &KPropertiesDialog::applied, &app, [&, applied]() {
                    ++*applied;
                    auto *name = dialog->findChild<QLineEdit *>(QStringLiteral("fileNameLineEdit"));
                    if (!dialog->isVisible() || !name) {
                        code = 3;
                        app.quit();
                        return;
                    }
                    if (*applied == 1) {
                        name->setText(QStringLiteral("renomeado ação.txt"));
                    } else if (*applied == 2) {
                        if (!QFile::exists(directory.filePath(QStringLiteral("renomeado ação.txt")))
                            || !dialog->windowTitle().contains(QStringLiteral("renomeado ação.txt"))
                            || dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-real-path"))->text() != directory.filePath(QStringLiteral("renomeado ação.txt"))) {
                            code = 4;
                            app.quit();
                            return;
                        }
                        name->setText(QStringLiteral("segunda ação.txt"));
                    } else if (*applied == 3) {
                        if (!QFile::exists(directory.filePath(QStringLiteral("segunda ação.txt")))
                            || !dialog->windowTitle().contains(QStringLiteral("segunda ação.txt"))
                            || dialog->findChild<QLineEdit *>(QStringLiteral("linuxbr-real-path"))->text() != directory.filePath(QStringLiteral("segunda ação.txt"))) {
                            code = 5;
                            app.quit();
                            return;
                        }
                        for (auto *plugin : dialog->findChildren<KPropertiesDialogPlugin *>()) {
                            if (QString::fromLatin1(plugin->metaObject()->className()).endsWith(QStringLiteral("KFilePermissionsPropsPlugin"))) plugin->setDirty(true);
                        }
                    } else {
                        code = *applied == 4 ? 0 : 6;
                        std::puts("native-dialog-apply: four applications, two renames, permissions unchanged, same window: ok");
                        dialog->reject();
                        app.quit();
                        return;
                    }
                    QTimer::singleShot(0, dialog, [dialog]() { QMetaObject::invokeMethod(dialog, "apply", Qt::DirectConnection); });
                });
                QMetaObject::invokeMethod(dialog, "apply", Qt::DirectConnection);
            }
        });
        poll->start();
    });
    QTimer::singleShot(10000, &app, &QApplication::quit);
    app.exec();
    return code;
}
