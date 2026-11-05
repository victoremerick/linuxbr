#include <QObject>
#include <QQmlExtensionPlugin>
#include <QQmlEngine>
#include <QJSEngine>
#include <QGuiApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusReply>

class Boot : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString lastError READ lastError NOTIFY lastErrorChanged)
public:
    using QObject::QObject;
    QString lastError() const { return error; }
    Q_INVOKABLE bool shiftHeld() const {
        return QGuiApplication::keyboardModifiers().testFlag(Qt::ShiftModifier);
    }
    Q_INVOKABLE bool prepareRecovery() {
        auto message = QDBusMessage::createMethodCall(QStringLiteral("org.linuxbr.Boot"), QStringLiteral("/org/linuxbr/Boot"), QStringLiteral("org.linuxbr.Boot"), QStringLiteral("PrepareRecovery"));
        const QDBusReply<bool> reply = QDBusConnection::systemBus().call(message, QDBus::Block, 7000);
        error = reply.isValid() && reply.value() ? QString() : QStringLiteral("Não foi possível preparar a manutenção. ") + reply.error().message();
        emit lastErrorChanged();
        return error.isEmpty();
    }
signals:
    void lastErrorChanged();
private:
    QString error;
};

class BootPlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override {
        qmlRegisterSingletonType<Boot>(uri, 1, 0, "Boot", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Boot; });
    }
};

#include "plugin.moc"
