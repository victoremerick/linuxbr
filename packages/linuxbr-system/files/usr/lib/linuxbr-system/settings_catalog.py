"""Searchable configuration routes with explicit native capabilities."""
import shutil
import subprocess
import unicodedata

CATEGORIES=[('home','Início','go-home'),('system','Sistema','computer'),('devices','Bluetooth e dispositivos','preferences-devices-tree'),('network','Rede e Internet','network-workgroup'),('appearance','Personalização','preferences-desktop-theme'),('apps','Aplicativos','applications-all'),('accounts','Contas','system-users'),('language','Hora e idioma','preferences-desktop-locale'),('gaming','Jogos','applications-games'),('accessibility','Acessibilidade','preferences-desktop-accessibility'),('privacy','Privacidade e segurança','security-high'),('updates','Atualizações','system-software-update')]
PAGES=[]


def add(category,identifier,title,description,icon,*route,keywords=''):
    PAGES.append(dict(category=category,id=identifier,title=title,description=description,icon=icon,route=list(route),keywords=keywords))


def native(category,rows):
    for identifier,title,description,icon,module in rows:add(category,identifier,title,description,icon,'kcm',module)


for identifier,title,description,icon,page in [
 ('display','Tela','Monitores, resolução, escala, orientação e disposição.','video-display','Telas'),
 ('sound','Som','Saídas, entradas, microfones, perfis e volumes por aplicativo.','audio-volume-high','Áudio'),
 ('power','Energia e bateria','Tela, suspensão, tampa, botão de energia e bateria.','preferences-system-power-management','Energia e bateria'),
 ('storage','Armazenamento','Discos, letras de unidade, montagem e espaço ocupado.','drive-harddisk','Armazenamento'),
 ('remote','Área de trabalho remota','Acesso remoto, protocolos, usuários e conectividade.','krdc','Acesso remoto'),
 ('recovery','Recuperação','Pontos de sistema, restauração e opções de reparo.','document-revert','Backup e recuperação'),
 ('about','Sobre','Versão, nome do computador, processador, memória e suporte.','help-about','Sistema'),
 ('maintenance','Cuidados com o computador','Diagnóstico, proteção, espaço e limpeza com revisão.','tools-wizard','Cuidados com o computador')]:add('system',identifier,title,description,icon,'embedded',page)
native('system',[
 ('display-advanced','Tela avançada','Frequência, modos e capacidades oferecidos por cada monitor.','video-display','kcm_kscreen'),
 ('nightlight','Luz noturna','Temperatura da cor e horários da luz noturna.','weather-clear-night','kcm_nightlight'),
 ('notifications','Notificações','Preferências por aplicativo, alertas, sons e Não perturbe.','preferences-desktop-notification','kcm_notifications'),
 ('multitasking','Multitarefas','Foco, comportamento das janelas e posicionamento.','preferences-system-windows','kcm_kwinoptions'),
 ('switcher','Alt+Tab','Escolha o comportamento e a aparência da troca de janelas.','preferences-system-windows-switcher','kcm_kwintabbox'),
 ('desktops','Áreas de trabalho virtuais','Quantidade, organização e navegação entre áreas de trabalho.','preferences-desktop-virtual','kcm_kwin_virtualdesktops'),
 ('window-rules','Regras por janela','Tamanho, posição, foco e preferências de janelas específicas.','preferences-system-windows-actions','kcm_kwinrules'),
 ('session','Entrada e saída da sessão','Restaurar janelas, sair, desligar e comportamento da sessão.','system-log-out','kcm_smserver'),
 ('energy-history','Uso de energia','Estatísticas e informações de consumo disponíveis.','battery','kcm_energyinfo')])
