"""Windows-like process overview using the kernel's /proc data."""
import os
import pwd
import signal
from PyQt6.QtCore import QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QTabWidget,QProgressBar)


def snapshot():
    ticks=os.sysconf('SC_CLK_TCK')
    memory={}
    with open('/proc/meminfo',encoding='utf-8') as stream:
        for line in stream:
            key,_,value=line.partition(':')
            if key in ('MemTotal','MemAvailable'):
                memory[key]=int(value.strip().split()[0])*1024
    rows=[]
    for name in os.listdir('/proc'):
        if not name.isdecimal(): continue
        try:
            pid=int(name)
            data=open(f'/proc/{pid}/stat',encoding='utf-8').read()
            tail=data[data.rfind(')')+2:].split()
            cmd=open(f'/proc/{pid}/cmdline','rb').read(4096).split(b'\0')[0].decode(errors='replace')
            uid=os.stat(f'/proc/{pid}').st_uid
            try:user=pwd.getpwuid(uid).pw_name
            except KeyError:user=str(uid)
            rss=int(tail[21])*os.sysconf('SC_PAGE_SIZE')
            rows.append(dict(pid=pid,name=cmd.split('/')[-1] or data[data.find('(')+1:data.rfind(')')],
                user=user,uid=uid,rss=rss,cpu=(int(tail[11])+int(tail[12]))/ticks))
        except (OSError,ValueError,IndexError): continue
    return rows,memory


class NumericItem(QTableWidgetItem):
    def __init__(self, text, number):
        super().__init__(text)
        self.number = number
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        return self.number < other.number


