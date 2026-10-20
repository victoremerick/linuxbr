# Pacotes Linux BR

Os recursos do patch 0.2 foram migrados de `config/includes.chroot/` para os pacotes, preservando o wallpaper e atualizando apenas a versão nele. Não há repositório APT remoto nesta etapa.

| Pacote | Responsabilidade |
| --- | --- |
| linuxbr-release | os-release, banners e linuxbr-release |
| linuxbr-branding | wallpaper e ícone Linux BR derivado da paleta existente |
| linuxbr-desktop | layout e padrões iniciais por usuário; identificação do GRUB instalado |
| linuxbr-boot-theme | tema GRUB, Plymouth e ciclo de seleção/restauração |
| linuxbr-calamares-settings | configuração/branding do instalador e atalho Live |
| linuxbr-sddm-theme | Breeze com recursos Linux BR e seleção do tema |
| linuxbr-drive-manager | aplicativo Qt para discos, letras persistentes por usuário e locais SMB; UDisks2/polkit e Dolphin/KIO |
| linuxbr-system | Central do Sistema e acesso às ferramentas existentes do KDE |
| linuxbr-device-manager | inventário de hardware, drivers, firmware, diagnósticos e helper polkit |

## Identificação e compatibilidade

`linuxbr-release` instala os dados de origem em `/usr/share/linuxbr/release` e registra `dpkg-divert` para `/usr/lib/os-release`, `/etc/os-release`, `/etc/issue` e `/etc/issue.net`. Os arquivos Debian são preservados em `.debian`. Durante o live-build, o pacote assume especificamente o desvio temporário LOCAL de `/etc/os-release` para `/etc/os-release.debootstrap`, somente quando existe o marcador `/.live-build`. Outros desvios continuam sendo rejeitados. A remoção do pacote restaura os originais; não edita `/etc/debian_version`, origens do dpkg nem fontes APT.

`ID=linuxbr`, `VERSION_ID=0.4.0`, `ID_LIKE=debian` e `VERSION_CODENAME=trixie` descrevem a distribuição e sua base. Aplicativos de terceiros que exigem estritamente `ID=debian` ou uma versão Debian em `VERSION_ID` podem precisar de adaptação. O teste de APT/base-files não demonstra compatibilidade universal.

## Calamares

O build baixa `calamares-settings-debian=13.0.13-1` e transforma esse pacote em `linuxbr-calamares-settings`. Outra versão exige revisão explícita. Dependências, sequência, módulos e auxiliares Debian são preservados; os testes comparam sequência e auxiliares byte a byte.

`Conflicts/Replaces/Provides` evita instalar as duas configurações juntas. Os scripts de desvio do lançador genérico são preservados com o novo proprietário. A lista de remoção do sistema instalado remove o pacote Linux BR do instalador; os demais pacotes ficam instalados. O atalho usa `Instalar Linux BR`, ícone próprio e o wrapper Debian preservado. O autostart cria o ícone apenas em sessão Live. Links de suporte não definidos são ocultados; nenhuma URL institucional é inventada.

Os arquivos de copyright Debian permanecem no pacote derivado. Os hashes exatos de ambos os pacotes de origem ficam no manifesto de build.

## SDDM e desktop

O tema é uma cópia do Breeze do Debian em diretório próprio, com copyright e autoria preservados. Isso mantém usuários, senha, seleção de sessão, indicador de teclado e ações de energia do tema original. Não altera PAM nem implementa autenticação própria. `90-linuxbr.conf` seleciona o tema, e o wallpaper e o ícone vêm de `linuxbr-branding`.

A seleção efetiva pode ser substituída por configuração posterior do administrador. Autologin pode pular a tela SDDM: faça logout para validá-la.

O wallpaper é aplicado uma vez por usuário, com marcador em `$XDG_STATE_HOME/linuxbr/wallpaper-initialized` (padrão `~/.local/state`). Alterações posteriores do usuário são respeitadas. A configuração global cobre o usuário Live e novos usuários instalados.

