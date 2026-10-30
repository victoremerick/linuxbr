# Biblioteca de programas Windows — implementação de 28/10/2026

Esta rodada melhora o uso de programas Windows no Linux BR. As alterações estão no código-fonte; os testes, a geração de pacotes e uma nova ISO ficaram para outra etapa, conforme solicitado. A descrição abaixo não representa homologação de compatibilidade com novos programas.

## O que mudou

A ferramenta **Programas Windows e jogos** agora abre na biblioteca **Meus programas** do ambiente selecionado. É possível pesquisar, abrir com duplo clique ou Enter, abrir o local do arquivo, renomear o atalho e remover somente o atalho. Os mesmos programas ficam disponíveis no menu Iniciar. O menu de contexto oferece essas ações com o botão direito.

**Localizar instalados** procura executáveis em `Program Files`, `Program Files (x86)` e nas pastas de programas instalados na conta Windows do ambiente. A procura ocorre em um processo separado, sem travar a janela. A pessoa escolhe quais executáveis quer adicionar; nenhum programa encontrado é iniciado automaticamente. A pesquisa omite nomes comuns de instaladores, desinstaladores e atualizadores, mas ainda pode listar componentes auxiliares. O limite é de 250 candidatos e 2.000 diretórios por busca.

**Adicionar EXE** também aceita programas portáteis. O atalho guarda a localização do executável, sem copiá-lo. Mover ou apagar sua pasta depois de criar o atalho exige adicioná-lo novamente. A lista identifica arquivos que não estão mais disponíveis. MSI continua sendo um instalador: não é cadastrado como programa da biblioteca.

Cada ambiente pode ser renomeado e escolhido como **padrão** para as próximas aberturas de instaladores. Essa preferência não altera o ambiente dos atalhos já cadastrados. Programas x64 continuam recusados em ambientes de 32 bits.

A página **Instalar / configurar** reúne o instalador, Downloads, a Loja, Winecfg, dependências, unidade C: e os registros. Arrastar um único EXE ou MSI para a janela seleciona o arquivo e abre essa página; a execução ainda depende do botão **Abrir / instalar**. `Ctrl+O` escolhe um arquivo, `Ctrl+F` pesquisa a biblioteca e `F5` atualiza a lista.

**Dependências** abre a interface do Winetricks no ambiente selecionado, após explicar a ação. **Encerrar programas travados** pede confirmação e encerra os processos Wine daquele ambiente. Trabalho não salvo nesses programas pode ser perdido. A ação não apaga o ambiente nem seus documentos.

**Jogos e controles** reúne Steam, modo Big Picture, Bottles, Bluetooth, áudio, telas, informações Vulkan e drivers. A consulta da instalação do Bottles agora ocorre em segundo plano, com limite de tempo; o download opcional pelo Flathub precisa de confirmação dentro da interface.

**Ajuda de compatibilidade** explica arquitetura, executáveis portáteis, dependências, atualizações, arquivos salvos, drivers, antitrapaça e limites de Wine/Proton. Não existe promessa de que todos os programas Windows funcionam. O botão direito no iniciador da ferramenta também oferece atalhos diretos para instalar um programa ou abrir a página de jogos.

## Dados preservados e integração

- Ambientes existentes continuam em `$XDG_DATA_HOME/linuxbr/windows/environments/<UUID>/`, ou `~/.local/share/linuxbr/windows/environments/<UUID>/`.
- O ambiente padrão fica em `linuxbr/windows/preferences.json`.
- Os registros dos atalhos ficam em `linuxbr/windows/programs/<UUID>.json`.
- Os arquivos de menu têm o nome `linuxbr-windows-<UUID>.desktop` no diretório de aplicações da conta.
- O campo `Exec` dos atalhos contém apenas o comando fixo `/usr/bin/linuxbr-windows --launch <UUID>`. Nomes e caminhos escolhidos pelo usuário não são interpolados em comandos de shell.
- Metadados são gravados em arquivo temporário e substituídos de forma atômica, com permissões de usuário.
- Remover atalho elimina somente o registro e o arquivo de menu criado pela ferramenta. Não desinstala programas, não remove ambientes e não interfere nos atalhos criados pelo próprio Wine.
- A descoberta não segue links simbólicos de diretórios; ela não percorre a unidade Z: nem documentos pessoais.
- Ambientes Bottles e jogos Proton continuam sendo administrados pelas ferramentas correspondentes.
- Não há nova dependência de biblioteca Python ou novo executável em `/usr/bin`. São reaproveitados PyQt6, Wine, Winetricks, Flatpak, Steam, Konsole e os módulos KDE já utilizados pela distribuição. Quando uma ferramenta opcional não estiver instalada, a interface informa sua ausência.

## Fontes oficiais usadas na implementação

Consultadas em 28/10/2026:

