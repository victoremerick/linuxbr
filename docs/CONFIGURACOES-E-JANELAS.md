# Configurações e janelas Linux BR

## Experiência padrão

O Konsole abre novas janelas e abas com o perfil Linux BR e letras de unidades.
`terminal-modo linux` troca somente a sessão atual para o prompt tradicional;
`terminal-modo letras` volta ao modo de letras. Scripts continuam usando Bash e
caminhos Linux. Preferências antigas em terminal.json não determinam a abertura.

O autostart `linuxbr-session-defaults` desativa a flutuação dos painéis existentes,
sem recriar seus widgets. A migração dos controles de janela ocorre uma vez por
usuário e guarda o kwinrc anterior em ~/.local/state/linuxbr. O tema Aurorae usa
botões retangulares de minimizar, maximizar/restaurar e fechar à direita, com
menu à esquerda. O clique direito no título abre o menu de operações do KWin;
mover e redimensionar ficam em Mais ações. Aplicativos com decoração própria
podem desenhar seus próprios controles.

## Central

| Categoria | Recursos |
| --- | --- |
| Dispositivos | Informações de hardware, drivers, impressoras, Bluetooth, áudio e KDE Connect |
| Armazenamento | Gerenciamento de discos e letras existente |
| Rede | Wi-Fi/Ethernet, VPN, proxy KDE, Bluetooth e compartilhamentos |
| Usuários / Organização | Contas locais e integração de domínio existente |
| Programas | Programas instalados, instalação local, catálogo e atualizações via Discover |
| Telas | Monitores, resolução, escala e disposição via KScreen |
| Personalização | Claro/escuro e quatro cores de destaque, mantendo layout e decoração |
| Acesso remoto | Cliente RDP/VNC (KRDC) e compartilhamento da sessão via VNC (Krfb) |

Os módulos de hardware usam as ferramentas KDE do sistema. O compartilhamento
remoto não é ativado automaticamente: configure autorização e senha no Krfb;
para acesso externo, utilize a rede privada/VPN da organização. Isso não configura
um servidor de login RDP nem sessões remotas independentes.

O proxy é por usuário, para aplicações KDE/KIO: desativado, manual ou PAC.
Não altera proxy do APT, serviços ou configurações próprias dos navegadores.
URLs com credenciais embutidas não são aceitas.

A personalização aplica os esquemas Linux BR, variantes GTK e decoração clara
ou escura, sem importar temas globais nem mudar painéis e widgets. Aplicativos
com tema próprio podem exigir configuração individual ou reinicialização.

## Arquivos de instalação

As associações padrão abrem a janela Linux BR de revisão do pacote. DEB tem
nome, versão e arquitetura inspecionados antes de continuar para Discover e
PackageKit. Flatpak e flatpakref também são encaminhados ao Discover. A instalação
pode solicitar autenticação e acesso à rede para dependências.

RPM, MSI e EXE abrem uma explicação de incompatibilidade; não são convertidos nem
executados. AppImage é identificado como portátil e não é instalado por esta
interface. Formatos desconhecidos não são executados. Associações pessoais já
configuradas pelo usuário podem prevalecer sobre os padrões do sistema.

## Validação realizada em 19/10/2026

Passaram os testes de terminal, layout inicial do painel, configurações do
terminal, Central, layout compacto e integração de proxy/instalador/aparência.
Também passou a compilação sintática dos módulos Python e do hook Bash.

Uma VM descartável, sem rede e com a ISO existente somente para leitura, recebeu
os arquivos atuais por overlay de teste. Foram observados:

- painel com `floating=false`, inclusive com todas as janelas minimizadas;
- prompt com letras apesar de preferência antiga pelo modo Linux;
- controles Aurorae renderizados, maximizar/restaurar, minimizar e menu do título;
- aplicação do modo escuro e decoração correspondente;
- associação DEB, revisão dos metadados e encaminhamento ao Discover;
- lista Installed do Discover com 160 itens.