O GRUB instalado recebe `GRUB_DISTRIBUTOR="Linux BR"`. O pacote `linuxbr-boot-theme` adiciona um fragmento próprio em `/etc/default/grub.d/`, arquivos em `/boot/grub/themes/linuxbr/` e tema Plymouth em `/usr/share/plymouth/themes/linuxbr/`. A seleção Plymouth usa a ferramenta oficial e não assume propriedade do arquivo de configuração do pacote Debian.

## Coleção de wallpapers do Brasil

`linuxbr-branding` inclui quatro fotografias livres em `/usr/share/wallpapers/LinuxBR-*`, com metadados do KDE, além de uma ilustração gerada de um pinguim com camisa de futebol brasileira. Os recursos são copiados automaticamente pelo empacotador, sem downloads durante o build.

As fotografias têm pelo menos 3840 × 2160 pixels (proporções originais preservadas). Créditos, fontes, licenças CC BY-SA 4.0/CC0, resoluções e hashes ficam em `files/usr/share/doc/linuxbr-branding/WALLPAPERS.md` e `wallpapers.json`, e acompanham o pacote instalado. A imagem gerada tem origem e resolução documentadas separadamente no seu `CREDITS.txt`; ela não herda a licença das fotografias.

Após reconstruir a ISO, os wallpapers estarão disponíveis na seleção de papel de parede do Plasma. O padrão do desktop no Live e no sistema instalado é Grafite, renderizado diretamente em 3840 × 2160 a partir de SVG, em `/usr/share/wallpapers/LinuxBR-graphite/contents/images/3840x2160.png`. A aplicação ocorre no primeiro login de cada usuário; escolhas posteriores são preservadas.

O SDDM usa o mesmo PNG Grafite 4K do desktop. O Calamares inclui uma cópia desse arquivo no branding (`wallpaper.png`), usada na imagem de boas-vindas e no slideshow da instalação.

## Desktop da etapa 2

`linuxbr-desktop` inclui o tema global `org.linuxbr.desktop` com um layout inicial próprio: painel inferior, menu com ícone Linux BR, tarefas com Dolphin/Firefox/Configurações/Discover, bandeja, relógio e mostrar desktop. O script não cria outro painel se já houver um. Usa a API de layouts do Plasma: https://develop.kde.org/docs/plasma/scripting/.

`/etc/skel/.config/kdeglobals` seleciona esse tema para novos usuários e habilita abertura por duplo clique. `mimeapps.list` define Dolphin, Firefox ESR e Okular. Esses arquivos são copiados na criação dos usuários Live e instalado; não são reaplicados a cada login. O wallpaper continua usando o inicializador existente. Atualizar o pacote não redefine o layout de contas já criadas. O usuário pode alterar tema, atalhos, painel e aplicativos normalmente.

Discover e seu backend Flatpak são dependências explícitas. A ISO inclui traduções pt_BR do Firefox e LibreOffice; o locale do Live continua em português e a escolha de idioma no Calamares é respeitada. Nenhum repositório Flatpak externo é adicionado automaticamente.

As aplicações administrativas continuam em etapas futuras. A aparência, os lançadores e a persistência precisam ser conferidos em sessão Plasma 6 no Live e após instalar.

Os fundos de boot são derivados com Pillow no empacotamento, sem download nem alteração do wallpaper original. `prepare-live-boot.py` personaliza os templates GRUB/ISOLINUX antes do live-build, sem substituir `grub.cfg` ou `live.cfg`.

Referências técnicas: [formato de temas GRUB](https://www.gnu.org/software/grub/manual/grub/html_node/Theme-file-format.html); implementação e hooks Plymouth examinados nos pacotes Debian `plymouth`/`plymouth-themes` 24.004.60-5 e templates de `live-build` 1:20250505+deb13u1.

O Plymouth agora usa fundo sólido, logo Linux BR e 12 quadros de animação independentes do progresso informado pelo boot. Mensagens rotineiras são ocultas; callbacks de senha e pergunta permanecem ativos. `rsvg-convert` rasteriza o logo existente no build; os quadros são gerados localmente com Pillow. A identidade geométrica e o wallpaper Grafite são usados nos menus GRUB/ISOLINUX, no SDDM e no desktop; o pinguim fica como opção na coleção.
