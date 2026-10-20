// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLockFile>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUrl>
#include <algorithm>
#include <functional>

namespace LinuxBRNavigation {
inline QString cleanUrl(const QUrl &url) {
    static const QStringList schemes = {"file", "linuxbr", "smb", "sftp", "ftp", "network", "remote", "zeroconf", "nfs", "mtp", "afp", "webdav", "webdavs"};
    if (!url.isValid() || !schemes.contains(url.scheme())) return {};
    return url.adjusted(QUrl::RemoveUserInfo | QUrl::RemoveQuery | QUrl::RemoveFragment | QUrl::NormalizePathSegments | QUrl::StripTrailingSlash).toString();
}
class State {
    QString path;
public:
    explicit State(QString file = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + "/linuxbr/sidebar.json") : path(std::move(file)) {}
    QJsonObject read() const {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly)) return {};
        return QJsonDocument::fromJson(file.readAll()).object();
    }
    bool edit(const std::function<void(QJsonObject &)> &change) {
        QDir().mkpath(QFileInfo(path).absolutePath());
        QLockFile lock(path + ".lock");
        if (!lock.tryLock(50)) return false;
        auto state = read(); change(state);
        QSaveFile file(path);
        if (!file.open(QIODevice::WriteOnly)) return false;
        file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
        const QByteArray bytes = QJsonDocument(state).toJson();
        return file.write(bytes) == bytes.size() && file.commit();
    }
    static int limit(const QJsonObject &state) { return qBound(3, state["limit"].toInt(3), 5); }
    void seed() {
        if (read().contains("favorites")) return;
        edit([](QJsonObject &s) {
            if (s.contains("favorites")) return;
            QJsonArray favorites;
            const QList<QPair<QStandardPaths::StandardLocation, QString>> defaults = {
                {QStandardPaths::HomeLocation, "Pasta pessoal"}, {QStandardPaths::DocumentsLocation, "Documentos"},
                {QStandardPaths::DownloadLocation, "Downloads"}, {QStandardPaths::PicturesLocation, "Imagens"},
                {QStandardPaths::MoviesLocation, "Vídeos"}, {QStandardPaths::MusicLocation, "Músicas"}};
            for (const auto &entry : defaults) {
                const QString path = QStandardPaths::writableLocation(entry.first);
                if (!path.isEmpty()) favorites.append(QJsonObject{{"url", cleanUrl(QUrl::fromLocalFile(path))}, {"name", entry.second}});
            }
            s["favorites"] = favorites;
        });
    }
    bool favorite(const QUrl &url, const QString &label, bool remove = false) {
        const QString key = cleanUrl(url);
        if (key.isEmpty()) return false;
        return edit([&](QJsonObject &s) {
            QJsonArray entries;
            for (const auto &value : s["favorites"].toArray())
                if (value.toObject()["url"].toString() != key) entries.append(value);
            if (!remove) entries.append(QJsonObject{{"url",key},{"name",label.trimmed().left(120)}});
            s["favorites"] = entries;
        });
    }
    bool visit(const QUrl &url, qint64 now = QDateTime::currentSecsSinceEpoch()) {
        const QString key = cleanUrl(url);
        if (key.isEmpty() || url.scheme() == "linuxbr" || url.scheme() == "network" || url.scheme() == "remote") return false;
        return edit([&](QJsonObject &s) {
            QJsonObject history;
            const auto old = s["history"].toObject();
            for (auto it = old.begin(); it != old.end(); ++it) {
                QJsonArray recent;
                for (const auto &t : it.value().toArray())
                    if (t.toInteger() > now - 30*86400 && t.toInteger() <= now) recent.append(t);
                if (!recent.isEmpty()) history[it.key()] = recent;
            }
            QJsonArray visits = history[key].toArray();
            if (visits.isEmpty() || now - visits.last().toInteger() >= 60) visits.append(now);
            while (visits.size() > 256) visits.removeAt(0);
            history[key] = visits;
            // Bound storage by retaining the 200 most recently visited locations.
            QStringList keys = history.keys();
            std::sort(keys.begin(), keys.end(), [&](const QString &a, const QString &b) {
                return history[a].toArray().last().toInteger() > history[b].toArray().last().toInteger();
            });
            for (int i=200; i<keys.size(); ++i) history.remove(keys[i]);
            s["history"] = history;
        });
    }
    static QStringList frequent(const QJsonObject &s, qint64 now = QDateTime::currentSecsSinceEpoch()) {
        QList<QPair<QString, QPair<int,qint64>>> ranks;
        const auto history = s["history"].toObject();
        for (auto it=history.begin(); it!=history.end(); ++it) {
            int count=0; qint64 last=0;
            for (const auto &v : it.value().toArray()) if (v.toInteger()>now-30*86400 && v.toInteger()<=now) { ++count; last=qMax(last,v.toInteger()); }
            if (count && !cleanUrl(QUrl(it.key())).isEmpty()) ranks.append({it.key(), {count,last}});
        }
        std::sort(ranks.begin(), ranks.end(), [](const auto &a, const auto &b) { return a.second != b.second ? a.second > b.second : a.first < b.first; });
        QStringList result;
        for (const auto &entry : ranks) { if (result.size()==limit(s)) break; result.append(entry.first); }
        return result;
    }
};
}
