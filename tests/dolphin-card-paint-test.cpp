// Regression: refreshing a dirty card must not delete an active hover painter.
#include "views/dolphinfileitemlistwidget.h"
#include <QApplication>
#include <QImage>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QPainter>
#include <QStyleFactory>
#include <QStyleOptionGraphicsItem>
#include <QUrl>
#include <QWidget>
#include <iostream>
#include <memory>

class Card : public DolphinFileItemListWidget {
public:
    using DolphinFileItemListWidget::DolphinFileItemListWidget;
    using DolphinFileItemListWidget::paint;
};
int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    auto *style = QStyleFactory::create(QStringLiteral("Breeze"));
    if (!style) { std::cerr << "Breeze style required\n"; return 1; }
    app.setStyle(style);
    QWidget viewport;
    std::unique_ptr<KItemListWidgetInformant> informant(KFileItemListWidget::createInformant());
    QGraphicsScene scene;
    QGraphicsView view(&scene, &viewport);
    Card card(informant.get(), nullptr);
    scene.addItem(&card);
    card.setIndex(0);
    card.setVisibleRoles({"text"});
    card.setLayout(KStandardItemListWidget::IconsLayout);
    KItemListStyleOption options;
    options.font = app.font();
    options.fontMetrics = QFontMetrics(options.font);
    options.palette = app.palette();
    options.maxTextLines = 1;
    card.setStyleOption(options);
    QImage image(600, 200, QImage::Format_ARGB32_Premultiplied);
    QStyleOptionGraphicsItem graphicsOption;
    for (int i = 0; i < 100; ++i) {
        card.setHovered(false);
        card.setSelected(false);
        card.setCurrent(false);
        card.resize(400 + i % 20, 112);
        card.setData({{"url", QUrl("linuxbr:/C")}, {"text", QString("Sistema (C:) %1").arg(i)},
                      {"iconName", "drive-harddisk"}, {"isDir", true},
                      {"linuxbrCard", QVariantMap{{"title", "Sistema (C:)"}, {"icon", "drive-harddisk"},
                        {"capacityText", "50 GiB livres de 100 GiB"},
                        {"usage", QVariantMap{{"total", 100.0}, {"used", double(i)}}}}}});
        card.setHovered(true);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        // The first dirty hovered paint reproduced the original SIGSEGV.
        card.paint(&painter, &graphicsOption, &viewport);
        card.setSelected(true);
        card.setCurrent(true);
        card.paint(&painter, &graphicsOption, &viewport);
        if (!painter.isActive()) return 2;
    }
    // Ordinary folders retain the upstream painting path.
    card.setHovered(false);
    card.setData({{"url", QUrl("file:///tmp")}, {"text", "Folder"}, {"iconName", "folder"}, {"isDir", true}});
    QPainter painter(&image);
    card.paint(&painter, &graphicsOption, &viewport);
    std::cout << "PASS: Breeze cards, hover, selection, resize, usage refresh and ordinary folder\n";
}
