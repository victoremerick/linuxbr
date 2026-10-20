"""Windows-like process overview using the kernel's /proc data."""
import os
import pwd
import signal
from PyQt6.QtCore import QTimer, Qt
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


class Tasks(QWidget):
    def __init__(self):
        super().__init__()
        self.previous={}; self.last_time=None
        body=QVBoxLayout(self); body.setContentsMargins(32,28,32,28)
        title=QLabel('Gerenciador de Tarefas'); title.setStyleSheet('font-size:26px;font-weight:600'); body.addWidget(title)
        tabs=QTabWidget(); body.addWidget(tabs,1)
        processes=QWidget(); process_body=QVBoxLayout(processes)
        toolbar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('Buscar processo…'); self.search.textChanged.connect(self.filter_rows); toolbar.addWidget(self.search)
        end=QPushButton('Finalizar tarefa'); end.clicked.connect(self.end_task); toolbar.addWidget(end)
        refresh=QPushButton('Atualizar'); refresh.clicked.connect(self.refresh); toolbar.addWidget(refresh)
        process_body.addLayout(toolbar)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Nome','PID','Usuário','CPU','Memória'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True); process_body.addWidget(self.table)
        tabs.addTab(processes,'Processos')
        performance=QWidget(); perf=QVBoxLayout(performance)
        self.cpu=QProgressBar(); self.ram=QProgressBar(); self.cpu.setFormat('CPU: %p%');self.ram.setFormat('Memória: %p%')
        perf.addWidget(self.cpu);perf.addWidget(self.ram);perf.addStretch();tabs.addTab(performance,'Desempenho')
        self.message=QLabel();body.addWidget(self.message)
        self.timer=QTimer(self); self.timer.setInterval(2000); self.timer.timeout.connect(self.refresh);self.timer.start()
        self.refresh()

    def refresh(self):
        import time
        now=time.monotonic(); rows,memory=snapshot(); elapsed=max(.1,now-self.last_time) if self.last_time else 1
        previous=self.previous;self.previous={r['pid']:r['cpu'] for r in rows};self.last_time=now
        selected=self.table.currentItem();selected_pid=self.table.item(selected.row(),1).text() if selected and self.table.item(selected.row(),1) else ''
        self.table.setSortingEnabled(False);self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            usage=max(0, (row['cpu']-previous.get(row['pid'],row['cpu']))/elapsed*100)
            for j,value in enumerate((row['name'],str(row['pid']),row['user'],f'{usage:.1f}%',f'{row["rss"]/1048576:.0f} MiB')):
                cell=QTableWidgetItem(value)
                if j==1:cell.setData(Qt.ItemDataRole.UserRole,row['uid'])
                self.table.setItem(i,j,cell)
            if selected_pid==str(row['pid']):self.table.selectRow(i)
        self.table.setSortingEnabled(True);self.filter_rows(self.search.text())
        total=memory.get('MemTotal',1)
        self.ram.setValue(min(100,round((total-memory.get('MemAvailable',total))*100/total)))
        self.cpu.setValue(min(100,round(sum(max(0,r['cpu']-previous.get(r['pid'],r['cpu'])) for r in rows)*100/elapsed/(os.cpu_count() or 1))))

    def filter_rows(self,text):
        query=text.casefold().strip()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row,query not in self.table.item(row,0).text().casefold()
                and query not in self.table.item(row,1).text())

    def end_task(self):
        row=self.table.currentRow()
        if row<0:self.message.setText('Selecione um processo.');return
        pid=int(self.table.item(row,1).text());uid=self.table.item(row,1).data(Qt.ItemDataRole.UserRole)
        if uid!=os.getuid() or pid in (1,os.getpid()):
            self.message.setText('Só é possível finalizar processos da sua conta.');return
        if QMessageBox.question(self,'Finalizar tarefa',f'Encerrar o processo {pid}? Dados não salvos podem ser perdidos.')!=QMessageBox.StandardButton.Yes:return
        try:os.kill(pid,signal.SIGTERM);self.message.setText('Sinal de encerramento enviado.')
        except ProcessLookupError:self.message.setText('O processo já terminou.')
        except PermissionError:self.message.setText('Sem permissão para encerrar esse processo.')
