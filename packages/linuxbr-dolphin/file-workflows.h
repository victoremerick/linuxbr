// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <KConfigGroup>
#include <KSharedConfig>
#include <KUrlNavigator>
#include <QDataStream>
#include <QDir>
#include <QFileInfo>
#include <QHash>
#include <QStorageInfo>
#include <QRegularExpression>
#include <QSet>

namespace LinuxBRFileWorkflows
{
inline QUrl normalizedFolder(QUrl url)
{
    if (url.isLocalFile()) {
        const QFileInfo path(url.toLocalFile());
        const QString canonical = path.canonicalFilePath();
        return QUrl::fromLocalFile(canonical.isEmpty() ? path.absoluteFilePath() : canonical);
    }
    return url.adjusted(QUrl::RemoveUserInfo | QUrl::RemoveQuery | QUrl::RemoveFragment | QUrl::StripTrailingSlash);
}

inline KConfigGroup privacy()
{
    return KConfigGroup(KSharedConfig::openConfig(QStringLiteral("dolphinrc")), QStringLiteral("LinuxBRPreviewPrivacy"));
}

inline bool blockedPreview(const QUrl &url)
{
    const QUrl folder = normalizedFolder(url);
    const auto entries = privacy().readEntry("Folders", QStringList());
    if (!entries.isEmpty() && (url.scheme() == QLatin1String("filenamesearch")
        || url.scheme() == QLatin1String("baloosearch") || url.scheme() == QLatin1String("tags"))) {
        return true;
    }
    for (const QString &entry : entries) {
        const QUrl root(entry);
        if (root == folder || root.isParentOf(folder)) {
            return true;
        }
    }
    return false;
}

inline bool ownPreviewBlock(const QUrl &url)
{
    return privacy().readEntry("Folders", QStringList()).contains(normalizedFolder(url).toString(QUrl::FullyEncoded));
}

inline void togglePreviewBlock(const QUrl &url)
{
    const QString folder = normalizedFolder(url).toString(QUrl::FullyEncoded);
    auto preferences = privacy();
    auto entries = preferences.readEntry("Folders", QStringList());
    if (!entries.removeOne(folder)) {
        entries.append(folder);
    }
    preferences.writeEntry("Folders", entries, KConfigBase::Notify);
    preferences.sync();
}

inline QString windowsNameKey(QString name)
{
    while (name.endsWith(QLatin1Char('.')) || name.endsWith(QLatin1Char(' '))) {
        name.chop(1);
    }
    return name.normalized(QString::NormalizationForm_C).toCaseFolded();
}

inline bool windowsFileSystem(const QUrl &folder)
{
    if (folder.scheme() == QLatin1String("smb")) {
        return true;
    }
    if (!folder.isLocalFile()) {
        return false;
    }
    const QByteArray type = QStorageInfo(folder.toLocalFile()).fileSystemType().toLower();
    return type == "ntfs" || type == "ntfs3" || type == "fuseblk" || type == "vfat" || type == "msdos"
        || type == "exfat" || type == "cifs" || type == "smb3";
}

inline QStringList incompatibleNames(const QList<QUrl> &items, const QUrl &folder)
{
    if (!windowsFileSystem(folder)) {
        return {};
    }
    static const QRegularExpression forbidden(QStringLiteral("[<>:\"/\\\\|?*\\x00-\\x1f]|[. ]$"));
    static const QRegularExpression device(QStringLiteral("^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])($|\\.)"));
    QHash<QString, QString> existing;
    if (folder.isLocalFile()) {
        for (const QString &name : QDir(folder.toLocalFile()).entryList(QDir::AllEntries | QDir::Hidden | QDir::System | QDir::NoDotAndDotDot)) {
            existing.insert(windowsNameKey(name), name);
        }
    }
    QStringList conflicts;
    for (const QUrl &item : items) {
        const QString name = item.fileName();
        const QString key = windowsNameKey(name);
        if (name.isEmpty() || forbidden.match(name).hasMatch() || device.match(key).hasMatch()
            || (existing.contains(key) && existing.value(key) != name)) {
            conflicts.append(name);
        }
        existing.insert(key, name);
    }
    conflicts.removeDuplicates();
    return conflicts;
}

inline QList<QUrl> history(const KUrlNavigator *navigator)
{
    QList<QUrl> locations;
    for (int index = navigator->historySize() - 1; index >= 0; --index) {
        locations.append(navigator->locationUrl(index));
    }
    return locations;
}

inline void restoreHistory(const QList<QUrl> &locations, int position, KUrlNavigator *navigator)
{
    if (position < 0 || position >= locations.size()) {
        return;
    }
    for (const auto &location : locations) {
        navigator->setLocationUrl(location);
    }
    for (int index = 0; index < position; ++index) {
        navigator->goBack();
    }
}
}
