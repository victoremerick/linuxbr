// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QWidget>
#include <functional>

class QComboBox;
class QLabel;
class QTableWidget;
class VolumeMap;

class PreflightPage final : public QWidget
{
public:
    explicit PreflightPage(std::function<void()> finished, QWidget* parent = nullptr);
    void scan();
    bool ready() const { return loaded; }
    QJsonObject liveChecks() const;

private:
    QWidget* storagePage();
    QWidget* firmwarePage();
    QWidget* peripheralsPage();
    void showReport(const QJsonObject& report);
    void showDisk(int index);

    std::function<void()> finished;
    QJsonArray disks;
    bool started = false;
    bool loaded = false;
    QLabel* notice;
    QComboBox* diskSelector;
    QTableWidget* volumes;
    VolumeMap* map;
    QLabel* firmwareInfo;
    QComboBox* keyboard;
    QComboBox* touchpad;
    QComboBox* audio;
    QComboBox* video;
};