- [Valve: Steam Hardware and Proton](https://partner.steamgames.com/doc/steamhardware/proton). O suporte a antitrapaça depende da integração do desenvolvedor; a Valve descreve limitações para soluções que exigem componentes do kernel Windows e outros obstáculos de compatibilidade.
- [Steam: modo Big Picture](https://help.steampowered.com/en/faqs/view/3725-76D3-3F31-FB63). Modo de interface para TV e controle.
- [Steam Input: primeiros passos para jogadores](https://partner.steamgames.com/doc/features/steam_controller/getting_started_for_players). Configuração de controles pelo cliente Steam.
- [Bottles: projeto oficial](https://usebottles.com/). Ambientes, versões de Wine/Proton e componentes gráficos administrados por aplicativo; Flatpak é a distribuição recomendada pelo projeto.
- [Winetricks: código publicado pelo Debian](https://sources.debian.org/src/winetricks/20250102-1/src/winetricks/). Interface de seleção de componentes usando o ambiente Wine definido pelo chamador.

## Verificações reservadas para a próxima etapa

Não foram executadas nesta rodada: abertura da interface em 1280×768, criação e lançamento real de atalhos, descoberta em ambientes existentes, comportamento dos diálogos, encerramento de aplicativos, execução de Wine/Steam/Bottles, testes automatizados e construção da ISO. A suíte antiga também deverá acompanhar as novas páginas e a recusa de criação de ambientes por root.

A biblioteca registra executáveis, sem analisar atalhos `.lnk`, extrair ícones de EXE ou importar parâmetros de inicialização personalizados. Programas que dependem desses parâmetros podem continuar usando os atalhos criados pelo instalador ou ser administrados pelo Bottles. A descoberta de um EXE demonstra que o arquivo existe, não que o programa seja compatível.

## Complemento: multimídia e periféricos em programas de 32 bits

O hook da imagem instala Wine com `--no-install-recommends`. A pesquisa da ficha oficial de `libwine` no Debian Trixie confirmou que essa escolha deixa de instalar recomendações usadas em vídeo, impressão e dispositivos. Bibliotecas equivalentes de 64 bits não satisfazem um processo Wine de 32 bits.

Acrescentados explicitamente ao hook `0150-linuxbr-windows.hook.chroot`, com disponibilidade i386 confirmada no catálogo oficial Trixie:

| Pacote i386 | Motivo |
| --- | --- |
| `gstreamer1.0-plugins-good` | Conjunto recomendado por libwine; também instala o conjunto base necessário ao pipeline de reprodução. |
| `gstreamer1.0-plugins-bad` | Parsers e formatos adicionais usados por pipelines multimídia; sugerido pelo pacote libwine. |
| `gstreamer1.0-plugins-ugly` | Formatos legados e componentes adicionais, também sugeridos por libwine. |
| `gstreamer1.0-libav` | Decodificadores FFmpeg integrados ao GStreamer, sugeridos por libwine. |
| `libcups2t64` | Biblioteca recomendada pelo Wine para comunicar-se com a impressão configurada no Linux. |
| `libsdl2-2.0-0` | Biblioteca recomendada pelo Wine para sua integração com dispositivos e entrada SDL. |
| `libv4l-0t64` | Biblioteca recomendada pelo Wine para integração com vídeo/captura Video4Linux. |

Esses componentes completam a infraestrutura da imagem. Não instalam drivers Windows, não substituem exigências do aplicativo e não alteram os runtimes gerenciados por Steam ou Bottles Flatpak. Os pacotes nativos de multimídia permanecem na lista principal da distribuição. Não foi feita instalação, resolução experimental pelo APT, reprodução de mídia ou teste de periférico nesta rodada; tudo isso permanece pendente.

Fontes primárias adicionais, consultadas em 28/10/2026:

- [Debian Trixie: libwine, dependências, recomendações e sugestões](https://packages.debian.org/trixie/libwine)
- [Debian: GStreamer good](https://packages.debian.org/trixie/gstreamer1.0-plugins-good), [bad](https://packages.debian.org/trixie/gstreamer1.0-plugins-bad), [ugly](https://packages.debian.org/trixie/gstreamer1.0-plugins-ugly) e [libav](https://packages.debian.org/trixie/gstreamer1.0-libav)
- [Debian i386: CUPS](https://packages.debian.org/trixie/i386/libcups2t64), [SDL2](https://packages.debian.org/trixie/i386/libsdl2-2.0-0) e [Video4Linux](https://packages.debian.org/trixie/i386/libv4l-0t64)
- [Bottles: documentação sobre vídeos e plugins GStreamer](https://github.com/bottlesdevs/documentation/blob/master/faq/video-gstreamer-problems.md)

## Complemento: abertura de arquivos no instalador

O instalador de arquivos locais agora aceita arrastar um único DEB, Flatpak, Flatpakref, EXE ou MSI para revisão. `Ctrl+O` abre o seletor. Arrastar ou escolher o arquivo não inicia sua execução: o botão permanece como etapa explícita de continuação. A tela mostra também a pasta de origem.

Para EXE/MSI, o botão passa a dizer **Escolher ambiente Wine…** e explica que a confirmação ocorre na ferramenta Windows, sem sudo. Pacotes Linux continuam sendo encaminhados ao Discover. A ausência do arquivo tem mensagem própria em português. AppImage permanece fora desse fluxo e é informado como formato não instalável por essa ferramenta. Nenhum teste ou instalação foi executado nesta alteração.
