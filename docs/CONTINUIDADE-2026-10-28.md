# Continuidade — personalização Windows, 28/10/2026

## Novos requisitos registrados em 29/10/2026

Solicitações do usuário registradas para evolução. Implementadas em código-fonte
em 30/10/2026, versão 0.4.8, com validação ainda adiada:

- O terminal deve mostrar a localização atual dentro da própria área de comandos,
  no prompt, atualizando o caminho após cada mudança de pasta. O título da janela
  não deve ser necessário para identificar a localização.
  A apresentação deve usar a referência de caminhos do Windows: letra de unidade,
  dois-pontos e barras invertidas, conforme as unidades e os locais do Linux BR.
  Usar o mesmo mapeamento do gerenciador de arquivos, inclusive para unidades de
  rede; não inventar um caminho visual sem correspondência com a pasta aberta.
  A evolução deve contemplar navegação por esses caminhos, além da apresentação
  do prompt, para manter coerência entre o endereço mostrado e o que se pode digitar.
- Aplicativos web devem usar o favicon da página para facilitar a identificação.
  Obter o ícone do site, mantendo alternativa quando indisponível.
- O Gerenciador de Tarefas deve ser um aplicativo independente, com janela própria,
  em vez de uma página agregada às configurações. Incluir a entrada no menu de
  contexto da barra de tarefas. Ctrl+Shift+Esc deve abrir esse aplicativo diretamente.
- Ctrl+Alt+Del deve abrir uma tela de ações de sessão inspirada na imagem enviada:
  fundo azul em tela inteira, lista central com Bloquear, Trocar usuário, Sair,
  Alterar uma senha e Gerenciador de Tarefas, além de Cancelar.
  Cancelar/Esc retorna à sessão sem executar outra ação; o Gerenciador de Tarefas
  abre o aplicativo independente. As ações devem usar os mecanismos reais de
  sessão e autenticação do Linux, respeitando o tipo de conta e as permissões.
  Esta tela é uma interface de ações da sessão; não deve alegar as garantias da
  sequência de atenção segura do Windows. Evitar conflito com o atalho de saída
  atualmente registrado pelo Plasma.

Referência visual fornecida pelo usuário:
`C:/Users/emeri/AppData/Local/Temp/codex-clipboard-1a981f21-b841-499c-997e-3d3f86821c34.png`.
Detalhes e limites da implementação: [sessão, terminal e ícones](IMPLEMENTACAO-SESSAO-2026-10-30.md).
Não foram executados testes nem criada uma nova ISO nesta etapa.

## Pedido em vigor

Trabalhar na distribuição Linux BR com aparência e uso familiar para brasileiros
acostumados ao Windows, pesquisando fontes oficiais para descobrir lacunas.
Encerrar às 23:50 America/Sao_Paulo ou no limite da cota e retomar às 23h do dia
seguinte. O agendamento diário das 23h foi pausado a pedido do usuário em
29/10/2026; a próxima execução foi cancelada. Não retomar automaticamente
enquanto esse agendamento permanecer pausado.

O usuário pediu explicitamente que os testes ficassem para outro momento.
**Não executar testes, compilações, criação de ISO nem ensaios de VM nesta etapa.**
Quando houver autorização para testar, priorizar UEFI em 1280×768; BIOS somente
ao final. Não confundir versões de fonte com imagens construídas ou validadas.

## Estado de entrega

- Fonte em desenvolvimento: **0.4.8**, incluindo a implementação de 30/10, sem execução.
- Última ISO construída: **0.4.4**, preservada em `dist/` no host Fedora.
- Último pacote de sistema exercitado em VM UEFI: **0.4.6**, dos perfis web.
- Nenhum pacote ou ISO 0.4.7/0.4.8 foi produzido nestas etapas de edição.
- Alterações anteriores e dados de perfis web/Wine devem permanecer intactos.
- Não houve commit, push ou publicação neste lote. O checkout remoto já tinha
  diversas alterações locais; não usar reset/clean para reorganizá-lo.

## Implementações desta etapa

### Área de trabalho

Padrões de contas novas: tema claro azul, barra inferior, agrupamento e prévias
de janelas, clique para minimizar, relógio de 24h e data brasileira. Atalhos para
Executar, acesso rápido, pesquisa, histórico de cópia, captura de região e visão
de tarefas. Script KWin para maximizar/restaurar/minimizar e áreas de trabalho.
O autostart deixa de reaplicar preferências do painel e da decoração sobre
escolhas do usuário. Associações de documentos, fotos, áudio, vídeo e arquivos
compactados e preferências do Dolphin foram ampliadas.

