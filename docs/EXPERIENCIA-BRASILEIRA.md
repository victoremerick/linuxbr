# Experiência brasileira — Linux BR 0.4.1

Esta revisão completa a integração de recursos já existentes sem substituir as
alterações locais de tela, energia, acesso remoto, notificações e cores.

## Uso diário

- Painel inferior e menu Linux BR com guia Primeiros passos entre os favoritos.
- Guia offline em português: preparação, equivalências com Windows, arquivos,
  instalação de programas, atalhos e resolução de problemas.
- Na sessão Live, botão direto para instalar o Linux BR.
- Primeira abertura automática por usuário; opção de mostrar a cada entrada.
  A preferência fica em `$XDG_CONFIG_HOME/linuxbr/welcome.json`.
- Central com Primeiros passos, Recuperação e ajuda, busca sem distinção de
  acentos, termos familiares, Ctrl+F e indicação de pesquisa sem resultados.
- Exportação voluntária de informações básicas para um arquivo local de suporte.
  Não inclui nome de usuário, nome do computador, configurações de rede ou logs.
- Contas novas recebem atalhos Windows+E, Windows+I, Windows+R,
  Ctrl+Shift+Esc e Print. Os padrões normais de bloquear e mostrar o desktop
  usam Windows+L e Windows+D. As escolhas das contas existentes são preservadas.
- Writer e Calc são associados aos formatos Office e OpenDocument nas contas
  novas. Firefox e Okular continuam como padrões de navegação e PDF.
- A imagem inclui locale pt_BR.UTF-8, teclado ABNT2, corretor ortográfico
  brasileiro, hifenização e captura de tela. O instalador permite escolher
  outro idioma e fuso. O fuso inicial é America/Sao_Paulo. A primeira sessão
  Plasma recebe o teclado escolhido pelo instalador; arquivos de configuração
  de teclado já existentes não são substituídos.

## Configurações e recuperação

A Central integra os controles existentes de discos, dispositivos, usuários,
rede, áudio, tela, aparência, acesso remoto e energia. Categorias que usam
ferramentas KDE continuam abrindo essas ferramentas. O guia de recuperação
orienta o usuário e abre as configurações relacionadas; não formata discos,
reinstala o sistema, restaura backups ou altera drivers automaticamente.

Não foi adicionado serviço comercial de nuvem ou repositório de terceiros.
A disponibilidade da loja depende dos repositórios configurados e da conexão.
Programas EXE/MSI não são executados automaticamente. Não há promessa de
compatibilidade universal com aplicativos Windows.

## Compilar e executar

```bash
./init-build.sh
./init-vm-bios-cd.sh
./init-vm-uefi-cd.sh
```

O emulador usa VGA com EDID de 1280×768. VirtIO permanece disponível via
`QEMU_VIDEO_DEVICE=virtio-vga`; nesse modo o backend pode anunciar outra
resolução preferida.

O build salva os logs em `.cache/logs/` e produz
`dist/linuxbr-0.4.1-amd64.iso`. Cada compilação conserva sua árvore em `build/`.
O sistema instalado pode ser iniciado pelos atalhos `*-sem-cd.sh` depois de
instalar na VM correspondente. Execute uma VM por disco por vez.

## Verificação

Testes específicos:

```bash
QT_QPA_PLATFORM=offscreen python3 tests/test-welcome.py
QT_QPA_PLATFORM=offscreen dbus-run-session python3 tests/test-system-central.py
python3 tests/test-build-entrypoints.py
python3 tests/test-launchers.py
node tests/test-desktop-layout.js
```

Os testes gráficos exigem PyQt6 e as dependências existentes da Central.
Use Debian 13 em contêiner para testar o ambiente da distribuição.
`tests/check-rootfs.py` confere também o guia, os atalhos, a inicialização
automática, o dicionário e o locale no filesystem produzido.

Validação em 28/10/2026, QEMU/KVM no computador de desenvolvimento:

| Etapa | Estado |
| --- | --- |
| Testes de código e interface isolada | Passaram |
| Pacotes e validação do filesystem | Passaram na imagem final |
| Compilação e checksum da ISO | Passaram; log compilacao.RcZ2yC.log |
| Boot Live BIOS e UEFI | Ambos passaram na ISO final; BIOS verificado uma vez após concluir os ajustes |
| Instalação Calamares e boot pelo disco | UEFI final passou, incluindo GPT/EFI e primeiro login sem ISO; instalação BIOS foi testada na revisão anterior |
| Menu, atalhos e primeiros passos na sessão real | UEFI passou: favoritos, guia único, Win+I, Win+E, Ctrl+Shift+Esc e busca Windows Update |
| Hardware real, periféricos e Secure Boot | Não homologados |

Uma verificação estática ou captura da interface isolada não comprova boot,
instalação ou funcionamento em hardware real.

A sessão Live e a primeira sessão instalada UEFI abriram em 1280×768 com VGA.
O sistema instalado confirmou LANG=pt_BR.UTF-8 e layout br. O instalador
identifica o modelo como Generic 105-key PC (pc105), com leiaute brasileiro.

SHA-256 da ISO validada:

49389736476bd1203aaa0659f06001ef74cf24f63cbe39ecc54e8f8f9f8dac9f

Limitações visuais observadas nesta versão Alpha: o banner inicial do Calamares
fica ampliado e algumas frases de seu resumo traduzido mostram o número 1
no lugar do nome do fuso/modelo. As seleções e a configuração instalada foram
verificadas; esses textos ainda precisam de acabamento.
