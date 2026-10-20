# Etapa 3 — Central do Sistema e unidades (0.3.0 Alpha)

## Entradas no menu

- **Central do Sistema Linux BR** (`linuxbr-system`): Dispositivos, Armazenamento, Rede, Usuários, Organização e Administração.
- **Unidades e rede** (`linuxbr-drive-manager`): acesso direto ao mesmo gerenciador de armazenamento.

A Central incorpora o Drive Manager e abre ferramentas existentes do KDE para hardware, Bluetooth, impressoras, conexões/VPN, usuários, partições/formatação, atualizações e inicialização. Logs e estado dos serviços abrem no Konsole. Formatação e particionamento permanecem no KDE Partition Manager, com suas próprias confirmações e autorizações. Organização identifica explicitamente domínio/AD, políticas e certificados como integração futura. Não há implementação de gerenciamento de drivers, grupos ou permissões nesta entrega.

## Serviço de letras

`linuxbr-drive-manager.service` é um **serviço systemd por usuário**, iniciado com a sessão KDE e ativável por D-Bus. Continua funcionando quando a Central e o Drive Manager são fechados; encerra com a sessão gráfica. Não é um serviço root nem requer habilitar linger.

O nome de sessão D-Bus é `org.linuxbr.DriveManager1`, objeto `/org/linuxbr/DriveManager1`, com métodos `GetState`, `Assign`, `AddShare`, `Forget`, `Resolve` e sinal `Changed`. Eventos de UDisks2 atualizam o inventário; uma consulta a cada cinco segundos cobre reinícios ou eventos perdidos. Consultas e montagem não bloqueiam o loop D-Bus.

- C: representa `/`.
- Volumes identificáveis recebem D: em diante; compartilhamentos recebem Z: em direção inversa.
- UUID/PARTUUID mantém a associação quando o dispositivo muda de `/dev/sdb` para `/dev/sdc`.
- Letras de unidades desconectadas continuam reservadas. É possível alterar a letra ou liberar reservas pela interface.
- IDs duplicados, volumes protegidos e discos sem filesystem não recebem operações inseguras.
- Montagens usam UDisks2/polkit, sem sudo e sem alterar fstab.

A configuração existente é reutilizada, sem migração destrutiva: `${XDG_CONFIG_HOME:-~/.config}/linuxbr/drive-manager.json`. Escrita atômica, permissões 0600 e lock. Arquivos inválidos são preservados com erro. As letras são individuais por usuário; preferências do Live não são transferidas ao usuário criado pelo Calamares.

## Dolphin

O Dolphin agora tem a página **Este computador** (`linuxbr:/`), também disponível no menu de aplicativos. A visão central mostra unidades com letras e ícones, agrupadas em **Discos locais**, **Dispositivos removíveis** e **Unidades de rede**. O protocolo informa o tipo de cada unidade; não simula pastas ou monta volumes apenas para exibir a lista. Mudanças de inventário notificam o KDirLister para atualizar uma página já aberta.

Na barra lateral fica apenas o atalho **Este computador** do Linux BR. O serviço remove as antigas entradas individuais que possuem seu marcador de propriedade, preservando favoritos pessoais e as seções nativas Dispositivos/Rede do KDE. As letras continuam no mesmo JSON e não são reatribuídas pela migração visual. A sincronização usa KBookmarkManager e preserva um backup inicial `user-places.xbel.before-linuxbr`; XML inválido ou edição concorrente detectada impede a sobrescrita.

O padrão global do Dolphin abre `linuxbr:/`, com restauração automática de abas desabilitada. Preferências explícitas do usuário prevalecem sobre os padrões. A página usa uma configuração própria em `dolphin/view_properties/linuxbr-computer`, sem modificar a visão de pastas locais ou remotas. O Dolphin adaptado define cartões e agrupamento por tipo para `linuxbr:/`.

Abrir `linuxbr:/C`, `linuxbr:/D`, etc. consulta o serviço, monta via UDisks2 quando necessário e redireciona ao caminho real. Dispositivos desconectados produzem erro. O ponto de montagem e a autenticação permanecem sob responsabilidade do Linux/KIO. A listagem do Dolphin mantém os componentes nativos e agora exibe barras de capacidade nos ícones das unidades montadas, acompanhadas do texto de espaço livre e capacidade. O menu de contexto de uma unidade em `linuxbr:/` oferece **Propriedades da unidade Linux BR**, com a mesma janela de detalhes da Central.

