// SPDX-License-Identifier: GPL-2.0-or-later
// Linux BR: native drive cards exclusively for linuxbr:/ entries.
#include <QPainter>
#include <QIcon>

QVariantMap DolphinFileItemListWidget::linuxbrCard() const
{
    if (styleOption().maxTextLines != 1) return {};
    const auto url = data().value("url").toUrl();
    if (url.scheme() != QLatin1String("linuxbr") || url.path().size() != 2) return {};
    return data().value("linuxbrCard").toMap();
}

QRectF DolphinFileItemListWidget::iconRect() const
{
    if (linuxbrCard().isEmpty()) return KFileItemListWidget::iconRect();
    return QRectF(12, (size().height()-56)/2, 56, 56);
}

QRectF DolphinFileItemListWidget::textRect() const
{
    if (linuxbrCard().isEmpty()) return KFileItemListWidget::textRect();
    return QRectF(80, 12, qMax(0.0, size().width()-96), size().height()-24);
}

QRectF DolphinFileItemListWidget::selectionRect() const
{
    if (linuxbrCard().isEmpty()) return KFileItemListWidget::selectionRect();
    return QRectF(4, 4, qMax(0.0, size().width()-8), qMax(0.0, size().height()-8));
}

QRectF DolphinFileItemListWidget::textFocusRect() const
{
    if (linuxbrCard().isEmpty()) return KFileItemListWidget::textFocusRect();
    return selectionRect().adjusted(2, 2, -2, -2);
}

void DolphinFileItemListWidget::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{
    const auto card = linuxbrCard();
    if (card.isEmpty()) { KFileItemListWidget::paint(painter, option, widget); return; }
    // Refresh the standard layout BEFORE the base class opens a painter on its
    // hover pixmap. selectionRect() also refreshes it, but doing so from inside
    // drawItemStyleOption() deletes that pixmap while its painter is active.
    // Use the qualified getter: our textRect() override skips the standard cache.
    (void)KStandardItemListWidget::textRect();
    KItemListWidget::paint(painter, option, widget);
    painter->save();
    painter->setRenderHint(QPainter::Antialiasing);
    const auto palette = styleOption().palette;
    const auto foreground = isSelected() ? palette.highlightedText().color() : palette.text().color();
    QIcon::fromTheme(card.value("icon").toString()).paint(painter, iconRect().toRect());
    const auto rect = textRect();
    auto font = styleOption().font;
    font.setBold(true); painter->setFont(font); painter->setPen(foreground);
    const qreal lineHeight = painter->fontMetrics().height()+4;
    painter->drawText(QRectF(rect.x(), rect.y(), rect.width(), lineHeight), Qt::AlignVCenter,
                      painter->fontMetrics().elidedText(card.value("title").toString(), Qt::ElideRight, rect.width()));
    const auto usage = card.value("usage").toMap();
    const double total = usage.value("total").toDouble();
    if (total > 0) {
        const double fraction = qBound(0.0, usage.value("used").toDouble()/total, 1.0);
        const QRectF bar(rect.x(), rect.y()+lineHeight+8, rect.width(), 18);
        painter->setPen(QPen(palette.mid().color(), 1));
        painter->setBrush(palette.base()); painter->drawRoundedRect(bar, 1, 1);
        painter->setPen(Qt::NoPen);
        painter->setBrush(fraction >= .9 ? QColor("#c74b50") : palette.highlight().color());
        painter->drawRect(QRectF(bar.x()+1, bar.y()+1, (bar.width()-2)*fraction, bar.height()-2));
    }
    font.setBold(false); painter->setFont(font); painter->setPen(foreground);
    const auto text = card.value("capacityText").toString();
    painter->drawText(QRectF(rect.x(), rect.y()+lineHeight+34, rect.width(), lineHeight), Qt::AlignVCenter,
                      painter->fontMetrics().elidedText(text, Qt::ElideRight, rect.width()));
    painter->restore();
}
