// SPDX-License-Identifier: GPL-3.0-or-later
#include <QStylePlugin>
#include <QProxyStyle>
#include <QStyleFactory>
#include <QStyleOptionButton>
#include <QPainter>

class CleanStyle final : public QProxyStyle {
public:
    static QStyle *base() { auto *style=QStyleFactory::create("Breeze"); return style ? style : QStyleFactory::create("Fusion"); }
    CleanStyle() : QProxyStyle(base()) {}
    void drawPrimitive(PrimitiveElement element, const QStyleOption *option,
                       QPainter *painter, const QWidget *widget = nullptr) const override {
        if (element != PE_PanelButtonCommand) {
            QProxyStyle::drawPrimitive(element, option, painter, widget); return;
        }
        const auto *button = qstyleoption_cast<const QStyleOptionButton *>(option);
        if (!button) { QProxyStyle::drawPrimitive(element, option, painter, widget); return; }
        const bool enabled = button->state & State_Enabled;
        const bool primary = button->features & QStyleOptionButton::DefaultButton;
        const bool focus = button->state & State_HasFocus;
        const auto group = enabled ? QPalette::Active : QPalette::Disabled;
        QColor fill = button->palette.color(group, primary ? QPalette::Highlight : QPalette::Window);
        if (button->state & State_Sunken) fill = fill.darker(110);
        painter->save();
        painter->setRenderHint(QPainter::Antialiasing, false);
        painter->fillRect(button->rect, fill);
        if (!primary || focus) {
            painter->setPen(QPen(button->palette.color(group,
                focus ? QPalette::WindowText : (button->state & State_MouseOver) ? QPalette::Highlight : QPalette::Mid), focus ? 2 : 1));
            painter->drawRect(button->rect.adjusted(1, 1, -2, -2));
        }
        painter->restore();
    }
    void drawControl(ControlElement element, const QStyleOption *option,
                     QPainter *painter, const QWidget *widget = nullptr) const override {
        const auto *button = qstyleoption_cast<const QStyleOptionButton *>(option);
        if (element == CE_PushButtonLabel && button && (button->features & QStyleOptionButton::DefaultButton)) {
            QStyleOptionButton copy(*button);
            copy.palette.setColor(QPalette::ButtonText, button->palette.color(QPalette::HighlightedText));
            QProxyStyle::drawControl(element, &copy, painter, widget);return;
        }
        QProxyStyle::drawControl(element, option, painter, widget);
    }
};
class CleanPlugin final : public QStylePlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QStyleFactoryInterface" FILE "style.json")
public:
    QStyle *create(const QString &key) override {
        return key.compare("LinuxBRClean", Qt::CaseInsensitive) == 0 ? new CleanStyle : nullptr;
    }
};
#include "style.moc"