add('system','clipboard','Área de transferência','Histórico, tamanho, comportamento e dados da área de transferência.','edit-paste','tool','clipboard')
add('system','virtualization','Máquinas virtuais','Crie, configure e gerencie máquinas, discos e redes virtuais.','computer','app','linuxbr-virtual-machines',keywords='hyper-v hyperv vm máquina virtual kvm qemu virtualbox')
add('system','administration','Ferramentas administrativas','Serviços, eventos, variáveis e tarefas agendadas.','preferences-system','tool','administration',keywords='services.msc eventvwr.msc taskschd.msc variáveis ambiente agendamento')
add('system','services','Serviços','Estado, início e configurações dos serviços da sua conta e do computador.','system-run','tool','administration','0')
add('system','events','Visualizador de eventos','Eventos e registros de diagnóstico dos serviços.','view-list-text','tool','administration','1')
add('system','environment','Variáveis de ambiente','Preferências de ambiente da sua conta e do computador.','preferences-system','tool','administration','2')
add('system','scheduler','Agendador de Tarefas','Programas, argumentos, horários e execução das tarefas agendadas.','appointment-new','tool','administration','3')
add('system','system-configuration','Configuração do Sistema','Inicialização normal, diagnóstica, serviços, programas automáticos e ferramentas.','preferences-system','app','linuxbr-msconfig',keywords='msconfig configuração seletiva boot')
add('system','boot-options','Configurações de inicialização','Modo de segurança, terminal, vídeo básico, diagnóstico e manutenção no próximo boot.','system-reboot','app','linuxbr-boot-options',keywords='F8 segurança recuperação shift reiniciar')
add('accounts','credentials-unlock','Desbloquear credenciais e senhas','Preparar o cofre seguro antes de entrar nos aplicativos.','wallet-open','app','linuxbr-credentials','--unlock',keywords='Office Microsoft Bottles autenticação login cofre')
add('accounts','credentials-store','Gerenciar senhas e cofres','Consultar o cofre seguro e alterar sua senha no gerenciador nativo.','dialog-password','app','seahorse',keywords='keyring credenciais segredos login')
native('devices',[
 ('bluetooth','Bluetooth','Parear, conectar e remover dispositivos Bluetooth.','preferences-system-bluetooth','kcm_bluetooth'),
 ('printers','Impressoras e scanners','Adicionar impressoras, padrões, propriedades e filas.','printer','kcm_printer_manager'),
 ('mouse','Mouse','Botões, velocidade, rolagem e preferências do ponteiro.','input-mouse','kcm_mouse'),
 ('touchpad','Touchpad','Toques, rolagem e sensibilidade em dispositivos compatíveis.','input-touchpad','kcm_touchpad'),
 ('keyboard','Teclado','Hardware, layouts, repetição e teclado brasileiro ABNT2.','input-keyboard','kcm_keyboard'),
 ('touch','Tela sensível ao toque','Associação de dispositivos e telas compatíveis.','input-touchscreen','kcm_touchscreen'),
 ('gestures','Gestos e bordas da tela','Ações de toque e navegação nas bordas da tela.','input-touchscreen','kcm_kwintouchscreen'),
 ('pen','Caneta e mesa digitalizadora','Mapeamento, botões e configurações do dispositivo.','input-tablet','kcm_tablet'),
 ('autoplay','Reprodução automática','Ações oferecidas ao conectar dispositivos e mídias.','media-removable','kcm_solid_actions'),
 ('automount','Montagem automática','Quando montar unidades removíveis e outros volumes.','drive-removable-media','kcm_device_automounter'),
 ('usb','Dispositivos USB','Informações sobre os dispositivos USB conectados.','preferences-devices-tree','kcm_usb'),
 ('thunderbolt','Thunderbolt','Autorização e gerenciamento de dispositivos compatíveis.','thunderbolt','kcm_bolt'),
 ('phone','Celular e dispositivos próximos','Envie arquivos e integre dispositivos com KDE Connect.','smartphone','kcm_kdeconnect')])
add('devices','device-manager','Gerenciador de Dispositivos','Hardware, drivers, identificação e diagnóstico.','preferences-devices-tree','embedded','Dispositivos')
add('devices','scan','Digitalizar documento','Scanners locais e de rede disponíveis.','scanner','app','skanpage')
add('devices','camera','Câmera e permissões','Permissões de câmera por aplicativo e limites dos formatos.','camera-web','tool','permissions')
native('network',[
 ('connections','Conexões e adaptadores','Wi-Fi, Ethernet, VPN, IP, DNS, rotas, métricas, ponte e VLAN.','network-wired','kcm_networkmanagement'),
 ('wifi','Wi-Fi e redes salvas','Conectar, editar e esquecer redes sem fio.','network-wireless','kcm_networkmanagement'),
 ('vpn','VPN','Criar e editar conexões dos protocolos instalados.','network-vpn','kcm_networkmanagement'),
 ('hotspot','Compartilhar conexão','Hotspot e conexão compartilhada conforme o adaptador.','network-wireless-hotspot','kcm_networkmanagement'),
 ])
