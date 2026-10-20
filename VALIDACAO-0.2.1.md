# Validação Linux BR 0.2.1 Alpha

## Automatizada

- `python3 tests/test-launchers.py`: geração de argumentos BIOS/UEFI, criação de diretórios/disco, persistência da NVRAM, boot sem ISO e rejeição de checksum errado. QEMU simulado.
- `tests/package-smoke.sh`: executar apenas no container indicado no README; gera os seis .deb, compara Calamares e testa identidade/APT/atualização/remoção.
- `python3 tests/check-rootfs.py CAMINHO --mode live`: executado automaticamente após `lb build`; verifica os cinco pacotes persistentes, identidade, arquivos SDDM/KDE, sequência e lançador Calamares.
- `python3 tests/check-rootfs.py / --mode installed`: dentro de um sistema instalado, com Python/PyYAML disponíveis; verifica identidade, pacotes persistentes e ausência do lançador Live.
- `./tests/verify-iso.sh`: checksum específico da ISO e entradas BIOS/UEFI. Requer xorriso no host.

## Manual, separadamente para BIOS e UEFI

1. Compilar e verificar a ISO 0.2.1.
2. Iniciar Live e confirmar idioma/teclado pt_BR, rede, Dolphin e KDE Info Center.
3. Conferir `cat /etc/os-release`: Linux BR 0.2.1 Alpha, base Debian em ID_LIKE/codename.
4. Fazer logout para verificar SDDM: fundo, logo, usuários, senha, sessões e botões de energia. Testar também resolução 1280×720 e 1920×1080.
5. Abrir **Instalar Linux BR**; conferir título, boas-vindas, logo e slideshow, sem links institucionais fictícios.
6. Instalar exclusivamente no disco virtual de testes.
7. Desligar e executar `./tests/test-iso.sh MODO installed`.
8. Confirmar login, identidade, wallpaper, APT (`sudo apt update`) e ausência do atalho de instalação.
9. Alterar wallpaper, sair e entrar novamente: a escolha deve persistir.
10. Criar outro usuário e conferir o wallpaper inicial.
11. Em UEFI, confirmar `test -d /sys/firmware/efi` e persistência da NVRAM entre reinícios.

Não declarar estes passos aprovados apenas por sucesso nos testes de arquivos/pacotes. Comparar eventuais regressões com a ISO 0.2 preservada em `dist/`.

## Resultado da implementação em 14/10/2026

Aprovados nesta sessão:

- Sintaxe Bash/Python e `git diff --check`.
- ShellCheck dos scripts de build, teste da ISO, QEMU e smoke test.
- Sete testes automatizados dos lançadores/checksum com QEMU simulado.
- Construção dos cinco pacotes `.deb` em Debian Trixie.
- Comparação da sequência e dos auxiliares do Calamares com o pacote Debian 13.0.13-1.
- Instalação e reinstalação da identidade, reinstalação de `base-files`, `apt-get update`, remoção e purge com restauração da identidade Debian.
- Instalação conjunta dos cinco pacotes e dependências em container Debian; verificação do filesystem no estado Live.
- Remoção de `linuxbr-calamares-settings`, restauração do lançador genérico do pacote Calamares e verificação dos quatro pacotes persistentes. Isso simula a remoção do instalador; não é uma instalação em disco pelo Calamares.

Não executados: build completo da ISO 0.2.1, boot BIOS/UEFI, interação gráfica com KDE/SDDM/Calamares e instalação/reinicialização em VM. O build privilegiado exige sudo no host; não havia autenticação sudo não interativa disponível. Os resultados acima não homologam esses cenários.

## Correção de integração com live-build

O smoke test foi ampliado após a falha do pacote `linuxbr-release` durante a compilação real. O teste anterior usava um container Debian sem o desvio temporário de `/etc/os-release` criado pelo live-build.

O pacote agora assume apenas o desvio LOCAL para `/etc/os-release.debootstrap`, quando está presente o marcador `/.live-build`. A regressão reproduz esse estado e verifica instalação, reinstalação, atualização de `base-files`, restauração Debian e rejeição de um desvio administrativo diferente. A limpeza posterior do live-build não deve remover o desvio permanente Linux BR.

## Desktop da etapa 2 — validação pendente em VM

