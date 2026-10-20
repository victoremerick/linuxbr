# Linux BR 0.2.1 Alpha

Distribuição experimental baseada em Debian 13 (Trixie), KDE Plasma 6 e Calamares. A versão 0.2.1 organiza a identidade Linux BR em pacotes locais e preserva os módulos de instalação Debian usados na 0.2.

## Construir no Fedora

Dependências do host: Podman, QEMU/KVM, qemu-img, edk2-ovmf e xorriso. Os nomes dos pacotes QEMU podem variar na versão do Fedora.

```bash
sudo dnf install podman qemu-system-x86 qemu-img edk2-ovmf xorriso
sudo env CONTAINER_ENGINE=podman ./build.sh
./tests/verify-iso.sh
```

O container de build é privilegiado e monta este repositório em `/src`. Cada execução cria um diretório novo `build/linuxbr-0.2.1.XXXXXX`, sem apagar a compilação anterior. Reserve espaço para múltiplos chroots. O processo não é reproduzível byte a byte: os repositórios Debian e a imagem `debian:trixie` podem atualizar.

Saídas:

- `dist/linuxbr-0.2.1-amd64.iso`
- `dist/linuxbr-0.2.1-amd64.iso.sha256`
- `dist/linuxbr-0.2.1-upstream.sha256`, hashes dos pacotes de origem do Calamares e Breeze
- `dist/SHA256SUMS`, preservando entradas das outras versões

A ISO 0.2 existente permanece como referência. `apply-stage2.sh` é histórico e recusa execução no projeto atual.

## Atalhos na raiz do projeto

Execute `./init-build.sh` para compilar e validar a ISO da versão atual. O cabeçalho exibe a marca geométrica em texto, o nome Linux BR e a versão. Em terminal interativo, o modo padrão mostra uma barra de seis etapas com animação; as etapas não representam percentual de tempo nem previsão de término. Sem terminal interativo, informa mudanças de etapa sem sequências de controle. `NO_COLOR=1` desativa as cores da marca. O padrão mostra apenas resumo e salva a saída completa em `.cache/logs/`; use `./init-build.sh -v` ou `--verbose` para acompanhar os detalhes. `build.sh` aceita as mesmas opções. Falhas mostram as últimas 40 linhas e preservam o código de saída. No Fedora, o script instala automaticamente via `dnf install -y` apenas as dependências ausentes de build e validação (incluindo Podman e xorriso), verifica novamente os comandos e então compila. Solicita sudo quando necessário para instalar pacotes e compilar; interrompe se qualquer etapa falhar. As dependências das VMs são instaladas pelos quatro atalhos de inicialização. A validação cobre checksum e entradas de boot; a instalação gráfica ainda deve ser testada na VM.

| Comando | Inicialização |
| --- | --- |
| `./init-vm-bios-cd.sh` | BIOS com a ISO conectada |
| `./init-vm-bios-sem-cd.sh` | BIOS pelo disco instalado, sem ISO |
| `./init-vm-uefi-cd.sh` | UEFI com a ISO conectada |
| `./init-vm-uefi-sem-cd.sh` | UEFI pelo disco instalado, sem ISO |

Os quatro atalhos verificam QEMU e qemu-img e instalam via DNF os componentes ausentes no Fedora. O backend GTK é instalado quando usado; OVMF é instalado apenas para UEFI quando nenhum par de firmware é encontrado. Caminhos OVMF personalizados inválidos geram erro, sem substituir sua configuração.

Execute os scripts de VM como usuário normal; sudo é usado somente para instalar pacotes, sem elevar o QEMU. Instale o sistema usando a variante com CD, encerre a VM e execute a variante sem CD do mesmo modo. Cada par reutiliza seu disco; o par UEFI também reutiliza a NVRAM. Os ajustes por variáveis de ambiente descritos abaixo continuam disponíveis.

## Testes em VM

```bash
./tests/test-iso.sh bios
./tests/test-iso.sh bios installed
./tests/test-iso.sh uefi
./tests/test-iso.sh uefi installed
```