Capturas em `.cache/settings-vm.sd3q7708/`. O script
`tests/settings-vm-smoke.py` prepara uma sessão supervisionada; não declara
aprovação automática das interações visuais. A VM não tinha rede: não foi
concluída instalação de pacote nem testada conectividade Wi-Fi, Bluetooth,
impressoras ou acesso remoto. A ISO final ainda precisa ser reconstruída com
`./init-build.sh`; os testes com overlay não substituem a validação dessa ISO.

A decoração segue o formato público [Aurorae do KDE](https://develop.kde.org/docs/plasma/aurorae/), com desenhos originais do Linux BR.

## Refinamento de navegação, energia e controles

O prompt padrão do terminal é apenas `> `. Usuário e caminho com letra de unidade
ficam no título; caracteres de controle são removidos antes de escrever esse título.
O alinhamento dos títulos permanece à esquerda. A prévia de Personalização muda
imediatamente com a seleção, sem aplicar as cores até clicar em Aplicar.

O plugin Qt 6 Widgets LinuxBRClean mantém o Breeze como base e redesenha os botões:
primário padrão com preenchimento sólido e secundário com contorno na superfície
da janela. Foco e estado desabilitado permanecem visíveis. Os aplicativos Linux BR
usam também estilos explícitos para suas ações primárias. GTK 3/4 recebe a mesma
convenção em `suggested-action`. Aplicativos Qt 5, controles Qt Quick próprios, interfaces web ou controles
próprios não são redesenhados pelo plugin Qt 6.

A Central oferece busca por categoria, descrição e ações, ignorando acentos.
Inclui energia/bateria, notificações, acessibilidade, hora/idioma, entrada/atalhos,
pesquisa/padrões e privacidade/sessão. Energia abre o PowerDevil para ajustar tempo
até apagar a tela, suspensão, tampa e botão de energia, com opções por alimentação
quando disponíveis. O bloqueio automático usa o módulo de bloqueio da sessão.
As configurações avançadas usam módulos KDE em suas próprias janelas: não são uma
reimplementação integral de todas as páginas do Windows. Recursos exclusivos da
Microsoft, como Windows Update, Defender ou BitLocker, não são apresentados como
se existissem no Linux.

O menu Iniciar mantém busca, navegação, favoritos e ações de sessão do Plasma,
com lista de aplicativos e favoritos lado a lado. O painel de configurações
rápidas permite ligar/desligar Wi-Fi e Bluetooth, ajustar o volume da saída padrão,
silenciar e ajustar o brilho de cada tela compatível, sem abrir outra janela.
Os estados são confirmados por NetworkManager, BlueZ, áudio do Plasma e PowerDevil.
Controles indisponíveis ou bloqueados pelo hardware ficam desabilitados; falhas de
alteração dos rádios aparecem no próprio painel. Alterações externas atualizam os
controles e mudar o volume não remove o estado silencioso. O menu “Mais
configurações” mantém acesso a rede/VPN, Bluetooth, áudio, telas, energia e luz
noturna.

O sino permanece acessível no painel e abre o histórico em um painel alto à
direita, com Não perturbe, agrupamento e limpeza oferecidos pelo Plasma. O tempo
padrão dos avisos é 5 segundos; notificações críticas, ações pendentes ou tempos
explicitamente definidos pelo aplicativo seguem as regras do serviço. O histórico
é da sessão; não foi acrescentado um banco persistente entre reinicializações.

As adaptações dos applets são aplicadas pelo postinst e por um trigger quando
arquivos do Plasma são atualizados. `plasma-layout.py` confere os trechos esperados,
é idempotente e mantém uma cópia para restauração. Se uma versão futura mudar um
trecho, aquele arquivo é mantido sem adaptação, com aviso. Ao remover o pacote,
restaura somente arquivos que ainda correspondem ao conteúdo gerado, preservando
mudanças posteriores.

Validação adicional: compilação do plugin Qt 6 em Debian trixie, renderização dos
botões primário/secundário, testes de busca, prévia, terminal, layout do painel e
aplicação/restauração dos patches. Capturas da VM com overlay atual em
`.cache/settings-vm.py98nubs/`. As ações físicas de energia ainda precisam ser
validadas em notebook/hardware compatível. A ISO não foi recompilada nesta etapa.

O timeout segue o [esquema oficial do serviço de notificações do Plasma 6.3](https://raw.githubusercontent.com/KDE/plasma-workspace/Plasma/6.3/libnotificationmanager/kcfg/notificationsettings.kcfg).

## Controles rápidos diretos

O applet usa os módulos QML fornecidos pelos pacotes `plasma-nm`, `bluedevil`,
`plasma-pa`, `powerdevil` e `qml6-module-org-kde-bluezqt`, declarados como
dependências de `linuxbr-desktop`. Não executa comandos de shell a partir dos
controles. O brilho depende das telas que o PowerDevil disponibiliza; ausência de
suporte é informada no painel. O controle de volume fica entre 0 e 100%.

`tests/test-quick-controls.py` exercita a interface com dispositivos simulados,
incluindo bloqueio, ausência, alterações externas e remoção de telas. Precisa de
PyQt6 QtQuick/QtQml e dos módulos QML do Plasma. Não altera dispositivos do host.
`tests/test-quick-controls-native.py` exige uma VM descartável com sessão Plasma,
rádios virtuais e saída de áudio ativa, além de `LINUXBR_DISPOSABLE_VM=1`.
Confere Wi-Fi pelo nmcli, Bluetooth pelo bluetoothctl e volume/mute pelo pactl,
restaurando os estados originais ao terminar.
Execute esse teste a partir da sessão gráfica ativa; quando acionado por um
console de administração da VM, use `systemd-run --user --wait --pipe` no
gerenciador do usuário da sessão. Um processo isolado iniciado com `runuser`
pode ser recusado pelo PolicyKit, mesmo usando o barramento correto.

Na VM de validação, os rádios foram criados com mac80211_hwsim e btvirt, o áudio
usou uma saída PipeWire virtual com fluxo ativo, e o brilho foi ajustado na tela
virtual do KWin. Isso valida a integração dos serviços, não a conectividade ou o
comportamento de hardware físico. A ISO precisa ser reconstruída com
`./init-build.sh` para incluir esses controles.
Captura e resultados desta validação: `.cache/settings-vm.t1lbsuuz/`.

### Seleção de redes e dispositivos no painel

“Redes Wi-Fi” abre uma página interna com as redes disponíveis, atualização da
busca, conexão e desconexão. Perfis salvos reutilizam as credenciais do sistema;
redes pessoais novas exibem um campo de senha no painel, apagado após envio ou
cancelamento. Uma conexão em andamento pode ser cancelada. Redes corporativas
com certificados/802.1X usam a configuração segura do NetworkManager. Na primeira
utilização, o KDE também pode solicitar a configuração ou desbloqueio do cofre de
senhas; o painel não substitui nem desativa essa proteção.

“Dispositivos Bluetooth” lista dispositivos conhecidos e próximos, permite
parear, conectar e desconectar e apresenta erros do BlueZ. Códigos e confirmações
usam o agente de pareamento do KDE. A busca iniciada pelo painel dura até 30
segundos e termina ao sair da página; buscas já iniciadas por outros componentes
não são interrompidas. Dispositivos bloqueados não recebem ações de conexão.

`tests/test-quick-selection.py` testa os caminhos aberta/salva/protegida do Wi-Fi,
desconexão, limpeza do campo de senha e parear/conectar/desconectar Bluetooth com
serviços simulados. As páginas usam os modelos e serviços QML nativos do Plasma,
sem montar comandos de shell com nomes de redes, dispositivos ou senhas.

Validação em `.cache/settings-vm.zlqullka/`: descoberta de rede WPA2 virtual
(mac80211_hwsim + hostapd), conexão pelo painel com DHCP e desconexão confirmadas
pelo NetworkManager. O cofre KDE foi configurado durante o teste. A descoberta
Bluetooth foi conferida com um controlador virtual; pareamento e conexão foram
exercitados com serviços simulados, não com um headset ou telefone físico. A ISO
não foi recompilada nesta alteração.