add('network','network-information','Detalhes da conexão','Adaptadores, endereços IPv4/IPv6, gateway, DNS e propriedades da conexão.','network-workgroup','embedded','Detalhes da conexão')
for identifier,title,description,icon,page in [('ip','Endereços IP e DNS','Propriedades IPv4 e IPv6 por conexão.','network-wired','Endereços IP e DNS'),('proxy','Proxy','Servidor manual ou configuração automática PAC e alcance.','network-server','Proxy'),('firewall','Firewall','Regras, portas, serviços de rede e proteção de conexões.','security-high','Firewall'),('network-drives','Unidades e compartilhamentos','Compartilhamentos SMB e letras de unidade de rede.','folder-network','Arquivos e atalhos')]:add('network',identifier,title,description,icon,'embedded',page)
native('appearance',[
 ('background','Plano de fundo','Papel de parede, imagens e apresentação de slides.','preferences-desktop-wallpaper','kcm_wallpaper'),
 ('colors','Cores e modo claro/escuro','Esquemas de cor e aparência das aplicações.','preferences-desktop-color','kcm_colors'),
 ('themes','Temas','Aparência global, estilo e comportamento do desktop.','preferences-desktop-theme','kcm_lookandfeel'),
 ('icons','Ícones','Tema de ícones para aplicativos e funcionalidades.','preferences-desktop-icons','kcm_icons'),
 ('cursor','Ponteiro do mouse','Tema e tamanho do cursor.','input-mouse','kcm_cursortheme'),
 ('fonts','Fontes','Tamanho e renderização dos textos da interface.','preferences-desktop-font','kcm_fonts'),
 ('install-fonts','Instalar e gerenciar fontes','Fontes da sua conta e do sistema.','preferences-desktop-font','kcm_fontinst'),
 ('lockscreen','Tela de bloqueio','Imagem, tempo de bloqueio e comportamento da sessão.','system-lock-screen','kcm_screenlocker'),
 ('window-decoration','Barras de título','Bordas, botões e decoração das janelas.','preferences-system-windows','kcm_kwindecoration'),
 ('effects','Animações e efeitos','Efeitos visuais oferecidos pelo compositor.','preferences-desktop-effects','kcm_kwin_effects'),
 ('virtual-keyboard','Teclado virtual','Método de entrada e teclado na tela.','input-keyboard-virtual','kcm_virtualkeyboard'),
 ('desktop-sounds','Sons do sistema','Tema sonoro dos eventos e notificações.','audio-volume-high','kcm_soundtheme')])
add('appearance','desktop-layout','Menu Iniciar e barra de tarefas','Aparência, posição, organização e preferências do desktop.','preferences-desktop','embedded','Personalização')
for identifier,title,description,icon,args in [('store','Loja de aplicativos','Instale e descubra programas Linux, webapps e opções Windows.','system-software-install',[]),('installed','Aplicativos instalados','Biblioteca, origem, versão e remoção de programas.','applications-all',['--installed']),('sources','Fontes de aplicativos','Repositórios APT, Flatpak e catálogos adicionais.','network-server',['--sources'])]:add('apps',identifier,title,description,icon,'app','linuxbr-store',*args)
native('apps',[
 ('defaultapps','Aplicativos padrão','Navegador, e-mail e aplicações preferidas.','preferences-desktop-default-applications','kcm_componentchooser'),
 ('filetypes','Tipos de arquivo e protocolos','Aplicativos por extensão, tipo de conteúdo e protocolo.','document-properties','kcm_filetypes'),
 ('search-index','Pesquisa e indexação','Pastas e tipos de arquivo incluídos no índice.','edit-find','kcm_baloofile'),
 ('search-system','Pesquisa do sistema','Resultados, extensões e opções de pesquisa.','system-search','kcm_plasmasearch'),
 ('personal-folders','Localização das pastas pessoais','Documentos, downloads, imagens, música e vídeos.','user-home','kcm_desktoppaths')])