Instale pelo Calamares antes de executar a variante `installed`. Encerre a VM anterior antes de reutilizar seu disco. O modo `installed` não conecta a ISO.

Os discos padrão são separados: `vm/linuxbr-0.2.1-bios.qcow2` e `vm/linuxbr-0.2.1-uefi.qcow2`. A NVRAM UEFI é copiada uma vez e preservada ao reiniciar. O script procura pares OVMF sem Secure Boot; se necessário, informe `OVMF_CODE` e `OVMF_VARS_TEMPLATE`. Outros ajustes: `ISO`, `DISK_IMAGE`, `OVMF_VARS`, `RAM_MB`, `CPUS`, `DISK_SIZE` e `QEMU_DISPLAY`.

Verificar hash e entradas El Torito não prova que o sistema inicia ou instala. Execute ambos os modos e a matriz em [VALIDACAO-0.2.1.md](VALIDACAO-0.2.1.md).

## Organização

- `VERSION`: versão usada pelos scripts.
- `build.sh` e `scripts/build-in-container.sh`: construção em Podman/live-build.
- `config/package-lists/`: pacotes Debian.
- `config/includes.chroot/`: reservado para arquivos adicionais; a identidade foi migrada para pacotes.
- `packages/`: recursos e configurações Linux BR.
- `scripts/build-packages.py`: gera seis pacotes `.deb` locais.
- `tests/`: verificações de pacotes, scripts, ISO e filesystem.
- `build/`, `dist/`, `.cache/`, `vm/`: artefatos ignorados pelo Git.

Veja [packages/README.md](packages/README.md) para decisões de empacotamento e compatibilidade.

## Verificações sem compilar a ISO

```bash
python3 tests/test-launchers.py
python3 tests/test-build-entrypoints.py
node tests/test-desktop-layout.js
mkdir -p .cache
podman run --rm --security-opt label=disable \
  -v "$PWD:/src:rw" -w /src docker.io/library/debian:trixie \
  bash tests/package-smoke.sh
```

Para também instalar todas as dependências gráficas e verificar a remoção do instalador, adicione `-e FULL_INTEGRATION=1` ao comando `podman run` (download maior).

O smoke test instala e remove pacotes apenas no container descartável, sem privilégios de host. Valida identidade, atualização de `base-files`, APT, restauração da identificação Debian e preservação dos auxiliares/sequência do Calamares. Os testes dos lançadores usam QEMU simulado; não equivalem a um teste de boot.

## Desktop da etapa 2

Novos usuários recebem o tema global Linux BR, painel inferior com menu próprio, Dolphin, Firefox, Configurações e Discover fixados. O desktop usa duplo clique e aplicativos padrão definidos em `/etc/skel/.config`. Contas existentes mantêm suas escolhas. O wallpaper Grafite 4K e a marca geométrica Linux BR são usados no desktop, SDDM e Calamares.

O idioma do Live é pt_BR; a escolha feita no instalador é preservada. Firefox e LibreOffice incluem traduções brasileiras. O teste de layout com Node.js usa uma API simulada; confirme o resultado na VM antes de considerar essa parte homologada.

## Limites

A personalização do Linux BR abrange toda a experiência de uso: organização familiar a usuários do Windows, Explorador de arquivos com Este computador e letras de unidades, Central do Sistema, gerenciamento de drivers e padrões brasileiros. O tema das janelas é uma parte desse escopo. A implementação mantém os mecanismos nativos do Linux, as escolhas dos usuários existentes e a identidade própria do Linux BR.

Os padrões brasileiros incluem português do Brasil, teclado ABNT2 com cedilha e fuso inicial America/Sao_Paulo, ajustáveis pelo usuário. A organização do desktop, dos aplicativos e das unidades deve ser consistente no live e no sistema instalado.