Detalhes e fontes: [implementação desktop](DESKTOP-WINDOWS-IMPLEMENTACAO.md).

### Executar, Central e guia

`linuxbr-run` usa o novo `run_dialog.py`. Nomes como control, notepad, calc,
mspaint, taskmgr, appwiz.cpl, ncpa.cpl, mmsys.cpl, devmgmt.msc e diskmgmt.msc
abrem equivalentes nativos. Também há pastas especiais, endereços web/SMB,
letras de unidade e seleção de arquivos. EXE/MSI passa pelo gerenciador Wine.
Não usa shell implícito nem grava histórico de comandos ou URLs.

`linuxbr-quick-access` abre o painel de ferramentas para Windows+X.
O URI existente `linuxbr-action:/run` usa o mesmo diálogo de Executar.
A Central ganhou Arquivos e atalhos, digitalização, análise de espaço, firmware
via Discover e links diretos às abas da compatibilidade Windows.

O guia offline agora aponta para a Loja Linux BR e Chromium, explica os novos
atalhos, equivalentes de aplicativos, fontes/documentos Office, unidades de rede
e perfis independentes de aplicativos web. Fluxo dos perfis 0.4.6 preservado:
um perfil abre direto; vários apresentam seleção múltipla; Novo perfil abre
outra janela com dados próprios e nome escolhido pelo usuário.

### Arquivos e loja

Assistente de atalhos Type=Link sem comandos arbitrários, copiar caminho e UNC,
mapear rede pelo mesmo serviço de letras de unidade, modelos TXT/Markdown/RTF.
Catálogo ampliado em 11 nativos: 29 Linux + 7 web + 2 Windows = 38 entradas.
Nativos com executável conhecido ganham Abrir aplicativo e mantêm gerenciamento
no Discover. Mapeamento local fixo, sem executar conteúdo do catálogo.

Detalhes e fontes: [arquivos e loja](ARQUIVOS-WINDOWS-IMPLEMENTACAO.md).

### Windows e jogos

Biblioteca de programas instalados e portáteis, atalhos no menu, descoberta de
EXEs em segundo plano, ambiente padrão persistente, renomear ambientes/atalhos,
arrastar instaladores, atalhos de teclado, recuperação de programas travados e
orientações por cenário. Remover um atalho não remove o programa ou ambiente.
O hook i386 inclui bibliotecas multimídia e de periféricos omitidas anteriormente
por `--no-install-recommends`. Não foram adicionados downloads avulsos de DLLs.

Detalhes e fontes: [compatibilidade](COMPATIBILIDADE-WINDOWS-IMPLEMENTACAO.md).

### Aplicativos e documentos

Lista de imagem ampliada com Impress/Draw, KCalc, Kate, KolourPaint, Gwenview,
Okular, Ark, 7zip/zip/unzip, VLC, Skanpage, Filelight, fontes Carlito/Caladea/
Liberation, IPP-over-USB, AirScan, CUPS browsed, firmware via fwupd/Discover
e codecs GStreamer. São seleções para a próxima imagem, não instalações
efetuadas na VM atual. O empacotamento declara KCalc/Kate/KolourPaint e marca
os novos launchers como executáveis.

O complemento final inclui plugins Qt6/KDE6 de formatos de imagem e
FFMpegThumbs, com associações de HEIF/HEIC/AVIF/JXL ao Gwenview. A escolha
`kimageformat6-plugins` é específica do Frameworks 6; o pacote sem o 6 ainda
é da geração anterior. Não foi executado teste com arquivos de câmera.
Ajuda offline do LibreOffice e dicionário de sinônimos em português brasileiro
complementam o corretor ortográfico e a hifenização já presentes.
O instalador também aceita arrastar um arquivo compatível para revisão e Ctrl+O;
EXE/MSI mostra a próxima etapa de escolha do ambiente Wine, sem executar no drop.

`linuxbr-system/files/etc/skel/.config/libreoffice/4/user/registrymodifications.xcu`
prepara Em abas para Writer/Calc/Impress/Draw, recuperação em cinco minutos,
cópia de segurança e avisos de formato. Não altera perfis LibreOffice existentes
e não habilita sobrescrita automática do documento original.

## Pesquisa adicional usada pelo integrador

