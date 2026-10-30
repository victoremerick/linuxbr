# Área de trabalho familiar para quem usa Windows

Implementação de 28/10/2026 no código do pacote `linuxbr-desktop`. **Não foram executados testes, compilação, instalação de pacotes nem geração de ISO neste lote**, conforme solicitado. As alterações abaixo precisam de validação posterior em uma conta nova e em atualização de conta existente.

## Aparência e organização

- Tema claro com destaque azul, superfícies neutras, controles de janela à direita e fonte Noto Sans de 10 pontos. As alternativas violeta, verde, grafite e modo escuro continuam disponíveis. Não são usados logotipos, fontes ou arquivos proprietários da Microsoft.
- As paletas azul, verde e grafite deixam de misturar links e estados ativos violetas; as versões escuras usam cores de texto de destaque mais claras.
- Painel inferior sempre visível, Iniciar à esquerda, aplicativos fixados junto dos abertos e uma linha de tarefas.
- Janelas de um mesmo programa ficam agrupadas. Clicar no grupo solicita as prévias; clicar na janela ativa minimiza; clique do meio solicita uma nova instância. A roda do mouse sobre a barra não troca a janela por acidente.
- Relógio em 24 horas, data `dd/MM/yyyy` abaixo da hora e calendário começando no domingo. Segundos aparecem na dica, sem ocupar espaço fixo na barra.
- Ícones da área de trabalho em colunas a partir do canto superior esquerdo, 48 pixels, renomeação no próprio ícone e abertura por duplo clique. Novas contas recebem links para **Arquivos pessoais** e **Lixeira**.

## Teclado e janelas

`Win` representa a tecla Meta/Super, normalmente marcada com o símbolo Windows no teclado.

| Atalho | Ação configurada |
| --- | --- |
| Win+E | Explorador de arquivos |
| Win+I | Central do Sistema |
| Win+R | Executar do Linux BR |
| Win+X | Menu de acesso rápido |
| Win+S / Alt+F2 | Pesquisa pelo KRunner |
| Win+D | Mostrar/restaurar a área de trabalho |
| Win+L | Bloquear a sessão |
| Ctrl+Shift+Esc | Gerenciador de Tarefas |
| Alt+Space | Menu da janela: mover, redimensionar, minimizar, fechar |
| Alt+F4 | Fechar a janela |
| Win+Esquerda/Direita | Encaixar nas laterais |
| Win+Cima | Maximizar; repetir mantém maximizada |
| Win+Baixo | Restaurar se maximizada; minimizar se já restaurada |
| Win+Shift+Esquerda/Direita | Mover para outra tela |
| Win+M / Win+Shift+M | Minimizar todas/restaurar as minimizadas pelo atalho |
| Win+Tab | Visão de tarefas e áreas de trabalho |
| Win+Ctrl+D | Criar e abrir uma área de trabalho |
| Win+Ctrl+F4 | Remover a área atual, preservando os aplicativos pelo KWin |
| Win+Ctrl+Esquerda/Direita | Alternar áreas de trabalho |
| Win+V | Histórico da área de transferência |
| Print | Captura de tela pelo Spectacle |
| Win+Shift+S | Selecionar região para captura |
| Alt+Print | Capturar a janela ativa |
| Win+Print | Capturar a área de trabalho inteira |

Os atalhos extras de maximização, minimizar todas e criar/remover áreas são implementados pelo script `linuxbr-window-shortcuts`, usando a API do KWin 6. Ele é habilitado apenas em novas contas. Os atalhos de encaixe vertical padrão são liberados para evitar conflito com Cima/Baixo; o atalho de parar atividade que ocupava Win+S é liberado para a pesquisa. Alt+F3 continua disponível para o menu da janela, e Win+W para a visão geral.

Arrastar uma janela para o topo maximiza; arrastar para as laterais permite encaixar; as bordas e os cantos mantêm os encaixes nativos do KWin. O foco muda por clique, com prevenção básica contra roubo de foco, sem ativar automaticamente a janela apenas porque o ponteiro passou sobre ela. O duplo clique no título maximiza/restaura. As barras de título continuam visíveis quando maximizado.

## Arquivos, captura e entrada

