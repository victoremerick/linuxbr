// Manage only Linux BR-owned places through KDE's bookmark API.
#include <KBookmarkManager>
#include <KBookmark>
#include <QCoreApplication>
#include <QStandardPaths>
#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QLockFile>
#include <QSet>
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QFile input; input.open(stdin, QIODevice::ReadOnly);
    QJsonParseError error;
    const auto doc = QJsonDocument::fromJson(input.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !doc.isArray()) return 2;
    QMap<QString,QJsonObject> desired;
    for (auto value : doc.array()) {
        auto o = value.toObject(); auto key = o["key"].toString();
        auto url = QUrl(o["url"].toString());
        if (key.isEmpty() || url.scheme() != "linuxbr" || o["name"].toString().isEmpty()) return 2;
        desired.insert(key,o);
    }
    const auto dir = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation);
    QDir().mkpath(dir);
    // Seed only missing view settings. Never overwrite a user's Dolphin view.
    const auto viewDir=dir + "/dolphin/view_properties/linuxbr-computer";
    const auto viewPath=viewDir + "/.directory";
    if (!QFile::exists(viewPath)) {
        QDir().mkpath(viewDir);
        QFile::copy("/usr/share/linuxbr/dolphin-computer.directory",viewPath);
    }
    const auto path = dir + "/user-places.xbel";
    QLockFile lock(path + ".linuxbr-lock");
    if (!lock.tryLock(3000)) return 75;
    QFile file(path); QByteArray before;
    if (file.exists()) {
        if (!file.open(QIODevice::ReadOnly)) return 3;
        before = file.readAll(); file.close();
        QDomDocument xml;
        if (!xml.setContent(before) || xml.documentElement().tagName() != "xbel") return 4;
        // Preserve a one-time backup of the user's original bookmarks.
        if (!QFile::exists(path + ".before-linuxbr")) {
            if (!QFile::copy(path, path + ".before-linuxbr")) return 3;
        }
    }
    KBookmarkManager manager(path);
    auto root = manager.root(); bool changed = false;
    QSet<QString> seen;
    for (auto b = root.first(); !b.isNull();) {
        auto next = root.next(b);
        const auto key = b.metaDataItem("LinuxBRDriveKey");
        if (!key.isEmpty()) {
            if (!desired.contains(key) || seen.contains(key)) { root.deleteBookmark(b); changed = true; }
            else {
                auto o=desired[key]; seen.insert(key);
                if (b.fullText()!=o["name"].toString() || b.url()!=QUrl(o["url"].toString()) || b.icon()!=o["icon"].toString()) {
                    b.setFullText(o["name"].toString()); b.setUrl(QUrl(o["url"].toString())); b.setIcon(o["icon"].toString()); changed=true;
                }
            }
        }
        b=next;
    }
    for (const auto value : doc.array()) {
        const auto o=value.toObject();
        const auto key=o["key"].toString();
        if (seen.contains(key)) continue;
        seen.insert(key);
        auto b=root.addBookmark(o["name"].toString(), QUrl(o["url"].toString()), o["icon"].toString());
        b.setMetaDataItem("LinuxBRDriveKey", key);
        b.setMetaDataItem("ID", "linuxbr:" + key);
        changed=true;
    }
    if (changed) {
        root.internalElement().setAttribute("xmlns:bookmark", "http://www.freedesktop.org/standards/desktop-bookmarks");
        // Do not overwrite an edit made while this update was being prepared.
        QByteArray now;
        if (file.exists()) { if (!file.open(QIODevice::ReadOnly)) return 3; now=file.readAll(); file.close(); }
        if (now!=before) return 75;
        bool failed=false;
        QObject::connect(&manager,&KBookmarkManager::error,[&](const QString&){failed=true;});
        manager.emitChanged(root);
        if (failed) return 3;
    }
    return 0;
}
