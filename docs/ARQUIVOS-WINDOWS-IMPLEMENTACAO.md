# Arquivos e atalhos familiares

Implementação de 28/10/2026, entregue em código-fonte. **Ainda não executada ou testada**, conforme a orientação de priorizar implementação nesta etapa. A presença destes arquivos no repositório não significa que já estejam na ISO publicada.

## O que foi acrescentado

O aplicativo **Arquivos e atalhos** reúne criar atalhos, mapear unidades de rede, abrir Este computador e abrir a Lixeira. Também explica atalhos de teclado do Explorador em português. O menu de aplicativos oferece ações diretas para criar um atalho ou mapear uma unidade.

### Criar atalho

O assistente permite escolher um arquivo, pasta, unidade do Linux BR, compartilhamento SMB ou site HTTP/HTTPS. Sugere o nome do item e a área de trabalho da conta como destino; ambos podem ser alterados. Ao clicar em Criar atalho, grava um arquivo `.desktop` do tipo `Link`, com o endereço do item. Não move o original. Nomes repetidos recebem um número, sem substituir documentos existentes.

Há uma ação **Criar atalho…** no menu de contexto do Dolphin para um item selecionado. A pasta de destino é escolhida pela pessoa. Links para sites continuam abrindo no navegador; a instalação de um aplicativo web permanece no gerenciador de webapps.

Os links aceitos são locais, HTTP/HTTPS, SMB e os locais do protocolo `linuxbr:`. Campos de atalho não aceitam comandos e não produzem um campo `Exec`. Arquivos e programas nunca são iniciados pela criação do atalho. O código recusa execução como root. Links para arquivos de programas continuam sujeitos às decisões normais do gerenciador de arquivos quando forem abertos posteriormente.

### Copiar caminho

O menu **Copiar caminho** aceita um ou vários itens. Abre uma caixa com os caminhos selecionados já na área de transferência, um por linha, e um botão para copiá-los novamente. O diálogo continua aberto para facilitar alternar para a aplicação onde será colado o texto.

Arquivos locais usam o caminho real no Linux. Endereços remotos preservam seu protocolo, removendo usuário e senha que eventualmente estejam na URL. Se houver um compartilhamento SMB, aparece a opção de copiar seu endereço como `\\servidor\pasta`, útil ao enviar um caminho de rede para alguém que usa Windows. Isso não envia o conteúdo nem concede acesso ao destinatário.

### Mapear unidade de rede

O assistente aceita `\\servidor\compartilhamento` e `smb://servidor/compartilhamento`, nome de exibição e a escolha de abrir a pasta após adicionar. Ele chama **o serviço de unidades existente**, `org.linuxbr.DriveManager1`, por `client.ServiceStore.add_share`; não mantém um segundo banco de unidades.

A letra é atribuída pelo gerenciador já existente e o local aparece em Este computador/Dolphin. A atribuição pode ser ajustada em Gerenciamento de discos. O assistente não solicita ou armazena senhas; a autenticação ocorre no acesso normal por KIO/SMB. O registro de um local não confirma que o servidor esteja disponível nem altera firewall, permissões ou publicação de pastas.

### Criar novo

Foram adicionados modelos ao menu Criar novo do Dolphin:

- Documento de texto `.txt`, texto simples para editores e Bloco de Notas.
- Anotações `.md`, com um título inicial editável.
- Documento formatado `.rtf`, com idioma português brasileiro, fonte Liberation Sans e tamanho 11.

Os modelos ficam em `/usr/share/templates`, com fontes em `.source`. São documentos locais, sem macros ou conteúdo remoto. A extensão de cada modelo permanece visível no nome da opção.

## Integração

- Executável: `/usr/bin/linuxbr-file-tools`.
- Interface principal: `/usr/lib/linuxbr-system/file_tools.py`.
- Ações: `--shortcut [ITEM]`, `--copy-path ITEM...`, `--map-network`.
- Menu de aplicativos: `linuxbr-file-tools.desktop`.
- Menus do Dolphin: `linuxbr-copy-path.desktop` e `linuxbr-shortcut.desktop`.
- Python, PyQt6, DBus Python e `linuxbr-drive-manager` já são dependências de `linuxbr-system`.
- A lista de executáveis de `scripts/build-packages.py` precisa incluir `linuxbr-file-tools`, preservando modo executável quando o código é editado no Windows.
- A Central pode oferecer `linuxbr-file-tools` na seção de organização/arquivos e `linuxbr-file-tools --map-network` na seção de rede.

## Fontes consultadas

As integrações seguem as interfaces já presentes no projeto e as fontes oficiais:

