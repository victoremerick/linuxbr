#include <KIO/WorkerBase>
#include <KIO/UDSEntry>
#include <QCoreApplication>
#include <QDBusInterface>
#include <QDBusReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QUrl>
#include <sys/stat.h>
class Metadata : public QObject {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.kde.kio.worker.linuxbr" FILE "worker.json")
};
class Drives : public KIO::WorkerBase {
public:
    Drives(const QByteArray &pool,const QByteArray &app):WorkerBase("linuxbr",pool,app){}
    KIO::WorkerResult stat(const QUrl &url) override {
        // No mounting on stat: merely displaying Places must never prompt polkit.
        if (!url.host().isEmpty() || url.hasQuery() || url.hasFragment()) return KIO::WorkerResult::fail(KIO::ERR_MALFORMED_URL,url.toString());
        auto parts=url.path().split('/',Qt::SkipEmptyParts);
        if (!parts.isEmpty() && (parts[0].size()!=1 || parts[0][0]<'C' || parts[0][0]>'Z')) return KIO::WorkerResult::fail(KIO::ERR_MALFORMED_URL,url.toString());
        KIO::UDSEntry e; e.fastInsert(KIO::UDSEntry::UDS_NAME,parts.isEmpty()?QStringLiteral("Este computador"):parts[0]);
        e.fastInsert(KIO::UDSEntry::UDS_FILE_TYPE,S_IFDIR); e.fastInsert(KIO::UDSEntry::UDS_ACCESS,0555);
        if(parts.isEmpty()) { e.fastInsert(KIO::UDSEntry::UDS_DISPLAY_NAME,QStringLiteral("Este computador")); e.fastInsert(KIO::UDSEntry::UDS_ICON_NAME,QStringLiteral("computer")); }
        statEntry(e); return KIO::WorkerResult::pass();
    }
    KIO::WorkerResult listDir(const QUrl &url) override {
        if (!url.host().isEmpty() || url.hasQuery() || url.hasFragment()) return KIO::WorkerResult::fail(KIO::ERR_MALFORMED_URL,url.toString());
        QDBusInterface service("org.linuxbr.DriveManager1","/org/linuxbr/DriveManager1","org.linuxbr.DriveManager1",QDBusConnection::sessionBus());
        service.setTimeout(150000);
        auto parts=url.path().split('/',Qt::SkipEmptyParts);
        if (parts.isEmpty()) {
            QDBusReply<QString> reply=service.call("GetState");
            if (!reply.isValid()) return KIO::WorkerResult::fail(KIO::ERR_CANNOT_CONNECT,reply.error().message());
            KIO::UDSEntry self;
            self.fastInsert(KIO::UDSEntry::UDS_NAME,QStringLiteral("."));
            self.fastInsert(KIO::UDSEntry::UDS_DISPLAY_NAME,QStringLiteral("Este computador"));
            self.fastInsert(KIO::UDSEntry::UDS_FILE_TYPE,S_IFDIR);
            self.fastInsert(KIO::UDSEntry::UDS_ACCESS,0555);
            self.fastInsert(KIO::UDSEntry::UDS_ICON_NAME,QStringLiteral("computer"));
            listEntry(self);
            auto state=QJsonDocument::fromJson(reply.value().toUtf8()).object();
            for(auto v:state["places"].toArray()) {
                auto o=v.toObject(); KIO::UDSEntry e;
                e.fastInsert(KIO::UDSEntry::UDS_NAME,QUrl(o["url"].toString()).path().mid(1));
                e.fastInsert(KIO::UDSEntry::UDS_DISPLAY_NAME,o["name"].toString());
                e.fastInsert(KIO::UDSEntry::UDS_FILE_TYPE,S_IFDIR);e.fastInsert(KIO::UDSEntry::UDS_ACCESS,0555);
                e.fastInsert(KIO::UDSEntry::UDS_ICON_NAME,o["icon"].toString());
                e.fastInsert(KIO::UDSEntry::UDS_EXTRA, QString::fromUtf8(QJsonDocument(o["card"].toObject()).toJson(QJsonDocument::Compact)));
                e.fastInsert(KIO::UDSEntry::UDS_MIME_TYPE,QStringLiteral("inode/directory"));
                e.fastInsert(KIO::UDSEntry::UDS_DISPLAY_TYPE,o["group"].toString());listEntry(e);
            }
            return KIO::WorkerResult::pass();
        }
        if(parts[0].size()!=1 || parts[0][0]<'C' || parts[0][0]>'Z' || parts.contains("..")) return KIO::WorkerResult::fail(KIO::ERR_MALFORMED_URL,url.toString());
        QDBusReply<QString> reply=service.call("Resolve",parts.takeFirst());
        if (!reply.isValid()) return KIO::WorkerResult::fail(KIO::ERR_CANNOT_MOUNT,reply.error().message());
        QUrl target(reply.value());
        if(target.scheme()!="file" && target.scheme()!="smb") return KIO::WorkerResult::fail(KIO::ERR_MALFORMED_URL,target.toString());
        if(!parts.isEmpty()) target.setPath(target.path()+ (target.path().endsWith('/')?"":"/") + parts.join('/'));
        redirection(target);return KIO::WorkerResult::pass();
    }
};
extern "C" int Q_DECL_EXPORT kdemain(int argc,char **argv) {
    QCoreApplication app(argc,argv);
    if(argc!=4) return 2;
    Drives worker(argv[2],argv[3]);worker.dispatchLoop();return 0;
}
#include "worker.moc"