Armazenamento com letras, Central do Sistema e gerenciador de dispositivos já possuem implementação neste repositório. Integração completa com Active Directory e políticas de organização permanece pendente. A geração de pacotes e os testes isolados não substituem homologação da ISO em BIOS/UEFI, instalação e hardware real. Secure Boot não está homologado.

## Temas de inicialização

`linuxbr-boot-theme` inclui o GRUB instalado e o Plymouth. O build prepara também GRUB UEFI e ISOLINUX BIOS para o Live, preservando as entradas geradas pelo live-build. As imagens são derivadas do wallpaper vetorial Grafite: 1920×1080 para GRUB, 640×480 com margens para ISOLINUX. Os fundos são escurecidos para leitura; o original 4K permanece intacto.

O tema Plymouth é selecionado na primeira instalação do pacote. Atualizações respeitam uma seleção posterior do administrador; a remoção restaura o tema anterior se Linux BR ainda estiver ativo. O initramfs é atualizado por trigger. O GRUB instalado mantém parâmetros existentes e adiciona `splash`, usa resolução automática e mostra o menu por cinco segundos. O boot normal Live/instalado usa `quiet splash`, reduz mensagens do kernel/udev/systemd e oculta o cursor de texto. Plymouth mostra o logo Linux BR e um indicador circular animado, sem mensagens rotineiras. Pedidos de senha e perguntas necessárias continuam disponíveis; Esc permite consultar detalhes. Firmware, erros graves e situações sem suporte gráfico ainda podem exibir texto. O menu permite editar a linha de boot para remover `splash` se for necessário diagnosticar a inicialização.

Teste isolado (instala kernel e dependências apenas dentro do container):

```bash
podman run --rm --security-opt label=disable \
  -v "$PWD:/src:rw" -w /src docker.io/library/debian:trixie \
  bash tests/boot-theme-smoke.sh
```

O teste de renderização usa Xvfb; não substitui boot por BIOS/UEFI nem confirma drivers gráficos de hardware real.

## Identidade visual geométrica

A identidade deriva do SVG fornecido para o projeto: amarelo `#E4DF91`, verde `#8EDB91`, violeta `#9690D9`, com fundos grafite. A coleção inclui wallpapers Grafite (padrão), Claro, Floresta e Violeta em SVG e PNG 3840×2160, símbolos coloridos/monocromáticos, assinaturas horizontais e ícones de aplicativo em SVG e PNG de 16 a 512 px. O pinguim e as fotografias permanecem opcionais.

Veja `branding/overview.png` para a apresentação e `branding/README.md` para fontes e reprodução. Os PNGs entram prontos no pacote: o build da ISO não baixa imagens nem exige gerar novamente a coleção. Contas existentes mantêm wallpapers escolhidos anteriormente; novos usuários recebem Grafite.

O instalador inicia no fuso `America/Sao_Paulo` (horário de Brasília, GMT−3), com teclado brasileiro ABNT2 herdado do live, incluindo cedilha. A escolha pode ser alterada durante a instalação. A interface usa a logo centralizada nas boas-vindas e durante a cópia, sem a barra lateral redundante de etapas. Os wallpapers 4K usam curvas suaves, cores discretas e a marca no centro.

A transição gráfica usa `plymouth quit`, liberando o terminal antes da entrada do servidor gráfico. `--retain-splash` foi removido após reproduzir tela preta no Xorg/SDDM da VM instalada. O systemd usa `ShowStatus=no`, e a abertura da sessão Plasma tem splash próprio Linux BR com logo e animação. Não são adicionadas esperas artificiais nem bloqueios à inicialização do SDDM. A continuidade visual depende da troca de modo do driver e deve ser conferida em BIOS e UEFI; pode haver um breve apagamento na troca de vídeo.

## Etapa 3 — Central do Sistema (0.3.0 Alpha)