- [Documentação KDE para menus de serviço do Dolphin](https://develop.kde.org/docs/apps/dolphin/service-menus/): diretório de instalação, seleção de MIME/protocolo e argumentos `%u`/`%U`.
- [Especificação Desktop Entry do freedesktop.org](https://xdg.pages.freedesktop.org/xdg-specs/desktop-entry/latest-single/): atalhos `Type=Link`, campo `URL` e escape de valores.
- [Documentação KDE sobre o menu Criar novo](https://userbase.kde.org/Adding_an_entry_to_the_Create_New_menu): arquivos de modelo do tipo Link, com os caminhos de instalação ajustados ao diretório XDG atual do projeto.

## Validação adiada

Não foram executados testes automatizados, compilação, geração de pacotes, testes de VM ou nova ISO nesta entrega. A próxima etapa deve verificar os menus na versão Debian/KDE usada pela distribuição, abertura dos atalhos, caracteres brasileiros, múltiplos caminhos, sessão Wayland/área de transferência, rede SMB e carregamento dos três modelos.

## Ampliação da loja: programas familiares

Na mesma etapa foi ampliado somente o catálogo `usr/share/linuxbr/store/catalog.json`, preservando o esquema e os mecanismos de instalação existentes. Foram acrescentados 11 aplicativos Linux com seus nomes originais, categorias já existentes e links oficiais. A inclusão no catálogo não indica instalação concluída ou testes realizados no Linux BR.

| Aplicativo | Busca familiar e uso principal | Fonte oficial consultada |
| --- | --- | --- |
| KCalc | Calculadora, contas e porcentagem | [KDE](https://apps.kde.org/kcalc/) |
| KolourPaint | Paint, desenhos e edição simples | [KDE](https://apps.kde.org/kolourpaint/) |
| Skanpage | Scanner, digitalizar e documentos PDF | [KDE](https://apps.kde.org/skanpage/) |
| Gwenview | Fotos, galeria e visualizador de imagens | [KDE](https://apps.kde.org/gwenview/) |
| Filelight | Armazenamento, WinDirStat e espaço ocupado | [KDE](https://apps.kde.org/filelight/) |
| KDE Connect | Vincular ao Celular, arquivos e notificações | [KDE Connect](https://kdeconnect.kde.org/) |
| KeePassXC | Senhas e cofre de credenciais | [KeePassXC](https://keepassxc.org/) |
| FileZilla | FTP, SFTP e transferência para servidores | [FileZilla](https://filezilla-project.org/) |
| Thunderbird | Outlook, Correio, e-mail e agenda | [Thunderbird](https://www.thunderbird.net/) |
| Audacity | Gravador de som, voz e edição de áudio | [Audacity](https://www.audacityteam.org/) |
| Transmission | Torrent, BitTorrent e downloads | [Transmission](https://transmissionbt.com/?lan=english) |

Também foram ampliadas palavras de busca de LibreOffice, Okular, VLC, Krita, Kdenlive, OBS Studio, Firefox, Chromium, Ark e Kate. Assim, termos como Acrobat Reader, Windows Media Player, Movie Maker, Clipchamp, WinZip e Bloco de Notas podem ajudar a localizar aplicativos da mesma finalidade.

Esses termos servem para descoberta por finalidade; não renomeiam os aplicativos nem prometem equivalência completa de recursos ou execução dos produtos Windows mencionados. Não foram alteradas as entradas Windows previamente existentes, nem as regras de disponibilidade do Discover. A instalação depende das fontes configuradas no computador.

## Abrir aplicativos Linux pela loja

`store_backend.py` agora mantém uma lista explícita de caminhos de inicializadores locais, vinculados aos IDs dos aplicativos Linux. Quando um executável conhecido existe em `/usr/bin` ou `/usr/games` e permite execução, `store.py` oferece **Abrir aplicativo**. A ação usa uma lista de argumentos fixa, sem shell, sem consultar comandos de metadados remotos e sem procurar executáveis no PATH da conta.

Ao mesmo tempo, **Gerenciar instalação no Discover** mantém disponível a escolha de origem, instalação, remoção e atualização na interface já existente. O estado é consultado novamente ao recuperar o foco e ao clicar, para acompanhar instalações ou remoções feitas enquanto a loja está aberta. A consulta usa apenas metadados de arquivos locais, sem rodar processos ou consultas de rede na interface.

Essa detecção cobre os inicializadores de sistema expressamente mapeados. A ausência de um desses arquivos **não é apresentada como prova de que o aplicativo não está instalado**: aplicações Flatpak, AppImage, versões portáteis e instalações em outros caminhos continuam acessíveis por seus próprios atalhos ou pelo Discover. Não foi acrescentada descoberta de Flatpak nesta etapa. As ações de aplicativos web e programas Windows/Wine permanecem específicas de seus respectivos tipos.

Os caminhos especiais foram consultados nas listas oficiais Debian para [Steam](https://packages.debian.org/trixie/amd64/steam-installer/filelist), [SuperTux](https://packages.debian.org/trixie/amd64/supertux/filelist) e [Transmission Qt](https://packages.debian.org/trixie/amd64/transmission-qt/filelist). O inicializador Steam pode conduzir à configuração ou atualização do cliente, conforme o estado da instalação. Os nomes dos demais executáveis seguem os aplicativos do sistema e só são oferecidos quando realmente presentes.

Arquivos alterados nesta etapa: `/usr/lib/linuxbr-system/store.py` e `/usr/lib/linuxbr-system/store_backend.py`, dentro de `packages/linuxbr-system/files`. Não houve alteração do esquema do catálogo. Esta implementação também ficou **sem execução de testes ou geração de pacotes**, conforme solicitado.