- No primeiro login Live e de um novo usuário instalado, conferir painel inferior, ícone do menu e os quatro aplicativos fixados.
- Abrir Dolphin, Firefox, Configurações e Discover pelo painel; conferir abertura por duplo clique no Dolphin.
- Abrir link HTTP/HTTPS e PDF para verificar Firefox/Okular como padrões.
- Conferir português no Live e o idioma escolhido no instalador.
- Personalizar o painel e aplicativos padrão; sair e entrar novamente e confirmar persistência sem duplicação de painéis.
- Testar resoluções 1280×720 e 1920×1080, Wayland e X11 quando disponíveis.

`node tests/test-desktop-layout.js` verifica a criação do painel e a preservação de um painel existente usando uma API Plasma simulada; não comprova renderização gráfica.

Verificações executadas para este incremento do desktop: teste do layout com API simulada; sete testes dos lançadores; geração dos cinco pacotes e smoke test de identidade/APT/diversões no Debian Trixie; disponibilidade das novas dependências e ausência de colisões dos arquivos de skel com plasma-desktop, plasma-workspace e desktop-base. A validação visual e a instalação completa continuam pendentes.

## Temas de boot — testes em VM pendentes

- BIOS Live: conferir menu ISOLINUX, pinguim e legibilidade; UEFI Live: conferir tema GRUB e navegação, incluindo submenu de utilitários.
- Nos dois modos, verificar Plymouth, mensagens e transição ao SDDM, inclusive em 1024×768 e 1920×1080.
- Após instalar, iniciar sem ISO, conferir menu GRUB Linux BR e Plymouth; verificar `/proc/cmdline` com `splash`.
- Conferir que `sudo plymouth-set-default-theme` retorna `linuxbr` e que o tema está presente no initramfs instalado.
- Verificar reinicialização/desligamento; se houver instalação criptografada, testar prompt real de senha e entrada pelo teclado brasileiro.
- O teste `boot-theme-smoke.sh` valida empacotamento, initramfs, seleção/reinstalação/remoção e renderização Plymouth em Xvfb, sem escrever no boot do host.

Resultados automatizados deste incremento: seis pacotes gerados; fundos com dimensões verificadas; templates Live preservando entradas upstream; fragmento GRUB preservando parâmetros e sem duplicar `splash`; tema/plugin presentes em initramfs real de kernel Debian; Plymouth renderizado em Xvfb com mensagem e solicitação de senha; reinstalação preservando seleção administrativa; remoção/purge restaurando seleção anterior. O container usou `MODULES=list` para verificar recursos de tema sem homologar drivers. Sete testes de lançadores e teste simulado do desktop também passaram.

O tema GRUB foi renderizado em QEMU/TCG a 1024×768 usando uma ISO mínima de teste (sem instalar nem iniciar o Linux BR). A imagem usa margens para preservar proporção em telas 4:3. Isso valida a leitura do tema e a apresentação do menu, não o boot da distribuição ou do sistema instalado. A sequência e os helpers do Calamares foram comparados com a implementação anterior e permanecem iguais.

## Boot silencioso e logs de build

- `python3 tests/test-build-entrypoints.py`: resumo padrão, ambos os aliases de verbosidade, logs completos, falhas com código preservado e substituição do arquivo do container durante `lb build` (simulado).
- No Live e instalado: conferir logo com animação contínua, ausência de mensagens rotineiras, Esc para detalhes e solicitação de senha quando aplicável.
- No build: conferir `./init-build.sh`, `./init-build.sh -v` e logs em `.cache/logs/`.

Nesta atualização, o smoke test passou com o logo no initramfs, renderização real do Plymouth em Xvfb e callbacks de senha. Duas capturas com intervalo de 0,3 s mostraram alteração de pixels apenas na região do indicador, confirmando animação. A mensagem rotineira de teste ficou oculta na captura. O teste continua sem homologar o boot completo da ISO ou hardware real.

## Identidade geométrica

Exportações SVG/PNG conferidas visualmente em `branding/overview.png`; dimensões dos quatro wallpapers 4K, metadados e ícones 16–512 px verificadas. Geração dos seis pacotes e smoke test Debian de identidade/APT/diversões passaram. Os seis testes de entrada de build, sete de lançadores e teste simulado do layout passaram. Grafite substitui o pinguim como padrão; o pinguim e fotografias permanecem opcionais. Validar a nova aparência no Live e instalado após reconstruir a ISO.