O menu **Central do Sistema Linux BR** reúne dispositivos, armazenamento, rede, usuários e administração. **Unidades e rede** abre diretamente o Drive Manager: discos e pendrives, montagem pelo UDisks2, letras persistentes por usuário e atalhos SMB abertos pelo Dolphin. Um serviço de sessão mantém as letras mesmo com a janela fechada e as publica na página **Este computador** do Dolphin (`linuxbr:/`), agrupadas por discos locais, removíveis e rede. A barra lateral mantém um único acesso, sem espalhar as unidades entre os favoritos. As associações anteriores são preservadas. As letras não substituem os caminhos Linux. Consulte [escopo, limites e testes](docs/ETAPA3-DRIVE-MANAGER.md). Compile com `./init-build.sh`; a saída usa a versão de `VERSION`, preservando ISOs de versões anteriores.

O hook `config/hooks/live/0200-linuxbr-keyboard.hook.chroot` define ABNT2/br ainda na construção, salva o mapa de console e atualiza os initramfs. Isso permite validar o teclado antes do primeiro boot, sem depender apenas dos parâmetros de `live-config`. O Calamares continua podendo gravar a escolha do usuário no sistema instalado. A checagem aceita atribuições shell com ou sem aspas.

## Etapa 4 — Dispositivos e drivers (0.4.0 Alpha)

A Central inclui inventário PCI/USB/plataforma/virtio, busca por dispositivo, identificação de driver e módulo, consulta de firmware, diagnósticos do kernel e exportação de relatório. A aba **Drivers e atualizações** identifica pacotes relacionados ao hardware, mostra versões e oferece instalar ou atualizar firmware e o kernel Debian. **Buscar versões mais recentes** atualiza os índices APT; as operações administrativas usam autenticação polkit. Também oferece NVIDIA proprietário recomendado pelo detector Debian, com headers/DKMS e verificações de Secure Boot. Não usa instaladores externos nem troca o driver gráfico em execução. Consulte [escopo, limites e validação da etapa 4](docs/ETAPA4-DISPOSITIVOS.md).

Compile com `./init-build.sh`. A ISO usa a versão de `VERSION`; o serviço de letras e os Locais do Dolphin da etapa 3 são preservados.

### Cache de compilação

O build reutiliza uma imagem local com as ferramentas Debian (live-build, Qt/KF6,
compiladores). A chave dessa imagem deriva de `scripts/Containerfile.build`;
alterar suas dependências cria uma nova imagem automaticamente. Os arquivos `.deb`
baixados pelo live-build ficam em `.cache/build-downloads/trixie-amd64`, inclusive
quando uma etapa posterior falha. Cada execução mantém workspace e sistema novos,
recompila os pacotes Linux BR e executa as mesmas validações. Índices APT continuam
sendo atualizados. Um lock impede builds simultâneos neste checkout.

- `./init-build.sh`: reaproveita ferramentas e downloads disponíveis.
- `./init-build.sh --no-cache`: atualiza a imagem base, reinstala as ferramentas e
  ignora o cache de downloads para esta execução, sem apagar workspaces anteriores.
- `./init-build.sh --no-cache -v`: mesma operação com log detalhado.

Use `--no-cache` periodicamente para atualizar as ferramentas do contêiner e ao
investigar problemas de cache. O primeiro build ainda prepara todos os componentes;
o ganho esperado está nas execuções seguintes. Instalação dos pacotes no sistema
live e compressão da ISO continuam necessárias; não há estimativa de redução medida.

O firmware da ISO é selecionado explicitamente em
`config/package-lists/linuxbr.list.chroot`. A seleção automática do live-build foi
desativada para evitar instaladores como `firmware-b43-installer` e
`firmware-b43legacy-installer`, que baixam arquivos externos durante o postinst e
podem interromper todo o build. Firmwares Debian para Intel, Realtek, Atheros,
MediaTek, Broadcom brcm80211 e vídeo permanecem incluídos. Placas antigas que usam
b43/b43legacy não recebem firmware pré-instalado: a Central → Dispositivos →
Drivers e atualizações oferece o instalador correspondente quando identifica o
módulo ativo ou candidato no hardware. É necessário acesso à internet (por exemplo,
via cabo) para o download externo, seguido de reinicialização. O cache não substitui
essa seleção.