add('apps','startup','Programas de inicialização','Habilitar e desabilitar aplicativos no login, consultar origem e restaurar alterações.','system-run','embedded','Programas de inicialização',keywords='msconfig inicialização autostart iniciar login')
add('apps','optional-features','Recursos opcionais','Ativar serviços, revisar dependências e instalar ou remover recursos do computador.','preferences-plugin','embedded','Recursos opcionais',keywords='recursos windows opcionais features bluetooth wine virtualização impressão desenvolvimento')
add('apps','webapps','Aplicativos web e perfis','Sites em janelas próprias, favicons e contas separadas.','internet-web-browser','app','linuxbr-webapps')
add('apps','windows-apps','Programas Windows','Instaladores, ambientes Wine, receitas e reparação.','wine','app','linuxbr-windows')
add('apps','install-file','Instalar a partir de arquivo','Revisar um DEB, Flatpak, EXE ou MSI.','package-x-generic','app','linuxbr-install-package')
for identifier,title,description,page in [('users','Usuários','Contas locais, senha, foto, tipo de conta e acesso.','Usuários'),('organization','Trabalho, escola e domínio','Integração com domínio e contas da organização.','Organização')]:add('accounts',identifier,title,description,'system-users','embedded',page)
native('accounts',[
 ('signin','Opções de entrada','Contas, senhas e opções oferecidas para a sessão.','preferences-desktop-user-password','kcm_users'),
 ('login-screen','Tela de entrada','Preferências do gerenciador de login e entrada automática.','preferences-system-login','kcm_sddm'),
 ('credentials','Credenciais e senhas salvas','Carteira do desktop e credenciais de aplicativos.','wallet-manager','kcm_kwallet5'),
 ('backup-preferences','Backup pessoal','Planos, destinos e histórico de arquivos pessoais.','document-save','kcm_kup')])
native('language',[
 ('datetime','Data e hora','Relógio, sincronização e fuso horário.','preferences-system-time','kcm_clock'),
 ('region','Idioma e região','Idioma, moeda, números, datas e formatos brasileiros.','preferences-desktop-locale','kcm_regionandlang'),
 ('typing','Digitação e layouts','Teclados, layouts e repetição de teclas.','input-keyboard','kcm_keyboard'),
 ('spelling','Ortografia','Dicionários e preferências da verificação ortográfica.','tools-check-spelling','kcmspellchecking'),
 ('shortcuts','Atalhos de teclado','Atalhos globais e por aplicação.','preferences-desktop-keyboard','kcm_keys')])
add('gaming','games','Programas Windows e jogos','Steam, Proton, ambientes e diagnóstico de compatibilidade.','applications-games','app','linuxbr-windows','--page','games')
native('gaming',[('controllers','Controles de jogos','Testar botões, eixos e configurar controles compatíveis.','input-gaming','kcm_gamecontroller')])
add('gaming','capture','Capturas de tela','Capture tela, janela ou região com as opções disponíveis.','spectacle','app','spectacle')
native('accessibility',[
 ('access','Visão, audição e interação','Leitor de tela, teclado, avisos e recursos de acessibilidade.','preferences-desktop-accessibility','kcm_access'),
 ('text-size','Tamanho do texto','Fontes e tamanho do texto da interface.','preferences-desktop-font','kcm_fonts'),
 ('visual-effects','Efeitos visuais','Animações, transparência e efeitos do desktop.','preferences-desktop-effects','kcm_kwin_effects'),
 ('pointer','Ponteiro e cursor','Tema e tamanho do ponteiro.','input-mouse','kcm_cursortheme'),
 ('keyboard-access','Teclado acessível','Repetição, layout e opções complementares de entrada.','input-keyboard','kcm_keyboard'),
 ('contrast','Contraste e cores','Escolha um esquema legível e adequado à visão.','preferences-desktop-color','kcm_colors'),
 ('audio-access','Áudio e dispositivos','Volumes, entradas, saídas e canais de áudio.','audio-volume-high','kcm_pulseaudio')])
