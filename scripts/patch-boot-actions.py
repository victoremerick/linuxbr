#!/usr/bin/env python3
"""Integrate one-boot maintenance into the existing authenticated power flows."""
from pathlib import Path
import sys


def patch_sddm(path):
    text=path.read_text()
    needle='onClicked: sddm.reboot()'
    if text.count(needle)!=2:raise ValueError('Revisar ações de reinício do tema SDDM.')
    text=text.replace('import QtQuick 2.15','import org.linuxbr.boot 1.0\nimport QtQuick 2.15',1)
    text=text.replace(needle,'onClicked: { if (!Boot.shiftHeld() || Boot.prepareRecovery()) sddm.reboot(); else root.notificationMessage = Boot.lastError; }')
    path.write_text(text)


def patch_logout(path):
    text=path.read_text()
    if 'id: rebootButton' not in text or 'return () => softwareUpdatePending ? rebootUpdateRequested() : rebootRequested();' not in text:
        raise ValueError('Revisar diálogo de reinício do Plasma.')
    text=text.replace('import QtQuick 2.2','import org.linuxbr.boot 1.0\nimport QtQuick 2.2',1)
    text=text.replace('    id: root','''    id: root
    property bool linuxbrRecoveryRequested: Boot.shiftHeld()
    function linuxbrRestart(withUpdates) {
        if (linuxbrRecoveryRequested || Boot.shiftHeld()) {
            if (!Boot.prepareRecovery()) { root.remainingTime = -1; return; }
            rebootRequested();
        } else if (withUpdates) rebootUpdateRequested();
        else rebootRequested();
    }
    PlasmaComponents.Label {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 24
        width: Math.min(parent.width - 48, 800)
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        text: Boot.lastError.length ? Boot.lastError : "Segure Shift ao reiniciar para abrir a manutenção."
        z: 100
    }''',1)
    text=text.replace('return () => softwareUpdatePending ? rebootUpdateRequested() : rebootRequested();','return () => root.linuxbrRestart(softwareUpdatePending);')
    needle='''                    if (softwareUpdatePending) {
                        rebootUpdateRequested();
                    } else {
                        rebootRequested();
                    }'''
    if text.count(needle)!=1:raise ValueError('Revisar botão de reinício do Plasma.')
    text=text.replace(needle,'                    root.linuxbrRestart(softwareUpdatePending);')
    text=text.replace('onClicked: rebootRequested()','onClicked: root.linuxbrRestart(false)')
    path.write_text(text)


if __name__=='__main__':
    {'sddm':patch_sddm,'logout':patch_logout}[sys.argv[1]](Path(sys.argv[2]))