Compartilhamentos aceitam `smb://servidor/compartilhamento` ou `\\servidor\compartilhamento`. Autenticação e navegação ficam com Dolphin/KIO; não são aceitas credenciais nas URLs nem armazenadas senhas no JSON. O cadastro não afirma que o servidor está online. Remover o compartilhamento remove só a associação local.

As letras não criam caminhos Windows `D:\`, links globais `/mnt/linuxbr` ou montagens CIFS no boot. Depois de abrir, a barra de endereço do Dolphin pode mostrar o destino Linux ou SMB real.

## Build e validação

`./init-build.sh` incorpora automaticamente os oito pacotes locais. O Drive Manager contém binários nativos, usa a arquitetura do Debian de build e dependências obtidas com `dpkg-shlibdeps`; os outros pacotes continuam `all`. CMake e os headers Qt6/KF6 são instalados no container de build.

Testes básicos:

```sh
python3 tests/test-drive-manager.py
python3 tests/test-drive-manager-backend.py
python3 tests/test-build-entrypoints.py
python3 tests/test-launchers.py
QT_QPA_PLATFORM=offscreen python3 tests/test-drive-manager-gui.py
QT_QPA_PLATFORM=offscreen python3 tests/test-system-central.py
```

`tests/package-smoke.sh` gera os pacotes e verifica a preservação da sequência/helpers Calamares, identidade e restauração do Debian. Execute apenas em container Debian descartável. Para testar serviço e Dolphin sem tocar favoritos reais, no mesmo container instale `python3-pyqt6 python3-dbus python3-gi dbus-x11` e execute `bash tests/drive-service-smoke.sh`. Esse teste usa D-Bus, KBookmarkManager e KIO reais, diretórios temporários e inventário UDisks simulado. Confere redirecionamento KIO, persistência após reiniciar o serviço, favoritos pessoais e recusa de XML corrompido.

A validação da imagem exige Central, serviço, plugin e pacotes tanto no Live quanto no sistema instalado. Compilar os pacotes e passar nos testes isolados não valida o boot nem operações reais de disco/rede.

## Roteiro na nova ISO

1. Abra a Central pelo menu. Abra Este computador no Dolphin e compare o inventário.
2. Em VM com disco/pendrive descartável, monte uma unidade e altere sua letra.
3. Feche a Central, desconecte/reconecte o dispositivo e abra sua letra na página Este computador do Dolphin. A associação deve permanecer.
4. Reinicie a sessão e confirme a letra e os favoritos pessoais.
5. Adicione um compartilhamento SMB disponível, autentique no Dolphin e confira a letra. Teste também servidor indisponível.
6. Confirme que C: não pode ser reatribuído/desmontado e que outra unidade não pode ocupar letra reservada.

Permanecem por validar na ISO: montagem/desmontagem real, reconexão USB e autenticação SMB. Não foi alterado o fluxo Plymouth/SDDM que corrigiu a tela preta.

### Verificação desta entrega

Passaram: 8 testes de modelo, 4 de backend, 2 de modelo do serviço/Locais; integração com D-Bus/KIO reais e reinício do serviço; interfaces Drive Manager/Central em Qt offscreen; 9 testes de build, 7 de lançadores e o teste do layout. Os oito pacotes foram gerados e o APT resolveu as dependências em simulação Debian Trixie. Os testes de instalação/reinstalação/restauração da identidade e preservação do Calamares passaram.

Artefatos desta execução: `.cache/stage3-central.v4yZrB/debs/`; prévia com dados de teste: `.cache/system-central.png`. Não foi compilada uma nova ISO nesta execução.

A migração dos favoritos próprios e a listagem KIO agrupada foram testadas com D-Bus/KIO reais e inventário simulado. A página inicial foi conferida no Dolphin real em Xvfb, com dados de teste; captura em `.cache/linuxbr-computer.png`. Não substitui boot/USB real na ISO.


## Espaço e propriedades das unidades

A Central → Armazenamento exibe barras de uso e texto com espaço livre para o
usuário e capacidade do filesystem. Propriedades mostra também espaço usado,
espaço reservado pelo filesystem, capacidade do volume, tipo, formato, dispositivo,
identificador persistente e pontos de montagem. Espaço reservado não é contado
como arquivo usado nem como espaço disponível ao usuário.

A consulta `statvfs` ocorre em subprocessos com timeout, fora da interface e do
loop D-Bus. Não monta volumes. Unidades desmontadas mostram “Monte para consultar”;
SMB mostra capacidade indisponível sem acessar automaticamente o servidor. Erros
ou remoção de dispositivo preservam a listagem sem inventar zero de espaço livre.
As propriedades mostram uma fotografia da última consulta, não alteram a unidade.

Testes: `tests/test-drive-capacity.py`, `tests/test-drive-manager-gui.py`, modelo e
backend. Menu Dolphin usa a extensão de serviço documentada pelo KDE:
https://develop.kde.org/docs/apps/dolphin/service-menus/


### Barras no Este computador do Dolphin

O serviço seleciona um ícone SVG de capacidade (0–100%) para cada unidade com
estatísticas disponíveis. O KIO usa esse ícone na listagem `linuxbr:/` e acrescenta
espaço livre/total ao nome exibido, sem alterar a letra, URL ou agrupamento. A barra
representa espaço usado; a partir de 90% fica vermelha. A escala acompanha o zoom
de ícones do Dolphin. Não se aplica patch ao Dolphin nem se modifica sua navegação.

Os 202 SVGs (disco/USB, 101 percentuais) são gerados pelo build e não crescem com o
tempo. A atualização de inventário já existente notifica o Dolphin quando o uso
muda. Compartilhamentos e unidades desmontadas não recebem barra fictícia; o texto
explica a ausência da medição. Configurações de exibição do usuário são preservadas.

Validação das barras: modelo, geração dos 202 ícones, passagem dos ícones/textos
pelo KIO real e preservação das letras após reiniciar o serviço. Conferência visual
no Dolphin real em Xvfb com inventário simulado: `.cache/linuxbr-dolphin-bars.png`.
`tests/test-drive-icons-qt.py` verifica as cores de preenchimento renderizadas pelo
Qt (dependência de teste: `python3-pyqt6.qtsvg`). ISO/boot não foram refeitos nesta
alteração.


### Cartões horizontais no Dolphin

A construção inclui uma adaptação do Dolphin Debian para a página `linuxbr:/`:
ícone à esquerda, título, barra larga e espaço livre à direita; grupos Discos
locais, Dispositivos removíveis e Unidades de rede. O desenho usa a seleção e a
navegação nativas. Dados adicionais são publicados pelo KIO em UDS_EXTRA e lidos
apenas para o protocolo Linux BR. Outras pastas mantêm a implementação original.

`scripts/patch-dolphin.py` aplica alterações com verificação exata de contexto;
se o código Debian mudar incompativelmente, o build falha em vez de ignorar o patch.
`scripts/build-dolphin.sh` gera os pacotes Dolphin, dolphin-data e libdolphinvcs6
com revisão local, preservando dependências Debian. Fonte e alterações definem a
chave de cache em `.cache/dolphin-packages`. `--no-cache` força recompilação.
Atualizações futuras do Dolphin Debian devem ser incorporadas reconstruindo esses
pacotes; uma substituição por Dolphin sem o patch retorna à apresentação por ícones.

Validação dos cartões: pacotes Debian compilados e instalados em contêiner,
Dolphin real em Xvfb com dados simulados, três grupos e ícones/barras conferidos.
A navegação de `linuxbr:/C` para `/` mantém a visualização normal de pastas.
Capturas: `.cache/linuxbr-dolphin-cards.png` e `.cache/linuxbr-dolphin-folder.png`.
Passaram integração D-Bus/KIO, preservação de letras, modelo e testes de cache/build.
A ISO completa ainda precisa ser reconstruída e testada no live/instalado.

### Ordenação e navegação em árvore

O Dolphin ordena os cartões de `linuxbr:/` por grupo (discos locais,
removíveis, rede) e depois pela letra, independentemente do nome ou do espaço
livre. Assim, Sistema (C:) aparece primeiro. A comparação não altera a
ordenação de pastas comuns.

Na primeira execução da atualização, a sidebar **Navegação** passa a ser o
padrão, com os quatro grupos descritos abaixo. O painel **Locais** continua
disponível em F9, com os favoritos preservados; F7 alterna a nova árvore.
Expandir ou abrir uma unidade pode solicitar montagem/autenticação pelo fluxo
existente do UDisks/KIO.

A regressão de ordenação pode ser validada em container descartável com
`bash tests/dolphin-navigation-smoke.sh /caminho/da/fonte-dolphin-compilada`,
após instalar o worker KIO Linux BR. O teste usa o modelo C++ real do Dolphin,
um serviço de sessão simulado e HOME temporário; verifica cartões e árvore sem
montar discos reais.

### Sidebar com quatro grupos

O painel Navegação (F7) substitui a árvore simples, preservando os cartões e o
painel Locais (F9). A atualização ativa o novo painel uma vez, usando a chave
`LinuxBRNavigation/GroupedSidebarInitialized` no dolphinrc.

1. **Acesso rápido**: Pasta pessoal, Documentos, Downloads, Imagens, Vídeos e
   Músicas, resolvidos pelos diretórios XDG do usuário. Arrastar uma pasta sobre
   esse grupo cria um atalho, sem mover arquivos. O menu de contexto permite
   fixar a pasta atual, adicionar outro caminho/URL, renomear ou remover atalhos.
2. **Mais acessados**: até 3 locais por padrão, configuráveis para 4 ou 5 pelo
   menu de contexto. Ordenação por frequência nos últimos 30 dias, com acesso
   mais recente como desempate. Repetições do mesmo local em menos de 60 segundos
   contam uma vez. O histórico pode ser limpo no mesmo menu.
3. **Este computador**: Discos locais, Dispositivos removíveis e Unidades de rede,
   ordenados por letra em cada subgrupo, com Sistema (C:) primeiro. A atualização
   do espaço livre não recolhe pastas abertas. Remoção de dispositivo remove seu
   nó; as associações de letras permanecem no serviço existente.
4. **Locais de rede**: Computadores e compartilhamentos (`smb:/`) e Dispositivos
   e serviços (`zeroconf:/`). A consulta acontece ao expandir cada ramo, usando os
   workers KDE, SMB/WS-Discovery e Avahi/mDNS. O computador/dispositivo precisa
   anunciar serviços compatíveis e a rede permitir descoberta. Não é um inventário
   completo de endereços IP. O menu permite atualizar ramos após uma falha.

As pastas são carregadas de forma assíncrona apenas ao expandir, com os fluxos de
montagem e autenticação do KIO/UDisks. Favoritos e histórico ficam em
`$XDG_CONFIG_HOME/linuxbr/sidebar.json` (normalmente `~/.config/linuxbr/sidebar.json`),
com escrita atômica, trava entre janelas e permissões de proprietário. Senhas,
usuários de URLs, queries e fragmentos não são persistidos. O histórico é limitado
a 200 locais e 256 registros por local. As pastas comuns do Dolphin e seus
favoritos anteriores não são alterados.

`tests/dolphin-sidebar-smoke.sh` testa em container a árvore Qt real, agrupamento,
ordenação de letras, atualização de unidades, persistência, privacidade e limites
do histórico. Descoberta em uma rede física deve ser validada no live/instalado
com um computador ou NAS que anuncie SMB e um dispositivo mDNS.

### Correção da falha ao destacar unidades (Breeze)

O desenho dos cartões prepara agora o cache padrão antes de desenhar seleção e
hover. Antes, `selectionRect()` podia atualizar o cache durante o desenho do
hover e destruir o pixmap que ainda tinha um `QPainter` ativo, causando SIGSEGV
em `QPainter::save()` dentro do Breeze. As pastas comuns continuam usando o
desenho original.

Regressão: `tests/dolphin-card-paint-smoke.sh /caminho/da/fonte-dolphin-compilada`,
em container Debian com `kde-style-breeze`. O teste exercita 100 ciclos de
hover, seleção, foco, redimensionamento e atualização de capacidade, mais uma
pasta comum. A falha foi reproduzida com a biblioteca anterior; recompilar o
renderizador corrigido e vinculá-lo à mesma biblioteca fez o teste passar. Isso
valida a correção do desenho, não substitui a validação da nova ISO.

O conteúdo do renderizador participa da chave do cache de pacotes; o próximo
`./init-build.sh` recompila automaticamente o Dolphin corrigido. A instalação
já existente não é alterada ao editar ou compilar o projeto.

### Layout Clean das janelas

A Central passa a usar seções abertas e links compactos, sem caixas ao redor
das especificações. A navegação mantém suas sete categorias e suporta teclado
e janela de 900×560, com rolagem no conteúdo. O gerenciador de unidades mantém
as ações e seus bloqueios: Atualizar/Abrir/Propriedades na barra; montagem,
desmontagem, letras e reservas em Gerenciar unidade; compartilhamentos em Rede.
A sidebar do Dolphin mantém seus quatro grupos e a árvore, com realce reto
baseado na paleta. Cartões têm foco e seleção delimitados pela área completa.

Validação funcional: `tests/test-clean-layout.py`, `tests/test-system-central.py`,
`tests/test-drive-manager-gui.py`, `tests/test-device-manager-gui.py`,
`tests/test-terminal-settings.py`, e os testes nativos do Dolphin (sidebar,
navegação e pintura). As prévias usam dados simulados; não substituem boot da ISO.

### Gerenciamento de discos

A Central e o aplicativo de armazenamento apresentam uma lista de volumes acima de um mapa de discos e partições, em painéis redimensionáveis. O mapa usa a tabela, a ordem e os deslocamentos fornecidos pelo UDisks; o disco que contém C: aparece primeiro. A seleção dos blocos e da tabela é sincronizada. Volumes sem topologia conhecida e unidades de rede aparecem separados. As larguras são aproximadas, com mínimo para leitura, e não indicam espaço livre dentro do sistema de arquivos.

O menu Partições e os menus de contexto executam criação, exclusão, formatação e redimensionamento diretamente nesta interface, por UDisks e polkit, sem abrir o KDE Partition Manager. O mapa mostra intervalos não alocados utilizáveis, alinhados a MiB, reservando 1 MiB em cada extremidade para metadados e alinhamento; não é uma representação de todos os setores vazios. Tabelas incompletas ou sobrepostas não geram intervalos editáveis.

A edição suporta GPT e MBR com partições primárias. Criação e formatação oferecem ext4, NTFS, exFAT e FAT32 (vfat), verificando a ferramenta disponível antes de executar. Redimensionamento suporta ext4 desmontado, sem mover o início da partição, com crescimento limitado ao espaço contíguo à direita. O mínimo real é validado pela ferramenta ext4. MBR com quatro partições primárias não permite uma quinta.

Discos com volumes montados, configuração fstab/crypttab, swap, LVM, RAID, criptografia, partições MBR estendidas/lógicas ou somente leitura ficam bloqueados. Partições EFI, de inicialização ou de tipos especiais não podem ser excluídas/formatadas/redimensionadas. Discos sem tabela precisam ser inicializados por outra ferramenta; esta implementação não inicializa discos nem migra tabelas.

Cada diálogo mostra o dispositivo e os parâmetros, exige confirmação explícita e, para exclusão/formatação, a digitação do caminho do dispositivo. O worker consulta novamente identidade, geometria, ocupação e jobs do UDisks. Não força desmontagem nem limpeza de dependências. A preparação do ext4 usa a API Repair do UDisks somente depois de uma verificação Check bem-sucedida em volume desmontado; sistemas com erros detectados na checagem inicial são bloqueados. A preparação grava o resultado de fsck exigido pelo resize2fs e é informada no diálogo de confirmação. Uma nova checagem é exigida antes de alterar tamanhos. Uma operação por usuário é serializada; UDisks continua responsável pela autorização e pela rejeição de dispositivos ocupados. Outros administradores não devem alterar o mesmo disco simultaneamente.

Na redução, verifica e prepara o ext4, reduz o sistema de arquivos, confirma seu tamanho e só então reduz a partição. Na ampliação, aumenta primeiro a partição. Falhas parciais são comunicadas sem rollback destrutivo e a lista é atualizada. A operação usa um indicador indeterminado, sem percentual inventado; a janela bloqueia o fechamento enquanto o worker está ativo.

Testes: `tests/test-partitioning.py` e `tests/test-partition-dialog.py` verificam limites, identidade alterada, autorização negada, ferramentas ausentes, ordem das operações, falhas parciais, confirmações e roteamento, com objetos D-Bus simulados. Não equivalem à homologação de alterações reais; antes de distribuir a ISO, testar com discos virtuais descartáveis, incluindo verificação dos arquivos após redução/ampliação e cancelamento de autorização.

Referências da implementação: [PartitionTable](https://storaged.org/doc/udisks2-api/latest/gdbus-org.freedesktop.UDisks2.PartitionTable.html), [Partition](https://storaged.org/doc/udisks2-api/latest/gdbus-org.freedesktop.UDisks2.Partition.html), [Filesystem](https://storaged.org/doc/udisks2-api/latest/gdbus-org.freedesktop.UDisks2.Filesystem.html) e [Manager](https://storaged.org/doc/udisks2-api/latest/gdbus-org.freedesktop.UDisks2.Manager.html).

Teste isolado da topologia e seleção: `QT_QPA_PLATFORM=offscreen python3 tests/test-disk-map.py`. As fixtures não montam nem alteram discos reais.


### Validação real em discos virtuais — 2026-10-18

Executada com sucesso em QEMU/KVM, usando o live Linux BR 0.4.0 como ambiente e injetando o código atual do gerenciador no initramfs de teste. A ISO original permaneceu somente leitura. A VM ficou sem rede e recebeu apenas dois arquivos novos de disco de 2 GiB, identificados por números de série exclusivos: GPT e MBR. Nenhum disco do host foi exposto à VM.

O teste chama `backend.py partition`, a mesma entrada utilizada pela interface, com UDisks 2.10.1 e libblockdev 3.3.0 reais. Foram aprovadas 29 verificações:

- Criação e exclusão de ext4, NTFS, exFAT e FAT32 nos dois esquemas.
- Reformatação entre os quatro formatos, seguida de montagem, escrita e releitura após remontar.
- Redução ext4 de 768 para 256 MiB e ampliação para 1024 MiB, preservando oito arquivos aleatórios (64 MiB por disco), verificados com SHA-256 e e2fsck.
- Rejeição de redução para 32 MiB, mantendo tamanho da partição e arquivos intactos.
- Bloqueio de disco montado e de confirmação com geometria desatualizada.
- Restauração de todo o espaço alocável após excluir as partições.
- Negação real de autorização pelo polkit para um usuário de teste, preservando o formato e tamanho existentes.

A execução revelou e corrigiu uma falha intermitente: a checagem somente leitura não registra a verificação que o resize2fs exige após uma montagem posterior. O worker agora verifica, prepara e verifica novamente o ext4 antes de mudar tamanhos. O teste introduz uma espera antes da montagem para reproduzir essa condição; os 17 testes unitários e o teste de confirmação da interface também passaram após a correção. A preparação usa Repair apenas após Check indicar um volume saudável; se Check detectar erros, não tenta repará-los automaticamente. A diferença entre as operações pode ser conferida no [código do libblockdev](https://github.com/storaged-project/libblockdev/blob/3.3.0/src/plugins/fs/ext.c).

Reprodução no host (Python 3.11+, QEMU/KVM, xorriso, cpio e zstd):

```bash
python3 tests/partition-vm-smoke.py --iso dist/linuxbr-0.4.0-amd64.iso
```

O runner cria os discos em `/tmp`, encerra a VM e remove seus arquivos temporários. `--keep-vm` preserva esses arquivos para diagnóstico. Não exige sudo no host. Logs, resumo, comando QEMU, hash da ISO e hashes do código testado ficam em `.cache/partition-vm.*/`. O script `partition-vm-guest.py` é exclusivo da VM e verifica virtualização, marcador de boot, tamanho e números de série antes de qualquer alteração.

Evidência desta execução: `.cache/partition-vm.uxq31o6s/summary.txt`, `serial.log` e `manifest.json`. O teste valida operações reais do backend, não interação com diálogos gráficos de autenticação, resistência a quedas de energia ou hardware físico. A ISO distribuída ainda precisa ser recompilada para incluir a correção.
