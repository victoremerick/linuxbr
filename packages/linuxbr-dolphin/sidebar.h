// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "linuxbr-sidebar-state.h"
#include <KIO/ListJob>
#include <KIO/JobUiDelegateFactory>
#include <KJobWidgets>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QInputDialog>
#include <QMenu>
#include <QMessageBox>
#include <QPersistentModelIndex>
#include <QPointer>
#include <QTimer>
#include <QTreeWidget>
#include <QHeaderView>
#include <QApplication>
#include <sys/stat.h>
#include <memory>
#include <QSet>
#include <QMimeData>
#include <QDropEvent>
#include <QDragEnterEvent>
#include <QDragMoveEvent>
#include <KJobUiDelegate>

class LinuxBRSidebar : public QTreeWidget {
    enum { UrlRole=Qt::UserRole, KindRole, LoadedRole, GenerationRole };
    LinuxBRNavigation::State state;
    QTreeWidgetItem *quick, *recent, *computer, *network;
    QList<QTreeWidgetItem *> drives;
    QUrl current;
    QByteArray lastState, lastDrives;
    bool querying=false;
    std::function<void(const QUrl &, bool)> navigate;
    static QString label(const QUrl &url) {
        if (url.isLocalFile() && url.path()=="/") return QStringLiteral("Sistema (C:)");
        return url.fileName().isEmpty() ? url.toDisplayString(QUrl::RemoveUserInfo) : url.fileName();
    }
    QTreeWidgetItem *add(QTreeWidgetItem *parent, const QString &title, const QString &icon, const QUrl &url={}, const QString &kind={}) {
        auto *item = parent ? new QTreeWidgetItem(parent) : new QTreeWidgetItem(this);
        item->setText(0,title); item->setIcon(0,QIcon::fromTheme(icon));
        item->setData(0,UrlRole,url); item->setData(0,KindRole,kind);
        item->setToolTip(0,url.isEmpty()?title:url.toDisplayString(QUrl::RemoveUserInfo));
        if (!url.isEmpty()) item->setChildIndicatorPolicy(QTreeWidgetItem::ShowIndicator);
        if (kind=="group") { auto font=item->font(0); font.setBold(true); item->setFont(0,font); }
        return item;
    }
    void clearChildren(QTreeWidgetItem *item) {
        // Persistent indexes invalidate callbacks for removed nodes, avoiding stale writes.
        qDeleteAll(item->takeChildren());
    }
    void message(QTreeWidgetItem *parent, const QString &text) {
        auto *item=add(parent,text,"dialog-information");
        item->setFlags(Qt::ItemIsEnabled);
    }
    void settingsChanged() {
        const auto data=state.read();
        const auto encoded=QJsonDocument(data).toJson(QJsonDocument::Compact) + QByteArray::number(QDateTime::currentSecsSinceEpoch()/60);
        if (encoded==lastState) return;
        lastState=encoded;
        // Only rebuild the favorites when they changed, preserving expanded trees.
        const auto favorites=QJsonDocument(QJsonObject{{"items",data["favorites"]}}).toJson();
        if (quick->data(0,LoadedRole).toByteArray()!=favorites) {
            clearChildren(quick); quick->setData(0,LoadedRole,favorites);
            for (const auto &value : data["favorites"].toArray()) {
                const auto entry=value.toObject(); QUrl url(entry["url"].toString());
                if (!LinuxBRNavigation::cleanUrl(url).isEmpty()) add(quick,entry["name"].toString(),"folder",url,"favorite");
            }
        }
        clearChildren(recent);
        for (const auto &value : LinuxBRNavigation::State::frequent(data)) add(recent,label(QUrl(value)),"folder",QUrl(value),"frequent");
        if (!recent->childCount()) message(recent,QStringLiteral("Os locais visitados aparecerão aqui"));
    }
    void load(QTreeWidgetItem *item, bool force=false) {
        const QUrl url=item->data(0,UrlRole).toUrl();
        const QString kind=item->data(0,KindRole).toString();
        if (url.isEmpty() || kind=="group" || (!force && item->data(0,LoadedRole).toBool())) return;
        item->setData(0,LoadedRole,true); clearChildren(item);
        message(item,QStringLiteral("Consultando…"));
        const QPersistentModelIndex index=indexFromItem(item);
        const int generation=item->data(0,GenerationRole).toInt()+1;
        item->setData(0,GenerationRole,generation);
        auto *job=KIO::listDir(url,KIO::HideProgressInfo,KIO::ListJob::ListFlags{});
        KJobWidgets::setWindow(job,this);
        job->setUiDelegate(KIO::createDefaultJobUiDelegate(KJobUiDelegate::AutoHandlingDisabled,this));
        auto first=std::make_shared<bool>(true);
        connect(job,&KIO::ListJob::entries,this,[this,index,first,generation](KIO::Job *job,const KIO::UDSEntryList &entries) {
            if (!index.isValid()) { job->kill(); return; }
            auto *parent=itemFromIndex(index);
            if (parent->data(0,GenerationRole).toInt()!=generation) return;
            if (*first) { clearChildren(parent); *first=false; }
            for (const auto &entry : entries) {
                const QString name=entry.stringValue(KIO::UDSEntry::UDS_NAME);
                if (name.isEmpty() || name.startsWith('.')) continue;
                QString target=entry.stringValue(KIO::UDSEntry::UDS_TARGET_URL);
                if (target.isEmpty()) target=entry.stringValue(KIO::UDSEntry::UDS_URL);
                if (entry.numberValue(KIO::UDSEntry::UDS_FILE_TYPE)!=S_IFDIR && target.isEmpty()) continue;
                QUrl child(target);
                if (target.isEmpty()) {
                    child=static_cast<KIO::ListJob *>(job)->url();
                    child.setPath(child.path()+(child.path().endsWith('/')?"":"/")+name);
                }
                if (LinuxBRNavigation::cleanUrl(child).isEmpty()) continue;
                const QString display=entry.stringValue(KIO::UDSEntry::UDS_DISPLAY_NAME);
                const QString icon=entry.stringValue(KIO::UDSEntry::UDS_ICON_NAME);
                add(parent,display.isEmpty()?name:display,icon.isEmpty()?"folder":icon,child,"directory");
            }
            parent->sortChildren(0,Qt::AscendingOrder);
        });
        connect(job,&KJob::result,this,[this,index,first,generation](KJob *result) {
            if (!index.isValid()) return;
            auto *parent=itemFromIndex(index);
            if (parent->data(0,GenerationRole).toInt()!=generation) return;
            if (*first) clearChildren(parent);
            if (result->error()) {
                parent->setData(0,LoadedRole,false);
                message(parent,QStringLiteral("Não foi possível listar. Clique direito para atualizar."));
                parent->setToolTip(0,result->errorString());
            } else if (!parent->childCount()) message(parent,QStringLiteral("Nenhum local encontrado"));
        });
    }
    void refreshDrives() {
        if (querying) return;
        querying=true;
        auto call=QDBusMessage::createMethodCall("org.linuxbr.DriveManager1","/org/linuxbr/DriveManager1","org.linuxbr.DriveManager1","GetState");
        auto *watcher=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(call,3000),this);
        connect(watcher,&QDBusPendingCallWatcher::finished,this,[this](QDBusPendingCallWatcher *watcher) {
            QDBusPendingReply<QString> reply=*watcher; watcher->deleteLater(); querying=false;
            if (reply.isError()) { computer->setToolTip(0,QStringLiteral("Serviço de unidades indisponível; tentando novamente…")); return; }
            applyDrives(QJsonDocument::fromJson(reply.value().toUtf8()).object()["places"].toArray());
        });
    }
    void contextMenu(const QPoint &position) {
        auto *item=itemAt(position);
        const QPersistentModelIndex selected=item ? indexFromItem(item) : QModelIndex();
        const QUrl selectedUrl=item ? item->data(0,UrlRole).toUrl() : QUrl();
        const QString selectedName=item ? item->text(0) : QString();
        QMenu menu(this);
        auto *pin=menu.addAction(QStringLiteral("Adicionar pasta atual ao Acesso rápido"));
        pin->setEnabled(!LinuxBRNavigation::cleanUrl(current).isEmpty());
        auto *custom=menu.addAction(QStringLiteral("Adicionar outro local ao Acesso rápido…"));
        QAction *remove=nullptr, *rename=nullptr, *refresh=nullptr;
        if (item && item->data(0,KindRole)=="favorite") {
            rename=menu.addAction(QStringLiteral("Renomear atalho…"));
            remove=menu.addAction(QStringLiteral("Remover do Acesso rápido"));
        }
        if (item && !item->data(0,UrlRole).toUrl().isEmpty() && item->data(0,KindRole)!="group") refresh=menu.addAction(QStringLiteral("Atualizar este local"));
        menu.addSeparator();
        auto *limits=menu.addMenu(QStringLiteral("Limite de Mais acessados"));
        for (int i=3;i<=5;++i) {
            auto *action=limits->addAction(QString::number(i)); action->setCheckable(true);
            action->setChecked(i==LinuxBRNavigation::State::limit(state.read()));
            connect(action,&QAction::triggered,this,[this,i] { state.edit([i](QJsonObject &s){s["limit"]=i;}); settingsChanged(); });
        }
        auto *clear=menu.addAction(QStringLiteral("Limpar histórico de Mais acessados"));
        auto *chosen=menu.exec(viewport()->mapToGlobal(position));
        if (!chosen) return;
        bool ok=true;
        if (chosen==pin) ok=state.favorite(current,label(current));
        else if (chosen==custom) {
            const QString text=QInputDialog::getText(this,QStringLiteral("Acesso rápido"),QStringLiteral("Caminho da pasta ou endereço de rede:"),QLineEdit::Normal,{},&ok);
            if (!ok || text.trimmed().isEmpty()) return;
            QUrl url=text.startsWith('/')?QUrl::fromLocalFile(text):QUrl(text);
            if (LinuxBRNavigation::cleanUrl(url).isEmpty()) { QMessageBox::information(this,QStringLiteral("Acesso rápido"),QStringLiteral("Informe um caminho absoluto ou um endereço como smb://servidor/pasta.")); return; }
            ok=state.favorite(url,label(url));
        } else if (chosen==remove) ok=state.favorite(selectedUrl,{},true);
        else if (chosen==rename) {
            const QString text=QInputDialog::getText(this,QStringLiteral("Renomear atalho"),QStringLiteral("Nome:"),QLineEdit::Normal,selectedName,&ok);
            if (!ok || text.trimmed().isEmpty()) return;
            ok=state.favorite(selectedUrl,text);
        } else if (chosen==refresh && selected.isValid()) load(itemFromIndex(selected),true);
        else if (chosen==clear) ok=state.edit([](QJsonObject &s){s.remove("history");});
        if (!ok) QMessageBox::warning(this,QStringLiteral("Navegação"),QStringLiteral("Não foi possível salvar a preferência. Tente novamente."));
        settingsChanged();
    }
