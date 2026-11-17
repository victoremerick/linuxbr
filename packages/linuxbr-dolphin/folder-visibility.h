// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QFile>
#include <QStringView>
#include <QtEndian>

#ifdef Q_OS_LINUX
#include <sys/xattr.h>
#endif

namespace LinuxBRFolderVisibility
{
inline bool systemPath(QStringView path)
{
    constexpr QStringView systemPaths[] = {u"/bin", u"/boot", u"/dev", u"/etc", u"/lib", u"/lib32", u"/lib64",
                                           u"/libx32", u"/lost+found", u"/proc", u"/run", u"/sbin", u"/sys", u"/usr", u"/var",
                                           u"/initrd.img", u"/initrd.img.old", u"/vmlinuz", u"/vmlinuz.old"};
    for (const auto systemPath : systemPaths) {
        if (path == systemPath) {
            return true;
        }
    }
    return false;
}

inline quint32 dosAttributes(const QString &path)
{
#ifdef Q_OS_LINUX
    quint32 attributes = 0;
    const auto name = QFile::encodeName(path);
    if (lgetxattr(name.constData(), "system.ntfs_attrib_be", &attributes, sizeof(attributes)) == sizeof(attributes)) {
        return qFromBigEndian(attributes);
    }
#endif
    return 0;
}

inline bool showLocalItem(const QString &path, bool showHidden, bool hideSystem)
{
    if (systemPath(path)) {
        return !hideSystem;
    }
    const auto attributes = dosAttributes(path);
    if (attributes & 0x04) { // FILE_ATTRIBUTE_SYSTEM
        return !hideSystem;
    }
    return showHidden || !(attributes & 0x02); // FILE_ATTRIBUTE_HIDDEN
}
}