Na Central → Armazenamento, a coluna **Espaço usado / livre** mostra a capacidade
dos filesystems montados. **Propriedades** detalha uso, espaço disponível e
reservado, dispositivo e pontos de montagem. No Dolphin, clique com o botão direito
em uma unidade de `linuxbr:/` e escolha **Propriedades da unidade Linux BR**.
As barras aparecem também nos ícones de **Este computador** do Dolphin, com texto
de espaço livre/total e atualização pelo serviço. Volumes desmontados e SMB não
são acessados automaticamente para obter capacidade.


O **Este computador** do Dolphin usa cartões horizontais no Linux BR: ícone à
esquerda, barra e espaço livre à direita, separados em discos locais, dispositivos
removíveis e unidades de rede. Isso é aplicado somente a `linuxbr:/` por um patch
restrito no Dolphin Debian. Sistema (C:) vem primeiro e as demais unidades são
ordenadas pela letra dentro de cada grupo. O painel Navegação (F7) é ativado como
sidebar em árvore na primeira execução da atualização; Locais (F9) preserva
os favoritos. A árvore mantém seus grupos e permite expandir diretórios.
O primeiro build dessa alteração também compila o Dolphin. Builds seguintes
reutilizam `.cache/dolphin-packages` se a fonte Debian e o patch forem os mesmos.
`--no-cache` recompila também esse componente.

A sidebar **Navegação** organiza Acesso rápido, Mais acessados (3 locais, ajustável
para 4 ou 5), Este computador (discos locais, removíveis e rede) e Locais de rede.
Use o botão direito para gerenciar atalhos, configurar o limite ou limpar o
histórico. Pastas também podem ser arrastadas para Acesso rápido. A descoberta
SMB/Zeroconf ocorre ao expandir os ramos de rede. Os favoritos antigos continuam
acessíveis em Locais (F9). Detalhes em [Etapa 3](docs/ETAPA3-DRIVE-MANAGER.md).

### Explorador de arquivos e terminal

O aplicativo de arquivos passa a se chamar **Explorador de arquivos**; o executável
`dolphin`, seu identificador desktop e os créditos KDE são preservados.

O perfil **Linux BR** do Konsole usa Bash interativo com letras de unidades por
padrão, compartilhando as associações do Drive Manager:

```bash
unidades                     # consultar letras disponíveis
D:                           # ir para a raiz de D (também aceita d:)
cd "D:/Minha pasta"           # navegar por letra
cd /home                     # caminhos Linux continuam válidos
ls "$(unidade D:/Projetos)"   # fornecer um caminho nativo a outros programas
terminal-modo linux          # modo tradicional apenas nesta sessão
terminal-modo letras         # voltar ao modo com letras
```

Cada nova janela ou aba do perfil Linux BR começa no modo com letras, mesmo
que uma preferência antiga tenha salvo o modo Linux. A Central → Administração
→ **Configurações do terminal** explica a troca temporária. O modo com letras
mostra caminhos como `C:/home/usuario` e `D:/Projetos` no título da janela;
o prompt fica limitado a `> `.
As letras não mudam a sintaxe de caminhos de todos os programas: use `unidade`
quando um comando precisar receber o caminho nativo. O terminal não vira CMD.

O perfil carrega o `.bashrc` existente. Scripts não interativos, outros shells e
perfis personalizados do Konsole não são alterados. O perfil padrão do Konsole
é fixado em **Linux BR** pela configuração do sistema.
Uma função `cd` já personalizada pelo usuário é preservada; nesse caso, use os
atalhos `D:`/`d:` ou `unidade`. No modo tradicional, esses atalhos ficam desativados.

Unidades locais são montadas pelo serviço existente ao navegar. Compartilhamentos
SMB usam KIO FUSE para fornecer um caminho POSIX; credenciais continuam no fluxo
KDE. A navegação exige sessão gráfica/D-Bus para montagem/autenticação. O prompt
não monta unidades nem acessa compartilhamentos automaticamente. C: representa `/`.