add('privacy','permissions','Permissões de aplicativos','Câmera pelo portal, som, rede e arquivos por aplicativo Flatpak.','preferences-system-privacy','tool','permissions')
native('privacy',[
 ('recent-files','Histórico de arquivos','Preferências dos arquivos recentes e atividades.','document-open-recent','kcm_recentFiles'),
 ('diagnostics','Dados de uso e diagnósticos','Preferências de envio de comentários do desktop.','preferences-system-privacy','kcm_feedback'),
 ('firmware-security','Segurança do firmware','Informações verificadas pelo serviço sobre firmware e inicialização.','security-high','kcm_firmware_security'),
 ('screenlock','Bloqueio da sessão','Quando bloquear e como proteger a sessão.','system-lock-screen','kcm_screenlocker')])
add('privacy','protection','Proteção e integridade','Estado de proteção, atualizações, backup e diagnósticos locais.','security-high','embedded','Cuidados com o computador')
add('privacy','web-permissions','Permissões dos sites','Preferências e permissões por perfil de aplicativo web.','internet-web-browser','app','linuxbr-webapps')
add('updates','updates','Atualizações do sistema e aplicativos','Consultar, revisar, instalar e acompanhar atualizações.','system-software-update','app','linuxbr-store','--updates')
add('updates','firmware','Atualizações de firmware','Dispositivos, versões oferecidas e instalação pelo fwupd.','preferences-devices-cpu','app','linuxbr-store','--firmware')
add('updates','update-recovery','Proteção antes de atualizar','Condições, pontos de sistema, recuperação e versão instalada.','document-revert','embedded','Atualizações')
add('updates','update-sources','Fontes e canais','Repositórios configurados, confiança e disponibilidade de atualizações.','network-server','app','linuxbr-store','--sources')

ALIASES={'Sistema':'about','Telas':'display','Áudio':'sound','Energia e bateria':'power','Armazenamento':'storage','Acesso remoto':'remote','Backup e recuperação':'recovery','Atualizações':'update-recovery','Cuidados com o computador':'maintenance','Dispositivos':'device-manager','Rede':'connections','Endereços IP e DNS':'ip','Proxy':'proxy','Firewall':'firewall','Arquivos e atalhos':'network-drives','Personalização':'desktop-layout','Usuários':'users','Organização':'organization','Programas':'installed','Aplicativos web':'webapps','Programas Windows e jogos':'windows-apps','Hora e idioma':'region','Entrada e atalhos':'keyboard','Pesquisa e padrões':'defaultapps','Privacidade e sessão':'screenlock','Administração':'administration','Notificações':'notifications','Acessibilidade':'access'}


def folded(text):return ''.join(c for c in unicodedata.normalize('NFD',text.casefold()) if not unicodedata.combining(c))


def search(query='',category=None):
    words=folded(query).split()
    return [page for page in PAGES if (not category or page['category']==category) and all(word in folded(' '.join([page['title'],page['description'],page['keywords'],page['id']])) for word in words)]


def inventory():
    modules=set()
    try:
        result=subprocess.run(['/usr/bin/kcmshell6','--list'],capture_output=True,text=True,timeout=15)
        if result.returncode==0:modules={line.split()[0] for line in result.stdout.splitlines() if ' - ' in line}
    except (OSError,subprocess.TimeoutExpired):pass
    import platform
    from pathlib import Path
    from about import release_summary
    memory='Não informada'
    try:memory=f"{int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))/1024**2:.1f} GiB"
    except (OSError,ValueError,StopIteration):pass
    space=shutil.disk_usage('/');summary=f'{platform.node()} · Linux BR {release_summary()[0]} · {memory} de memória · {space.free/1024**3:.1f} GiB livres no sistema'
    return dict(modules=modules,summary=summary,commands={p['route'][1]:bool(shutil.which(p['route'][1])) for p in PAGES if p['route'][0]=='app'})


def available(page,capabilities):
    kind,target,*_=page['route']
    if kind=='kcm' and target not in capabilities.get('modules',set()):return False,'Este módulo não está instalado nesta imagem.'
    if kind=='app' and not capabilities.get('commands',{}).get(target,False):return False,'Esta aplicação não está instalada nesta imagem.'
    return True,''