class Tasks(QWidget):
    def __init__(self):
        super().__init__()
        self.previous={}; self.last_time=None
        body=QVBoxLayout(self); body.setContentsMargins(32,28,32,28)
        title=QLabel('Gerenciador de Tarefas'); title.setStyleSheet('font-size:26px;font-weight:600'); body.addWidget(title)
        tabs=QTabWidget(); body.addWidget(tabs,1)
        processes=QWidget(); process_body=QVBoxLayout(processes)
        toolbar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('Buscar por nome, PID ou usuário…')
        self.search.setAccessibleName('Buscar por nome, PID ou usuário'); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_rows); toolbar.addWidget(self.search)
        self.end_button=QPushButton(QIcon.fromTheme('process-stop'), 'Finalizar tarefa')
        self.end_button.setEnabled(False); self.end_button.clicked.connect(self.end_task); toolbar.addWidget(self.end_button)
        refresh=QPushButton(QIcon.fromTheme('view-refresh'), 'Atualizar')
        refresh.clicked.connect(self.refresh); toolbar.addWidget(refresh)
        process_body.addLayout(toolbar)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Nome','PID','Usuário','CPU','Memória'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.table.setSortingEnabled(True); process_body.addWidget(self.table)
        self.table.itemSelectionChanged.connect(self.update_end_button)
        self.results = QLabel()
        process_body.addWidget(self.results)
        tabs.addTab(processes,'Processos')
        performance=QWidget(); perf=QVBoxLayout(performance)
        self.cpu=QProgressBar(); self.ram=QProgressBar(); self.cpu.setFormat('CPU: %p%');self.ram.setFormat('Memória: %p%')
        perf.addWidget(self.cpu);perf.addWidget(self.ram);perf.addStretch();tabs.addTab(performance,'Desempenho')
        self.message=QLabel();self.message.setWordWrap(True);body.addWidget(self.message)
        self.timer=QTimer(self); self.timer.setInterval(2000); self.timer.timeout.connect(self.refresh);self.timer.start()
        self.refresh()

    def refresh(self):
        import time
        now=time.monotonic(); rows,memory=snapshot(); elapsed=max(.1,now-self.last_time) if self.last_time else 1
        previous=self.previous;self.previous={r['pid']:r['cpu'] for r in rows};self.last_time=now
        selected = self.selected_process()
        selected_pid = selected.text() if selected else None
        scroll = self.table.verticalScrollBar()
        position = scroll.value()
        with QSignalBlocker(self.table):
            self.table.clearSelection()
            self.table.setCurrentItem(None)
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            selected_cell = None
            for index, row in enumerate(rows):
                self.table.setRowHidden(index, False)
                usage = max(0, (row['cpu'] - previous.get(row['pid'], row['cpu'])) / elapsed * 100)
                pid = NumericItem(str(row['pid']), row['pid'])
                pid.setData(Qt.ItemDataRole.UserRole, row['uid'])
                cells = (QTableWidgetItem(row['name']), pid, QTableWidgetItem(row['user']),
                         NumericItem(f'{usage:.1f}%', usage),
                         NumericItem(f'{row["rss"]/1048576:.0f} MiB', row['rss']))
                for column, cell in enumerate(cells):
                    self.table.setItem(index, column, cell)
                if pid.text() == selected_pid:
                    selected_cell = pid
            self.table.setSortingEnabled(True)
            if selected_cell is not None:
                self.table.selectRow(selected_cell.row())
        self.filter_rows(self.search.text())
        scroll.setValue(position)
        total=memory.get('MemTotal',1)
        self.ram.setValue(min(100,round((total-memory.get('MemAvailable',total))*100/total)))
        self.cpu.setValue(min(100,round(sum(max(0,r['cpu']-previous.get(r['pid'],r['cpu'])) for r in rows)*100/elapsed/(os.cpu_count() or 1))))

    def filter_rows(self,text):
        query = text.casefold().strip()
        visible = 0
        selected = self.selected_process()
        for row in range(self.table.rowCount()):
            matches = any(query in self.table.item(row, column).text().casefold() for column in range(3))
            self.table.setRowHidden(row, not matches)
            visible += matches
        if selected is not None and self.table.isRowHidden(selected.row()):
            self.table.clearSelection()
            self.table.setCurrentItem(None)
        self.results.setText(f'Processos exibidos: {visible}' if visible else 'Nenhum processo encontrado.')
        self.update_end_button()

    def selected_process(self):
        row = self.table.currentRow()
        if row >= 0 and not self.table.isRowHidden(row) and self.table.selectedItems():
            return self.table.item(row, 1)
        return None

    def update_end_button(self):
        item = self.selected_process()
        allowed = (item is not None and item.data(Qt.ItemDataRole.UserRole) == os.getuid()
                   and int(item.text()) not in (1, os.getpid()))
        self.end_button.setEnabled(allowed)

    def end_task(self):
        item = self.selected_process()
        if item is None:
            self.message.setText('Selecione um processo.');return
        pid = int(item.text())
        uid = item.data(Qt.ItemDataRole.UserRole)
        name = self.table.item(item.row(), 0).text()
        if uid!=os.getuid() or pid in (1,os.getpid()):
            self.message.setText('Só é possível finalizar processos da sua conta.');return
        confirmation = f'Encerrar {name} (PID {pid})? Dados não salvos podem ser perdidos.'
        if QMessageBox.question(self,'Finalizar tarefa',confirmation,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:os.kill(pid,signal.SIGTERM);self.message.setText('Sinal de encerramento enviado.')
        except ProcessLookupError:self.message.setText('O processo já terminou.')
        except PermissionError:self.message.setText('Sem permissão para encerrar esse processo.')


def main():
    import sys
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication
    from visual_style import BUTTONS
    application=QApplication(sys.argv)
    application.setDesktopFileName('linuxbr-task-manager')
    window=Tasks();window.setWindowTitle('Gerenciador de tarefas Linux BR')
    window.setWindowIcon(QIcon.fromTheme('utilities-system-monitor'))
    window.setStyleSheet(BUTTONS);window.resize(920,620)
    window.show()
    return application.exec()


if __name__=='__main__':
    raise SystemExit(main())