- [Pacotes Debian Trixie](https://packages.debian.org/trixie/): nomes e disponibilidade
  foram consultados por pacote, em especial [KCalc](https://packages.debian.org/trixie/kcalc),
  [KolourPaint](https://packages.debian.org/trixie/kolourpaint),
  [Skanpage](https://packages.debian.org/trixie/skanpage) e [7zip](https://packages.debian.org/trixie/7zip).
- [Firmware no Discover](https://packages.debian.org/trixie/plasma-discover-backend-fwupd),
  [IPP USB](https://packages.debian.org/trixie/ipp-usb),
  [AirScan](https://packages.debian.org/trixie/sane-airscan),
  [CUPS browsed](https://packages.debian.org/trixie/cups-browsed),
  [GStreamer libav](https://packages.debian.org/trixie/gstreamer1.0-libav).
- [Carlito](https://packages.debian.org/trixie/fonts-crosextra-carlito),
  [Caladea](https://packages.debian.org/trixie/fonts-crosextra-caladea) e
  [Liberation](https://packages.debian.org/trixie/fonts-liberation).
- [Formatos KDE6](https://packages.debian.org/trixie/kimageformat6-plugins),
  [formatos Qt6](https://packages.debian.org/trixie/qt6-image-formats-plugins) e
  [miniaturas de vídeo](https://packages.debian.org/trixie/ffmpegthumbs).
- [Ajuda pt-BR](https://packages.debian.org/trixie/libreoffice-help-pt-br) e
  [sinônimos pt-BR](https://packages.debian.org/trixie/mythes-pt-br).
- [NTFS, hibernação e Inicialização Rápida](https://manpages.debian.org/trixie/ntfs-3g/ntfs-3g.8.en.html):
  explicação adicionada ao guia de recuperação, sem forçar montagem ou remover
  arquivos de hibernação. Uma melhoria futura é contextualizar essa orientação
  diretamente no erro do gerenciador de unidades.
- [Interface LibreOffice 25.2](https://books.libreoffice.org/en/CG252/CG25217-UserInterfaceVariants.html)
  e schemas oficiais [ToolbarMode](https://github.com/LibreOffice/core/blob/libreoffice-25.2.3.2/officecfg/registry/data/org/openoffice/Office/UI/ToolbarMode.xcu)
  e [Recovery](https://github.com/LibreOffice/core/blob/libreoffice-25.2.3.2/officecfg/registry/schema/org/openoffice/Office/Recovery.xcs).

## Continuação

1. Ler os registros e mudanças atuais; não refazer o fluxo de perfis já implementado.
2. Continuar implementando detalhes de uso diário, com pesquisa oficial e sem
   alegar compatibilidade universal ou testes que não ocorreram.
3. Áreas para investigar: ajuda de migração de documentos, opções de backup com
   interface gráfica, associação de aplicativos portáteis, formatos de imagem de
   celulares, compartilhamento com outras máquinas, acessibilidade e escalas,
   preferências por aplicativo e experiências em hardware real.
4. Manter validação para uma etapa autorizada: dependências APT amd64/i386,
   GUI Qt, inicialização KWin e conflitos de teclas, associações, perfis Office,
   atualização de conta existente, compilação completa e UEFI antes de BIOS.
5. Não publicar ou substituir a ISO anterior antes dessa validação.

## Acesso e preservação

Host de desenvolvimento Fedora: `emericv@192.168.0.131`, SSH porta 2222,
repositório `/home/emericv/git/linuxbr`, branch `codex/customizacao-brasileira`.
Chave local: `C:/Users/emeri/.codex/tmp/linuxbr-dev-key`; known-hosts:
`C:/Users/emeri/.codex/tmp/linuxbr-known-hosts`. SCP usa `-O`.
O helper local `C:/Users/emeri/.codex/tmp/remote-control.mjs` recebe bash em stdin.

Snapshot remoto anterior a este lote:
`~/.local/state/linuxbr-dev-ssh/linuxbr-before-windows-polish-20261028-2334.tar.gz`.
Contém a árvore de fontes anterior, excluindo .git, .cache, build e dist.
Os serviços de inibição do host preparados anteriormente devem ser preservados;
não encerrar a sessão nem reiniciar a máquina durante o trabalho.

Integração inicial de 64 arquivos realizada às 23:43, seguida do complemento
final do instalador e formatos. Integridade de transferência conferida por hashes,
sem executar os programas. Serviços `linuxbr-work-inhibit.service` e
`linuxbr-work-session.service` estavam ativos na consulta das 23:43.
O manifesto de transferência fica em
`~/.local/state/linuxbr-dev-ssh/linuxbr-polish-manifest.json` no host remoto.
