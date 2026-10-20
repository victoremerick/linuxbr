// Run in a disposable container with a temporary HOME/XDG configuration.
#include "linuxbr-sidebar.h"
#include <QTemporaryDir>
#include <QEventLoop>
#include <iostream>
#define CHECK(x) do { if (!(x)) { std::cerr << "FAIL line " << __LINE__ << ": " #x "\n"; return 1; } } while(false)
class TestSidebar : public LinuxBRSidebar { public: using LinuxBRSidebar::LinuxBRSidebar; using LinuxBRSidebar::dropEvent; };
int main(int argc,char **argv) {
    QApplication app(argc,argv);
    QTemporaryDir temp;
    using namespace LinuxBRNavigation;
    State state(temp.path()+"/state.json");
    state.seed(); CHECK(state.read()["favorites"].toArray().size()==6);
    CHECK(state.favorite(QUrl("smb://user:secret@server/team"),"Equipe"));
    CHECK(!QJsonDocument(state.read()).toJson().contains("secret"));
    CHECK(state.favorite(QUrl("smb://server/team"),"Equipe nova"));
    CHECK(state.read()["favorites"].toArray().size()==7);
    CHECK(state.favorite(QUrl("smb://server/team"),{},true));
    CHECK(!state.favorite(QUrl("javascript:evil"),"Bad"));
    const qint64 now=2000000000;
    CHECK(state.visit(QUrl("file:///expired"),now-31*86400));
    for (int i=0;i<6;++i) for(int n=0;n<=i;++n) CHECK(state.visit(QUrl("file:///folder"+QString::number(i)),now-6000+i*600+n*61));
    auto top=State::frequent(state.read(),now);
    CHECK(top.size()==3); CHECK(top.first()=="file:///folder5"); CHECK(!top.contains("file:///expired"));
    CHECK(state.edit([](QJsonObject &s){s["limit"]=5;})); CHECK(State::frequent(state.read(),now).size()==5);
    CHECK(state.visit(QUrl("file:///folder5"),now));
    const auto before=state.read()["history"].toObject()["file:///folder5"].toArray().size();
    CHECK(state.visit(QUrl("file:///folder5"),now+1));
    CHECK(state.read()["history"].toObject()["file:///folder5"].toArray().size()==before);
    State second(temp.path()+"/state.json"); CHECK(second.favorite(QUrl("file:///other"),"Other"));
    CHECK(state.read()["favorites"].toArray().size()==7); CHECK(State::limit(state.read())==5);
    CHECK((QFileInfo(temp.path()+"/state.json").permissions() & (QFileDevice::ReadOther|QFileDevice::WriteOther))==0);
    TestSidebar sidebar(nullptr,[](const QUrl &,bool){});
    CHECK(sidebar.topLevelItemCount()==4);
    CHECK(sidebar.topLevelItem(0)->text(0)==QStringLiteral("Acesso rápido"));
    CHECK(sidebar.topLevelItem(1)->text(0)==QStringLiteral("Mais acessados"));
    CHECK(sidebar.topLevelItem(2)->text(0)==QStringLiteral("Este computador"));
    CHECK(sidebar.topLevelItem(3)->text(0)==QStringLiteral("Locais de rede"));
    QJsonArray places;
    auto drive=[](QString letter,QString group,QString name) {return QJsonObject{{"key",letter},{"url","linuxbr:/"+letter},{"group",group},{"card",QJsonObject{{"title",name},{"icon","drive-harddisk"}}}};};
    places.append(drive("F","Discos locais","Aardvark (F:)"));
    places.append(drive("E",QStringLiteral("Dispositivos removíveis"),"USB (E:)"));
    places.append(drive("D","Discos locais","Dados (D:)")); places.append(drive("C","Discos locais","Sistema (C:)"));
    places.append(drive("Z","Unidades de rede","Equipe (Z:)")); sidebar.applyDrives(places);
    auto *local=sidebar.topLevelItem(2)->child(0);
    CHECK(local->childCount()==3); CHECK(local->child(0)->text(0)=="Sistema (C:)"); CHECK(local->child(2)->text(0)=="Aardvark (F:)");
    auto *system=local->child(0); system->setExpanded(true);
    sidebar.applyDrives(places); CHECK(local->child(0)==system); CHECK(system->isExpanded());
    places.removeAt(0); sidebar.applyDrives(places); CHECK(local->childCount()==2); CHECK(local->child(0)==system);
    // Test actual asynchronous folder expansion without touching real volumes.
    QDir().mkpath(temp.path()+"/folder/child");
    auto *quick=sidebar.topLevelItem(0);
    auto *item=new QTreeWidgetItem(quick); item->setData(0,Qt::UserRole,QUrl::fromLocalFile(temp.path()+"/folder"));
    item->setData(0,Qt::UserRole+1,"favorite"); item->setChildIndicatorPolicy(QTreeWidgetItem::ShowIndicator);
    item->setExpanded(true);
    QEventLoop loop; QTimer::singleShot(2000,&loop,&QEventLoop::quit); loop.exec();
    CHECK(item->childCount()==1); CHECK(item->child(0)->text(0)=="child");
    sidebar.resize(360,900); sidebar.show(); app.processEvents();
    QMimeData mime; mime.setUrls({QUrl::fromLocalFile(temp.path()+"/folder")});
    QDropEvent drop(sidebar.visualItemRect(quick).center(),Qt::CopyAction|Qt::MoveAction,&mime,Qt::LeftButton,Qt::NoModifier);
    sidebar.dropEvent(&drop);
    CHECK(drop.isAccepted()); CHECK(drop.dropAction()==Qt::CopyAction);
    CHECK(QFileInfo(temp.path()+"/folder/child").isDir());
    QDropEvent moveOnly(sidebar.visualItemRect(quick).center(),Qt::MoveAction,&mime,Qt::LeftButton,Qt::NoModifier);
    sidebar.dropEvent(&moveOnly); CHECK(!moveOnly.isAccepted());
    std::cout << "PASS: sidebar groups, drive order/hotplug, lazy folder tree, favorites, history bounds and privacy\n";
    return 0;
}
