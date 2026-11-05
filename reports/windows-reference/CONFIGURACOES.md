# Revisão das Configurações do Windows

Referência: Windows 11 Enterprise Evaluation 26H2, build 26300.9457, pt-BR.

Foram consultadas 182 rotas de configuração. O índice abaixo apresenta 181 rotas, com 125 trilhas distintas nos títulos observados. Rotas específicas de serviços do fornecedor podem estar agrupadas no escopo funcional. A consulta não comprova que cada rota abre uma página exclusiva nem que todas as ações funcionem.

As categorias e os requisitos do Linux BR estão no [planejamento da 0.8.5](ESCOPO-0.8.5.md). A base de navegação é o [catálogo oficial de páginas](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings).

## Limites

- A consulta do catálogo não representa todos os diálogos ou recursos de todas as versões do Windows.
- Windows 10 e recursos exclusivos de Windows Server não foram instalados neste levantamento.
- Hardware ausente, contas externas e opções condicionais exigem revisão adicional.
- A 0.8.5 permanece em planejamento; este relatório não é homologação da implementação.

## Índice observado

| Rota solicitada | Título observado | Registros de controles | Estado |
| --- | --- | ---: | --- |
| `ms-settings:about` | Sistema > Sobre | 99 | Navegação registrada |
| `ms-settings:activation` | Sistema > Ativação | 72 | Navegação registrada |
| `ms-settings:apps-volume` | Sistema > Som > Mixer de volume | 47 | Navegação registrada |
| `ms-settings:appsfeatures-app` | Aplicativos > Aplicativos instalados | 145 | Navegação registrada |
| `ms-settings:appsfeatures` | Aplicativos > Aplicativos instalados | 116 | Navegação registrada |
| `ms-settings:appsforwebsites` | Aplicativos > Aplicativos para sites | 103 | Navegação registrada |
| `ms-settings:assignedaccess` | Contas > Outros usuários > Quiosque | 40 | Navegação registrada |
| `ms-settings:autoplay` | Bluetooth e dispositivos > Reprodução Automática | 52 | Navegação registrada |
| `ms-settings:batterysaver-settings` | Sistema > Energia | 49 | Navegação registrada |
| `ms-settings:batterysaver-usagedetails` | Sistema > Energia | 88 | Navegação registrada |
| `ms-settings:batterysaver` | Sistema > Energia | 94 | Navegação registrada |
| `ms-settings:bluetooth` | Bluetooth e dispositivos > Dispositivos | 72 | Navegação registrada |
| `ms-settings:clipboard` | Sistema > Área de Transferência | 74 | Navegação registrada |
| `ms-settings:colors` | Personalização > Cores | 91 | Navegação registrada |
| `ms-settings:connecteddevices` | Bluetooth e dispositivos > Dispositivos | 72 | Navegação registrada |
| `ms-settings:crossdevice` | Sistema > Compartilhamento por proximidade | 70 | Navegação registrada |
| `ms-settings:dateandtime` | Hora e idioma > Data e hora | 86 | Navegação registrada |
| `ms-settings:defaultapps` | Aplicativos > Aplicativos padrão | 75 | Navegação registrada |
| `ms-settings:delivery-optimization-activity` | Windows Update > Otimização de Entrega | 85 | Navegação registrada |
| `ms-settings:delivery-optimization-advanced` | Windows Update > Otimização de Entrega | 85 | Navegação registrada |
| `ms-settings:delivery-optimization` | Windows Update > Otimização de Entrega | 85 | Navegação registrada |
| `ms-settings:developers` | Sistema > Avançado | 98 | Navegação registrada |
| `ms-settings:deviceencryption` | Privacidade e segurança > Criptografia do dispositivo | 74 | Navegação registrada |
| `ms-settings:devices-touch` | Bluetooth e dispositivos > Impressoras e scanners | 78 | Navegação registrada |
| `ms-settings:devices-touchpad` | Bluetooth e dispositivos > Impressoras e scanners | 78 | Navegação registrada |
| `ms-settings:devicestyping-hwkbtextsuggestions` | Hora e idioma > Digitação | 74 | Navegação registrada |
| `ms-settings:deviceusage` | Personalização > Temas | 82 | Navegação registrada |
| `ms-settings:disksandvolumes` | Sistema > Armazenamento > Discos e volumes | 84 | Navegação registrada |
| `ms-settings:display-advanced` | Sistema > Tela | 87 | Navegação registrada |
| `ms-settings:display-advancedgraphics-default` | Sistema > Tela > Elementos gráficos | 87 | Navegação registrada |
| `ms-settings:display-advancedgraphics` | Sistema > Tela > Elementos gráficos | 87 | Navegação registrada |
| `ms-settings:display` | Sistema > Tela | 86 | Navegação registrada |
| `ms-settings:easeofaccess-audio` | Acessibilidade > Áudio | 73 | Navegação registrada |
| `ms-settings:easeofaccess-closedcaptioning` | Acessibilidade > Legendas | 57 | Navegação registrada |
| `ms-settings:easeofaccess-colorfilter-adaptivecolorlink` | Sistema > Tela | 86 | Navegação registrada |
| `ms-settings:easeofaccess-colorfilter-bluelightlink` | Sistema > Tela > Luz noturna | 62 | Navegação registrada |
| `ms-settings:easeofaccess-colorfilter` | Acessibilidade > Filtros de cor | 75 | Navegação registrada |
| `ms-settings:easeofaccess-cursor` | Acessibilidade > Cursor de texto | 64 | Navegação registrada |
| `ms-settings:easeofaccess-display` | Acessibilidade > Tamanho do texto | 70 | Navegação registrada |
| `ms-settings:easeofaccess-eyecontrol` | Acessibilidade > Controle com os olhos | 66 | Navegação registrada |
| `ms-settings:easeofaccess-hearingaids` | Acessibilidade > Dispositivos auditivos | 66 | Navegação registrada |
| `ms-settings:easeofaccess-highcontrast` | Acessibilidade > Temas de contraste | 76 | Navegação registrada |
| `ms-settings:easeofaccess-keyboard` | Acessibilidade > Teclado | 79 | Navegação registrada |
| `ms-settings:easeofaccess-magnifier` | Acessibilidade > Lupa | 81 | Navegação registrada |
| `ms-settings:easeofaccess-mouse` | Acessibilidade > Mouse | 87 | Navegação registrada |
| `ms-settings:easeofaccess-mousepointer` | Acessibilidade > Ponteiro do mouse e entrada por toque | 84 | Navegação registrada |
| `ms-settings:easeofaccess-narrator-isautostartenabled` | Acessibilidade > Narrador | 75 | Navegação registrada |
| `ms-settings:easeofaccess-narrator` | Acessibilidade > Narrador | 80 | Navegação registrada |
| `ms-settings:easeofaccess-speechrecognition` | Acessibilidade > Fala | 69 | Navegação registrada |
| `ms-settings:easeofaccess-visualeffects` | Acessibilidade > Efeitos visuais | 72 | Navegação registrada |
| `ms-settings:emailandaccounts` | Contas > Suas contas | 66 | Navegação registrada |
| `ms-settings:energyrecommendations` | Sistema > Energia > Recomendações de energia | 56 | Navegação registrada |
| `ms-settings:findmydevice` | Privacidade e segurança > Localizar meu dispositivo | 64 | Navegação registrada |
| `ms-settings:fonts` | Personalização > Fontes | 79 | Navegação registrada |
| `ms-settings:gaming-fullscreen` | Jogos > modo XBOX | 68 | Navegação registrada |
| `ms-settings:gaming-gamebar` | Jogos > Xbox Game Bar | 71 | Navegação registrada |
| `ms-settings:gaming-gamedvr` | Jogos > Capturas | 82 | Navegação registrada |
| `ms-settings:gaming-gamemode` | Jogos > Modo de Jogo | 50 | Navegação registrada |
| `ms-settings:keyboard-advanced` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:keyboard` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:lockscreen` | Personalização > Tela de bloqueio | 68 | Navegação registrada |
| `ms-settings:maps-downloadmaps` | Aplicativos > Mapas offline | 34 | Navegação registrada |
| `ms-settings:maps` | Aplicativos > Mapas offline | 28 | Navegação registrada |
| `ms-settings:mobile-devices` | Bluetooth e dispositivos > Dispositivos móveis | 76 | Navegação registrada |
| `ms-settings:mousetouchpad` | Bluetooth e dispositivos > Mouse | 72 | Navegação registrada |
| `ms-settings:multitasking-sgupdate` | Sistema > Multitarefas | 68 | Navegação registrada |
| `ms-settings:multitasking` | Sistema > Multitarefas | 81 | Navegação registrada |
| `ms-settings:network-advancedsettings` | Rede e Internet > Configurações avançadas de rede | 82 | Navegação registrada |
| `ms-settings:network-airplanemode` | Rede e Internet > Configurações avançadas de rede | 80 | Navegação registrada |
| `ms-settings:network-cellular` | Rede e Internet > Configurações avançadas de rede | 80 | Navegação registrada |
| `ms-settings:network-dialup` | Rede e Internet > Conexão discada | 34 | Navegação registrada |
| `ms-settings:network-directaccess` | Rede e Internet > Conexão discada | 34 | Navegação registrada |
| `ms-settings:network-ethernet` | Mais configurações > Rede e Internet > Ethernet | 104 | Navegação registrada |
| `ms-settings:network-mobilehotspot` | Mais configurações > Rede e Internet > Ethernet | 104 | Navegação registrada |
| `ms-settings:network-proxy` | Rede e Internet > Proxy | 60 | Navegação registrada |
| `ms-settings:network-status` | Rede e Internet | 76 | Navegação registrada |
| `ms-settings:network-vpn` | Rede e Internet > VPN | 66 | Navegação registrada |
| `ms-settings:network-wifi` | Rede e Internet > VPN | 66 | Navegação registrada |
| `ms-settings:network-wifisettings` | Mais configurações > Rede e Internet > Ethernet | 104 | Navegação registrada |
| `ms-settings:nightlight` | Sistema > Tela > Luz noturna | 62 | Navegação registrada |
| `ms-settings:notifications` | Sistema > Notificações | 88 | Navegação registrada |
| `ms-settings:optionalfeatures` | Sistema > Recursos opcionais | 46 | Navegação registrada |
| `ms-settings:otherusers` | Contas > Outros usuários | 52 | Navegação registrada |
| `ms-settings:pen-button` | Bluetooth e dispositivos > Caneta e Windows Ink | 62 | Navegação registrada |
| `ms-settings:pen` | Bluetooth e dispositivos > Caneta e Windows Ink | 62 | Navegação registrada |
| `ms-settings:personalization-background` | Personalização > Tela de fundo | 75 | Navegação registrada |
| `ms-settings:personalization-colors` | Personalização > Cores | 91 | Navegação registrada |
| `ms-settings:personalization-lighting` | Personalização > Iluminação Dinâmica | 73 | Navegação registrada |
| `ms-settings:personalization-start-places` | Personalização > Iniciar > Pastas | 60 | Navegação registrada |
| `ms-settings:personalization-start` | Personalização > Iniciar | 71 | Navegação registrada |
| `ms-settings:personalization-textinput` | Personalização > Entrada de texto | 114 | Navegação registrada |
| `ms-settings:personalization-touchkeyboard` | Personalização > Entrada de texto | 104 | Navegação registrada |
| `ms-settings:personalization` | Personalização | 85 | Navegação registrada |
| `ms-settings:powersleep` | Sistema > Energia | 94 | Navegação registrada |
| `ms-settings:presence` | Sistema > Energia | 88 | Navegação registrada |
| `ms-settings:printers` | Bluetooth e dispositivos > Impressoras e scanners | 81 | Navegação registrada |
| `ms-settings:privacy-accountinfo` | Privacidade e segurança > Informações da conta | 86 | Navegação registrada |
| `ms-settings:privacy-activityhistory` | Privacidade e segurança > Informações da conta | 86 | Navegação registrada |
| `ms-settings:privacy-appdiagnostics` | Privacidade e segurança > Diagnóstico de aplicativos | 62 | Navegação registrada |
| `ms-settings:privacy-automaticfiledownloads` | Privacidade e segurança > Downloads automáticos de arquivos | 70 | Navegação registrada |
| `ms-settings:privacy-backgroundspatialperception` | Privacidade e segurança > Downloads automáticos de arquivos | 70 | Navegação registrada |
| `ms-settings:privacy-broadfilesystemaccess` | Privacidade e segurança > Sistema de arquivos | 70 | Navegação registrada |
| `ms-settings:privacy-calendar` | Privacidade e segurança > Calendário | 62 | Navegação registrada |
| `ms-settings:privacy-callhistory` | Privacidade e segurança > Histórico de chamadas | 62 | Navegação registrada |
| `ms-settings:privacy-contacts` | Privacidade e segurança > Contatos | 72 | Navegação registrada |
| `ms-settings:privacy-customdevices` | Privacidade e segurança > Outros dispositivos | 67 | Navegação registrada |
| `ms-settings:privacy-documents` | Privacidade e segurança > Documentos | 72 | Navegação registrada |
| `ms-settings:privacy-downloadsfolder` | Privacidade e segurança > Pasta Downloads | 62 | Navegação registrada |
| `ms-settings:privacy-email` | Privacidade e segurança > Email | 84 | Navegação registrada |
| `ms-settings:privacy-eyetracker` | Privacidade e segurança > Email | 84 | Navegação registrada |
| `ms-settings:privacy-feedback` | Privacidade e segurança > Diagnóstico e comentários | 89 | Navegação registrada |
| `ms-settings:privacy-general` | Privacidade e segurança > Recomendações & ofertas | 85 | Navegação registrada |
| `ms-settings:privacy-graphicscaptureprogrammatic` | Privacidade e segurança > Capturas de tela e gravação de tela | 88 | Navegação registrada |
| `ms-settings:privacy-graphicscapturewithoutborder` | Privacidade e segurança > Bordas da captura de tela | 86 | Navegação registrada |
| `ms-settings:privacy-location` | Privacidade e segurança > Localização | 90 | Navegação registrada |
| `ms-settings:privacy-messaging` | Privacidade e segurança > Sistema de Mensagens | 72 | Navegação registrada |
| `ms-settings:privacy-microphone` | Privacidade e segurança > Microfone | 93 | Navegação registrada |
| `ms-settings:privacy-motion` | Privacidade e segurança > Microfone | 94 | Navegação registrada |
| `ms-settings:privacy-musiclibrary` | Privacidade e segurança > Biblioteca de músicas | 51 | Navegação registrada |
| `ms-settings:privacy-notifications` | Privacidade e segurança > Notificações | 62 | Navegação registrada |
| `ms-settings:privacy-phonecalls` | Privacidade e segurança > Chamadas telefônicas | 72 | Navegação registrada |
| `ms-settings:privacy-pictures` | Privacidade e segurança > Imagens | 80 | Navegação registrada |
| `ms-settings:privacy-radios` | Privacidade e segurança > Rádios | 62 | Navegação registrada |
| `ms-settings:privacy-speech` | Privacidade e segurança > Controle por Voz | 50 | Navegação registrada |
| `ms-settings:privacy-speechtyping` | Privacidade e segurança > Personalização de escrita à tinta e digitação | 60 | Navegação registrada |
| `ms-settings:privacy-tasks` | Privacidade e segurança > Tarefas | 62 | Navegação registrada |
| `ms-settings:privacy-videos` | Privacidade e segurança > Vídeos | 80 | Navegação registrada |
| `ms-settings:privacy-voiceactivation` | Privacidade e segurança > Ativação de voz | 76 | Navegação registrada |
| `ms-settings:privacy-webcam` | Privacidade e segurança > Câmera | 86 | Navegação registrada |
| `ms-settings:privacy` | Privacidade e segurança | 76 | Navegação registrada |
| `ms-settings:project` | Sistema > Projeção para este computador | 42 | Navegação registrada |
| `ms-settings:proximity` | Rede e Internet > Configurações avançadas de rede | 80 | Navegação registrada |
| `ms-settings:quiethours` | Sistema > Foco | 70 | Navegação registrada |
| `ms-settings:recovery` | Sistema > Recuperação | 85 | Navegação registrada |
| `ms-settings:regionformatting` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-bpmfime` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-cangjieime` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-chsime-pinyin-domainlexicon` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-chsime-pinyin-keyconfig` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-chsime-pinyin-udp` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-chsime-pinyin` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-chsime-wubi-udp` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-chsime-wubi` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-jpnime` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-korime` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage-quickime` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:regionlanguage` | Hora e idioma > Idioma e região | 89 | Navegação registrada |
| `ms-settings:remotedesktop` | Sistema > Área de Trabalho Remota | 66 | Navegação registrada |
| `ms-settings:savelocations` | Sistema > Armazenamento > Onde o novo conteúdo é salvo | 51 | Navegação registrada |
| `ms-settings:screenrotation` | Sistema > Tela | 86 | Navegação registrada |
| `ms-settings:search-moredetails` | Privacidade e segurança > Pesquisar | 84 | Navegação registrada |
| `ms-settings:search-permissions` | Privacidade e segurança > Pesquisar | 86 | Navegação registrada |
| `ms-settings:search` | Privacidade e segurança > Pesquisar | 86 | Navegação registrada |
| `ms-settings:signinoptions-dynamiclock` | Contas > Opções de entrada | 79 | Navegação registrada |
| `ms-settings:signinoptions` | Contas > Opções de entrada | 86 | Navegação registrada |
| `ms-settings:sound-defaultinputproperties` | Sistema > Som > Propriedades | 109 | Navegação registrada |
| `ms-settings:sound-defaultoutputproperties` | Sistema > Som > Propriedades | 107 | Navegação registrada |
| `ms-settings:sound-devices` | Sistema > Som > Todos os dispositivos de som | 62 | Navegação registrada |
| `ms-settings:sound-properties` | Sistema > Som | 94 | Navegação registrada |
| `ms-settings:sound` | Sistema > Som | 52 | Navegação registrada |
| `ms-settings:speech` | Hora e idioma > Fala | 59 | Navegação registrada |
| `ms-settings:startupapps` | Aplicativos > Inicialização | 104 | Navegação registrada |
| `ms-settings:storagepolicies` | Sistema > Armazenamento > Sensor de armazenamento | 52 | Navegação registrada |
| `ms-settings:storagerecommendations` | Sistema > Armazenamento | 84 | Navegação registrada |
| `ms-settings:storagesense` | Sistema > Armazenamento | 84 | Navegação registrada |
| `ms-settings:taskbar` | Personalização > Barra de Tarefas | 52 | Navegação registrada |
| `ms-settings:themes` | Personalização > Temas | 92 | Navegação registrada |
| `ms-settings:troubleshoot` | Sistema > Solução de Problemas | 80 | Navegação registrada |
| `ms-settings:typing` | Hora e idioma > Digitação | 38 | Navegação registrada |
| `ms-settings:usb` | Bluetooth e dispositivos > USB | 36 | Navegação registrada |
| `ms-settings:videoplayback` | Aplicativos > Reprodução de vídeo | 74 | Navegação registrada |
| `ms-settings:windowsdefender` | Privacidade e segurança > Segurança do Windows | 87 | Navegação registrada |
| `ms-settings:windowsinsider` | Windows Update > Programa Windows Insider | 62 | Navegação registrada |
| `ms-settings:windowsupdate-activehours` | Windows Update > Opções avançadas | 84 | Navegação registrada |
| `ms-settings:windowsupdate-history` | Windows Update > Histórico de atualização | 77 | Navegação registrada |
| `ms-settings:windowsupdate-optionalupdates` | Windows Update > Atualizações opcionais | 26 | Navegação registrada |
| `ms-settings:windowsupdate-options` | Windows Update > Opções avançadas | 84 | Navegação registrada |
| `ms-settings:windowsupdate-restartoptions` | Windows Update | 101 | Navegação registrada |
| `ms-settings:windowsupdate` | Windows Update | 81 | Navegação registrada |
| `ms-settings:workplace` | Contas > Acessar trabalho ou escola | 76 | Navegação registrada |
| `ms-settings:yourinfo` | Contas > Suas informações | 75 | Navegação registrada |