protected:
    void dragEnterEvent(QDragEnterEvent *event) override {
        if (event->mimeData()->hasUrls() && event->possibleActions().testFlag(Qt::CopyAction)) { event->setDropAction(Qt::CopyAction); event->accept(); }
    }
    void dragMoveEvent(QDragMoveEvent *event) override {
        auto *item=itemAt(event->position().toPoint());
        if (item && (item==quick || item->parent()==quick) && event->possibleActions().testFlag(Qt::CopyAction)) { event->setDropAction(Qt::CopyAction); event->accept(); }
        else event->ignore();
    }
    void dropEvent(QDropEvent *event) override {
        auto *item=itemAt(event->position().toPoint());
        if (!item || (item!=quick && item->parent()!=quick) || !event->possibleActions().testFlag(Qt::CopyAction)) return;
        bool added=false;
        for (const QUrl &url : event->mimeData()->urls()) {
            if (url.isLocalFile() && !QFileInfo(url.toLocalFile()).isDir()) continue;
            if (state.favorite(url,label(url))) added=true;
        }
        if (added) { event->setDropAction(Qt::CopyAction); event->accept(); settingsChanged(); }
    }
public:
    explicit LinuxBRSidebar(QWidget *parent, std::function<void(const QUrl &,bool)> open) : QTreeWidget(parent), navigate(std::move(open)) {
        setObjectName("linuxbrSidebar"); setHeaderHidden(true); setColumnCount(1); setRootIsDecorated(true);
        setSelectionMode(QAbstractItemView::SingleSelection); setContextMenuPolicy(Qt::CustomContextMenu);
        setAcceptDrops(true); viewport()->setAcceptDrops(true); setDragDropMode(QAbstractItemView::DropOnly);
        setFrameShape(QFrame::NoFrame); setIconSize(QSize(18,18));
        setStyleSheet(QStringLiteral(
            "QTreeWidget#linuxbrSidebar { border: none; background: palette(window); }"
            "QTreeWidget#linuxbrSidebar::item { padding: 3px 4px; border-radius: 0; border-left: 2px solid transparent; }"
            "QTreeWidget#linuxbrSidebar::item:hover { background: palette(alternate-base); }"
            "QTreeWidget#linuxbrSidebar::item:selected { background: palette(highlight); color: palette(highlighted-text); border-left: 2px solid palette(highlight); }"));
        setMinimumWidth(260); setIndentation(16); setUniformRowHeights(true); header()->setStretchLastSection(true);
        quick=add(nullptr,QStringLiteral("Acesso rápido"),"bookmarks",{},"group");
        recent=add(nullptr,QStringLiteral("Mais acessados"),"document-open-recent",{},"group");
        computer=add(nullptr,QStringLiteral("Este computador"),"computer",QUrl("linuxbr:/"),"group");
        for (const auto &name : {QStringLiteral("Discos locais"),QStringLiteral("Dispositivos removíveis"),QStringLiteral("Unidades de rede")}) {
            auto *group=add(computer,name,"drive-harddisk",{},"group"); group->setExpanded(true); drives.append(group);
        }
        // C remains reachable even while the session service is starting.
        add(drives[0],QStringLiteral("Sistema (C:)"),"drive-harddisk",QUrl("linuxbr:/C"),"drive");
        network=add(nullptr,QStringLiteral("Locais de rede"),"network-workgroup",QUrl("remote:/"),"group");
        add(network,QStringLiteral("Computadores e compartilhamentos"),"network-workgroup",QUrl("smb:/"),"network");
        add(network,QStringLiteral("Dispositivos e serviços"),"network-server",QUrl("zeroconf:/"),"network");
        for (auto *group : {quick,recent,computer}) group->setExpanded(true);
        connect(this,&QTreeWidget::itemExpanded,this,[this](QTreeWidgetItem *item){load(item);});
        auto activate=[this](QTreeWidgetItem *item,int) {
            const QUrl url=item->data(0,UrlRole).toUrl();
            if (!url.isEmpty()) navigate(url,QApplication::keyboardModifiers().testFlag(Qt::ControlModifier));
        };
        connect(this,&QTreeWidget::itemClicked,this,activate);
        connect(this,&QTreeWidget::itemActivated,this,activate);
        connect(this,&QTreeWidget::customContextMenuRequested,this,&LinuxBRSidebar::contextMenu);
        state.seed(); settingsChanged(); refreshDrives();
        auto *timer=new QTimer(this); timer->setInterval(5000);
        connect(timer,&QTimer::timeout,this,[this]{ settingsChanged(); refreshDrives(); }); timer->start();
    }
    void recordVisit(const QUrl &url) { state.visit(url); settingsChanged(); }
    void setLocation(const QUrl &url) {
        current=url; settingsChanged();
        const QString wanted=LinuxBRNavigation::cleanUrl(url);
        QTreeWidgetItemIterator it(this);
        while (*it) { if (LinuxBRNavigation::cleanUrl((*it)->data(0,UrlRole).toUrl())==wanted && !wanted.isEmpty()) { setCurrentItem(*it); break; } ++it; }
    }
    void applyDrives(const QJsonArray &places) {
        // Usage changes do not rebuild the tree and collapse open directories.
        QJsonArray identity;
        for (const auto &v : places) {
            const auto p=v.toObject(); const auto card=p["card"].toObject();
            identity.append(QJsonObject{{"url",p["url"]},{"group",p["group"]},{"name",card["title"]},{"icon",card["icon"]},{"key",p["key"]}});
        }
        const auto encoded=QJsonDocument(identity).toJson(QJsonDocument::Compact);
        if (encoded==lastDrives || identity.isEmpty()) return;
        lastDrives=encoded; computer->setToolTip(0,QStringLiteral("Este computador"));
        for (int g=0;g<drives.size();++g) {
            auto *parent=drives[g];
            QList<QJsonObject> entries;
            for (const auto &v:identity) if (v.toObject()["group"].toString()==parent->text(0)) entries.append(v.toObject());
            std::sort(entries.begin(),entries.end(),[](const auto &a,const auto &b){return a["url"].toString()<b["url"].toString();});
            QSet<QString> retained;
            for (const auto &entry : entries) {
                const QString key=entry["key"].toString(); retained.insert(key);
                QTreeWidgetItem *node=nullptr;
                for (int i=0;i<parent->childCount();++i) if (parent->child(i)->data(0,Qt::UserRole+10).toString()==key) { node=parent->child(i); break; }
                if (!node) node=add(parent,entry["name"].toString(),entry["icon"].toString(),QUrl(entry["url"].toString()),"drive");
                if (node->data(0,UrlRole).toUrl()!=QUrl(entry["url"].toString())) {clearChildren(node);node->setData(0,LoadedRole,false);}
                node->setText(0,entry["name"].toString()); node->setData(0,UrlRole,QUrl(entry["url"].toString()));
                node->setData(0,Qt::UserRole+10,key);
            }
            for (int i=parent->childCount()-1;i>=0;--i) if (!retained.contains(parent->child(i)->data(0,Qt::UserRole+10).toString())) delete parent->takeChild(i);
            // Move only if order actually changed, retaining expansion and selection.
            for (int i=0;i<entries.size();++i) for (int j=i;j<parent->childCount();++j)
                if (parent->child(j)->data(0,Qt::UserRole+10).toString()==entries[i]["key"].toString()) { if(i!=j) parent->insertChild(i,parent->takeChild(j)); break; }
        }
    }
};