- Dolphin abre com navegação por segmentos de pasta, renomeação direta, informações ao passar o ponteiro, barra de estado com espaço livre e zoom. O modo de visualização pode ser lembrado por pasta. Novas aberturas não restauram automaticamente um conjunto antigo de abas.
- Arquivos compactados podem ser navegados; Ark continua como aplicativo padrão para abrir ZIP, 7z, tar e formatos de compressão comuns.
- Abrir e Salvar mantêm a coluna de locais, navegação por segmentos e seleção automática da extensão adequada. Preferências que cada aplicativo controla por conta própria podem diferir.
- Novas contas associam texto a Kate, fotos comuns a Gwenview, áudio/vídeo a VLC, apresentações a Impress, RTF a Writer e CSV a Calc. PDFs continuam no Okular. Associação não promete suporte a todo codec ou documento.
- Capturas são copiadas para a área de transferência, sem salvar arquivos automaticamente. O usuário pode revisar, anotar ou salvar pelo Spectacle. A região precisa ser escolhida a cada captura.
- Histórico de 25 itens copiados, incluindo imagens, disponível na sessão atual. Selecionar um texto não o adiciona automaticamente ao histórico; o histórico não é salvo entre sessões.
- No Wayland, touchpad usa toque para clicar, toque e arraste, rolagem natural e supressão durante digitação. Mouse mantém rolagem convencional. Configurações já salvas por dispositivo têm prioridade.
- Novas contas iniciam uma sessão vazia, preservando os programas explicitamente configurados no início automático, sem restaurar todas as janelas da saída anterior.

## Preservação de preferências

Atalhos, habilitação do script de janelas, sessão inicial e associações ficam em `/etc/skel`, para novos usuários. Preferências de aplicativos em `/etc/xdg` são padrões, subordinados às escolhas gravadas no perfil do usuário.

O inicializador da sessão deixou de reaplicar painel sem flutuação, tema, botões da janela ou novos widgets a cada entrada. Os links iniciais usam um marcador criado com a conta e criação exclusiva: não sobrescrevem arquivos nem reaparecem se o usuário os remover. Uma área de trabalho desabilitada não cria links na pasta pessoal.

O papel de parede inicial também exige marcador de conta nova; atualizar o pacote não aplica o wallpaper sobre uma conta existente que não tenha esse marcador.

O comando de aplicação de tema agora limita as alterações às propriedades de aparência; ele não redefine o navegador padrão, foco das janelas, encaixes, fontes pessoais ou preferência de duplo clique.

## Base técnica consultada

As chaves foram escolhidas a partir dos esquemas e implementações oficiais correspondentes à base KDE 6.3 / Dolphin 24.12, consultados em 28/10/2026:

- [Configuração do gerenciador de tarefas](https://raw.githubusercontent.com/KDE/plasma-desktop/Plasma/6.3/applets/taskmanager/package/contents/config/main.xml), [relógio](https://raw.githubusercontent.com/KDE/plasma-workspace/Plasma/6.3/applets/digital-clock/package/contents/config/main.xml) e [ícones da área de trabalho](https://raw.githubusercontent.com/KDE/plasma-desktop/Plasma/6.3/containments/desktop/package/contents/config/main.xml).
- [Padrões do Dolphin](https://raw.githubusercontent.com/KDE/dolphin/release/24.12/src/settings/dolphin_generalsettings.kcfg) e [diálogos KIO](https://raw.githubusercontent.com/KDE/kio/v6.10.0/src/filewidgets/defaults-kfile.h).
- [Configuração do KWin](https://raw.githubusercontent.com/KDE/kwin/Plasma/6.3/src/kwin.kcfg), [atalhos](https://raw.githubusercontent.com/KDE/kwin/Plasma/6.3/src/useractions.cpp), [propriedades de janela](https://raw.githubusercontent.com/KDE/kwin/Plasma/6.3/src/window.h), [API de áreas de trabalho](https://raw.githubusercontent.com/KDE/kwin/Plasma/6.3/src/scripting/workspace_wrapper.h) e [empacotamento de scripts](https://develop.kde.org/docs/plasma/kwin/).
- [Spectacle](https://raw.githubusercontent.com/KDE/spectacle/release/24.12/src/Gui/SettingsDialog/spectacle.kcfg), [Klipper](https://raw.githubusercontent.com/KDE/plasma-workspace/Plasma/6.3/klipper/klipper.kcfg), [sessões](https://raw.githubusercontent.com/KDE/plasma-desktop/Plasma/6.3/kcms/ksmserver/smserversettings.kcfg) e [padrões Libinput por classe](https://raw.githubusercontent.com/KDE/kwin/Plasma/6.3/src/backends/libinput/connection.cpp).

## Validação deixada para depois

É necessário conferir numa conta nova os atalhos registrados por serviços, a ativação do script KWin, o posicionamento dos elementos em 1280×768, as prévias de grupos, as associações e as capturas. Conferir também monitores múltiplos, entrada por touchpad físico, aplicativos XWayland e atualização preservando preferências. O comportamento de Win+Baixo descrito cobre maximização; janelas em mosaico continuam sujeitas ao estado de encaixe nativo. Nenhum desses fluxos foi executado neste lote.