### Tema global das janelas — Linux BR Clean

O pacote `linuxbr-desktop` inclui o tema global, a paleta, a decoração Breeze
e a compatibilidade GTK 2/3/4. Os padrões são título alinhado à esquerda, botões
pequenos, borda fina, sombras leves, barras planas, áreas de leitura opacas e
menus Qt com 92% de opacidade. O painel mantém translucidez e desfoque nativos.
Qt 5/6 usam Breeze; aplicativos GTK compatíveis usam LinuxBRClean. LibreOffice
recebe a integração Qt 6.

A Central usa seções abertas, navegação com ícones, ações compactas e páginas
roláveis. O gerenciador de unidades agrupa montagem/letras e rede em menus;
as ações mantêm as mesmas permissões e os mesmos estados de habilitação.
Os gerenciadores de drivers, as propriedades das unidades e a configuração do
terminal seguem o mesmo espaçamento. A sidebar do Explorador usa seleção reta,
e o destaque dos cartões acompanha toda a área da unidade.

Novas contas usam os padrões de `/etc/xdg`. Contas existentes preservam suas
preferências; para aplicar o conjunto completo, execute **dentro do Linux BR**
`linuxbr-apply-theme`, sem sudo, e encerre/reabra a sessão. O comando salva backup
em `~/.local/state/linuxbr/theme-backups/` (ou `$XDG_STATE_HOME`), preserva chaves
não relacionadas e não redefine painel, wallpaper, atalhos ou dados.
`linuxbr-apply-theme --dry-run` lista as alterações sem escrever. Para reverter,
restaure os arquivos do backup nos mesmos caminhos relativos de `~/.config` e
remova apenas os arquivos listados em `previously-absent.txt`; reentre na sessão.
Também é possível selecionar outro tema em Configurações do Sistema.

Temas uniformizam os componentes fornecidos pelo toolkit; não reorganizam os
controles internos de todos os programas. Interfaces próprias, páginas web,
libadwaita e aplicativos isolados em Flatpak podem ignorar parte da aparência.
Nenhum patch global de transparência é imposto a essas interfaces.

Validação: `tests/window-theme-smoke.py` em container Debian com o conteúdo de
`linuxbr-desktop/files` instalado; sem argumentos verifica controles Qt/Breeze,
com `gtk3` e `gtk4` verifica os respectivos CSS. A decoração KWin, o desfoque e
o resultado final em cada aplicativo precisam ser conferidos na sessão da ISO.
As opções Breeze usadas seguem os esquemas oficiais de Plasma 6.3:
[kstyle](https://github.com/KDE/breeze/blob/Plasma/6.3/kstyle/breeze.kcfg) e
[decoração](https://github.com/KDE/breeze/blob/Plasma/6.3/kdecoration/breezesettingsdata.kcfg).

O Gerenciamento de discos inclui operações de partição na própria janela e mapa de espaço não alocado. Veja os formatos suportados, proteções e limites de validação em [Etapa 3](docs/ETAPA3-DRIVE-MANAGER.md#gerenciamento-de-discos).

### Contas locais e Active Directory

A Central reúne a lista de usuários locais e o acesso ao gerenciamento de contas do KDE. A página Organização permite localizar, conectar e desconectar domínios Active Directory usando realmd/SSSD. Consulte [Usuários e domínio corporativo](docs/USUARIOS-E-DOMINIO.md) para requisitos, autenticação e validação.

Consulte [Configurações e janelas](docs/CONFIGURACOES-E-JANELAS.md) para a Central ampliada, instaladores e validação visual.

A Central também reúne **Firewall**, **Gerenciador de Tarefas**, **Áudio**, **Endereços IP e DNS** e o gerenciamento de grupos locais em **Usuários**. O clique direito no botão Iniciar oferece as ações principais do sistema e o diálogo **Executar**. Consulte [escopo e validação dessas páginas](docs/CENTRAL-FIREWALL-REDE-AUDIO.md).
