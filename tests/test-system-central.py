#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
sys.path.insert(0,str(root/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
sys.path.insert(0,str(root/'packages/linuxbr-device-manager/files/usr/lib/linuxbr-device-manager'))
import central
import desktopflows08
central.Devices.refresh=lambda self:None
central.AccountsPage.refresh=lambda self:None
from app import Window
Window.refresh=lambda self:None
application=QApplication([])
window=central.Central(); window.drives.timer.stop()
window.drives.populate(dict(rows=[dict(key='system',name='Sistema',kind='Sistema',size=0,fs='ext4',mounts=['/'],path='',protected=True)],data=dict(letters={},shares={})))
window.show();application.processEvents()
assert window.stack.count()==len(central.PAGES)
assert window.stack.currentIndex()==0
assert not window.drives.isWindow()
window.nav.setCurrentRow(4);assert window.stack.currentIndex()==4
window.search.setText('tampa');assert window.nav.currentItem().text()=='Energia e bateria'
window.search.setText('wifi');assert window.nav.currentItem().text()=='Rede'
window.search.setText('windows update');assert window.nav.currentItem().text()=='Programas'
assert any(window.nav.item(i).text()=='Atualizações' and not window.nav.item(i).isHidden() for i in range(window.nav.count()))
window.navigate('Atualizações');assert window.stack.currentWidget().tabs.currentIndex()==1
window.search.setText('naoexiste-configuracao');assert window.search_status.isVisible();assert not window.stack.isVisible()
window.search.clear()
assert window.stack.isVisible();assert not window.search_status.isVisible()
window.navigate('Primeiros passos');assert 'Bem-vindo' in window.stack.currentWidget().browser.toPlainText()
window.navigate('Recuperação e ajuda');assert 'Cópia de segurança' in window.stack.currentWidget().browser.toPlainText()
window.navigate('Sistema')
about=window.stack.currentWidget()
assert len(about.details)==2
about.copy_details()
assert 'Kernel:' in application.clipboard().text()

# A focused native card accepts Enter once and delegates only the explicit action.
window.navigate('Administração');application.processEvents()
window.activateWindow();application.processEvents()
card=next(button for button in window.stack.currentWidget().findChildren(central.PathButton)
          if button.text()=='Aplicativos e atualizações')
with patch.object(window,'launch') as launch:
    card.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(card,Qt.Key.Key_Return);application.processEvents()
    launch.assert_called_once_with(['linuxbr-store'])

# An embedded page handles its inner history before the Central's outer history.
window.navigate('Sistema');window.navigate('Pesquisa e padrões');application.processEvents()
flows=window.stack.currentWidget();assert isinstance(flows,desktopflows08.DesktopFlowsPage)
assert not flows.back_shortcut.isEnabled()
flows.history.clear();flows.navigate('apps',remember=False)
outer_history=list(window.navigation_history)
card=flows.navigation[('apps','defaults')]
with patch.object(desktopflows08.backend,'launch_native') as launch:
    card.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(card,Qt.Key.Key_Return);application.processEvents()
    assert flows.current_page=='defaults' and flows.history==['apps']
    assert application.focusWidget() is flows.choose
    launch.assert_not_called()
    QTest.keyClick(flows.choose,Qt.Key.Key_Left,Qt.KeyboardModifier.AltModifier)
    application.processEvents()
    assert window.stack.currentWidget() is flows and flows.current_page=='apps'
    assert flows.history==[] and window.navigation_history==outer_history
    QTest.keyClick(application.focusWidget(),Qt.Key.Key_Left,Qt.KeyboardModifier.AltModifier)
    application.processEvents()
    assert window.breadcrumb.text()=='Sistema'
    launch.assert_not_called()

window.navigate('Armazenamento'); assert window.stack.currentIndex()==2
window.navigate('Sistema')
assert window.grab().save(os.environ.get('CENTRAL_PREVIEW','/tmp/linuxbr-system.png'))
window.close()
print('PASS: Central, navigation, embedded storage and screenshot')
