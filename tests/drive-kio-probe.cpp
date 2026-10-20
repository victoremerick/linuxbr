#include <QUrl>
#include <KIO/ListJob>
#include <KIO/StatJob>
#include <QCoreApplication>
#include <QDebug>
int main(int argc,char**argv){
 QCoreApplication app(argc,argv);
 auto stat=KIO::stat(QUrl("linuxbr:/D"),KIO::HideProgressInfo);
 if(!stat->exec()){qWarning()<<stat->errorString();return 1;}
 bool rootFound=false;
 auto root=KIO::listDir(QUrl("linuxbr:/"),KIO::HideProgressInfo);
 QObject::connect(root,&KIO::ListJob::entries,[&](KIO::Job*,const KIO::UDSEntryList &entries){
   for(const auto &entry:entries) if(entry.stringValue(KIO::UDSEntry::UDS_NAME)=="D") {
     rootFound=entry.stringValue(KIO::UDSEntry::UDS_DISPLAY_TYPE)=="Discos locais"
       && entry.stringValue(KIO::UDSEntry::UDS_ICON_NAME).endsWith("disk-060.svg")
       && entry.stringValue(KIO::UDSEntry::UDS_DISPLAY_NAME).contains("40.0 GiB livres")
       && entry.stringValue(KIO::UDSEntry::UDS_EXTRA).contains("capacityText");
   }
 });
 if(!root->exec() || !rootFound)return 4;
 bool found=false;
 auto job=KIO::listDir(QUrl("linuxbr:/D"),KIO::HideProgressInfo);
 QObject::connect(job,&KIO::ListJob::entries,[&](KIO::Job*,const KIO::UDSEntryList &entries){
   for(const auto &entry:entries) if(entry.stringValue(KIO::UDSEntry::UDS_NAME)=="sentinel")found=true;
 });
 if(!job->exec()){qWarning()<<job->errorString();return 2;}
 if(!found)return 3;
 qInfo()<<"PASS: KIO loads linuxbr worker and redirects to native filesystem";
}
