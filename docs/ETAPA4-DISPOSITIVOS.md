# Etapa 4 — Dispositivos e drivers (0.4.0 Alpha)

A Central do Sistema agora incorpora **Dispositivos e drivers** na categoria Dispositivos. Também existe a entrada independente no menu, executável `linuxbr-device-manager`. O novo pacote local é `linuxbr-device-manager`; o build incorpora nove pacotes e usa `VERSION=0.4.0`.

## Inventário e diagnósticos

- Dispositivos PCI, USB, plataforma e virtio, organizados por categoria, com busca por nome, fabricante, ID ou driver.
- Fabricante/modelo PCI pelo `lspci`; identificação USB e vínculos de driver/módulo pelo sysfs. Interfaces USB são agrupadas no dispositivo físico.
- Atualização manual e a cada 30 segundos, em processo separado para manter a interface responsiva. Dispositivos removidos desaparecem na próxima consulta.
- Driver associado, módulo do kernel e modalias. Drivers integrados ao kernel podem não ter um módulo separado.
- Para dispositivos sem driver, consulta de candidatos pela tabela local de aliases (`modprobe --resolve-alias`). Não carrega, descarrega nem força módulos. Ausência de vínculo/candidato não é uma declaração definitiva de incompatibilidade.
- Firmware declarado nos metadados do módulo via `modinfo`, verificando arquivos normais, comprimidos e padrões. Os metadados podem listar arquivos para outros modelos: arquivo ausente não comprova defeito.
- Mensagens do kernel sobre firmware, erros e timeout, filtradas das últimas 600 mensagens disponíveis, com aviso quando o journal tem acesso limitado. A ausência de mensagens não comprova ausência de problemas.
- Exportação JSON de inventário, módulos, versões de pacotes e avisos. Não inclui as mensagens do journal. Não são coletados serial de disco, senha de rede ou endereço MAC pelo inventário.

## Firmware e operações administrativas

A aba **Drivers e atualizações** consulta pacotes conhecidos para Intel, Realtek, Qualcomm/Atheros, Broadcom, MediaTek e AMD. A relação com módulos ativos/candidatos é indicativa, não uma recomendação automática de instalação. A lista padrão mostra somente firmwares relacionados ao hardware e a opção de kernel Debian. Exibe a versão instalada, a candidata do APT e a situação: disponível para instalar, atualização disponível, atualizado ou indisponível. A comparação usa as regras de versões do dpkg, incluindo epochs. Pacotes iguais ou mais antigos não são oferecidos como atualização. O catálogo completo de firmware continua acessível por opção explícita.

Selecione uma linha e use **Instalar selecionado** ou **Atualizar selecionado**. A instalação/atualização ocorre somente após confirmação explícita, seguida da autenticação polkit. **Buscar versões mais recentes** atualiza os índices do APT com autenticação e refaz a consulta. O botão **Atualizar dispositivos** apenas relê o inventário e os índices locais. O helper instalado pelo pacote:

1. Aceita um pacote de firmware da lista permitida ou `linux-image-amd64`, `nvidia-detect`, `nvidia-driver` e `nvidia-tesla-535-driver`. Para drivers NVIDIA, o helper revalida hardware, versão do detector, headers, sessão instalada e Secure Boot; não confia na seleção enviada pela interface. A única operação adicional é `--refresh`, para atualizar os índices APT. Não aceita comandos, opções adicionais ou nomes arbitrários.
2. Exige root e verifica Linux BR/Debian em `/etc/os-release`.
3. Executa Python em modo isolado e o APT por caminho absoluto, com ambiente definido, sem shell e sem herdar opções do usuário.
4. Usa `apt-get --no-remove install -y PACOTE`; não adiciona repositórios nem remove pacotes. A atualização de índices usa `APT::Update::Error-Mode=any`, para apresentar falhas de repositório em vez de anunciar sucesso parcial.

Os pacotes vêm dos repositórios já configurados no sistema. Disponibilidade depende da configuração APT, índices e conexão. Cancelamento da autenticação, falta de rede, bloqueio do APT e falhas de instalação aparecem na saída da operação. A janela não encerra normalmente enquanto a instalação está em andamento. Após instalar um pacote é recomendado reiniciar, sem reinício automático ou alteração de driver em uso. A opção de kernel segue o metapacote Debian e seus drivers integrados: a versão mostrada é do pacote, sem afirmar que cada driver recebeu uma versão nova.

No Live, alterações de firmware não são transferidas automaticamente ao sistema instalado. Para incluí-las permanentemente em futuras ISOs, a lista de pacotes do projeto deve ser ajustada deliberadamente.

Na aba de hardware, **Ver drivers e firmware deste dispositivo** filtra as opções para o dispositivo selecionado. **Todos os dispositivos** retorna à visão geral. Interfaces USB sem driver são consultadas separadamente, mesmo quando o dispositivo pai possui um driver USB genérico. Sem correspondência no catálogo, a interface informa a limitação; não declara que inexiste um driver em qualquer fonte.

## Limites da 0.4 Alpha

O gerenciamento cobre drivers fornecidos pelo kernel e firmware dos repositórios. Inclui NVIDIA proprietário empacotado pelo Debian, com DKMS/headers, conforme a seção abaixo. Não inclui instaladores externos `.run`, repositórios de fabricantes, troca do driver gráfico em execução, matrícula automática de chaves Secure Boot, flash de BIOS/UEFI ou atualização de firmware físico via fwupd. Não oferece desativação de hardware, pois desligar controladores ou descarregar módulos ativos exige tratamento próprio. Bluetooth e impressoras continuam acessíveis pelas ferramentas existentes do KDE.

A etapa 3 mantém o mesmo serviço de letras, protocolo KIO, configuração e favoritos. A correção Plymouth/SDDM e o fluxo Calamares permanecem.

## Verificação

```sh
python3 tests/test-device-manager.py
QT_QPA_PLATFORM=offscreen python3 tests/test-device-manager-gui.py
QT_QPA_PLATFORM=offscreen python3 tests/test-system-central.py
python3 tests/test-build-entrypoints.py
python3 tests/test-launchers.py
./init-build.sh
```

Os testes Qt exigem PyQt6. `tests/package-smoke.sh` deve rodar somente em container Debian descartável. Os testes de hardware usam sysfs sintético e não montam discos, carregam módulos ou instalam firmware real. O teste da interface verifica filtros, confirmação/cancelamento, indisponibilidade de candidatos, exportação sem logs e bloqueio de fechamento durante instalação.

Na nova ISO, conferir:

1. Central → Dispositivos; comparar os IDs/drivers com `lspci -k` e `lsusb`.
2. Conectar/remover um USB descartável e atualizar a lista.
3. Verificar inventário, aliases, firmware e mensagens em hardware com drivers conhecidos.
4. Cancelar uma solicitação polkit e confirmar que a interface permanece utilizável.
5. Em VM descartável, instalar um firmware escolhido e conferir o resultado do APT. Repetir sem rede para verificar a apresentação do erro.
6. Abrir discos pelas letras no Dolphin e confirmar que os favoritos, boot e login continuam funcionando.

Não foi compilada nem inicializada uma nova ISO nesta implementação. A validação de hardware real foi somente de leitura; a instalação administrativa foi testada com simulações, sem alterar firmware do host.

### Resultado desta implementação

Passaram sete testes de inventário/firmware/helper, testes Qt da nova interface e da Central, oito testes do modelo de unidades, quatro do backend, integração D-Bus/KIO real com inventário simulado, nove testes de build, sete de lançadores e o teste de layout. A leitura real do host encontrou 92 dispositivos e 53 módulos, sem operações de escrita no hardware.

Os nove pacotes 0.4.0 foram gerados em `.cache/stage4-final.6FLEhE/debs/`. O APT resolveu em simulação as dependências da Central/Dispositivos e todos os pacotes do catálogo de firmware com os componentes Debian configurados. Passaram as verificações de versão, polkit, identidade, preservação do Calamares e da liberação do Plymouth. Prévia com dados fictícios: `.cache/devices-stage4.png`.

### Simplificação da instalação

A revisão da lista automática passou em dez testes de modelo/helper no Debian, incluindo comparação real de versões com epoch, seleção por dispositivo e comandos administrativos permitidos. Os testes Qt verificaram instalação/atualização/busca de índices, confirmação/cancelamento, opções não relacionadas ocultas, bloqueio durante operação e integração da Central. A prévia com dados fictícios está em `.cache/drivers-simple.png`. Nenhum kernel ou firmware foi instalado no host; a operação administrativa real e uma nova ISO permanecem por validar.

## NVIDIA proprietário

A lista usa `/usr/bin/nvidia-detect` com o ID PCI de cada GPU NVIDIA detectada. Apenas a recomendação exata do detector pode oferecer `nvidia-driver` ou `nvidia-tesla-535-driver`; menções a alternativas e ramos legados não são tratadas como recomendação. GPUs desconhecidas e conjuntos de GPUs que exigem ramos diferentes ficam visíveis para análise, sem troca automática. O detector local pode não conhecer placas recentes; isso não prova ausência de suporte.

Para `nvidia-driver`, o detector instalado deve corresponder à versão candidata do driver. Havendo uma atualização do detector, ela aparece primeiro como ferramenta atualizável. O ramo Tesla aceito é 535. A instalação não escolhe drivers de outros fornecedores proprietários nesta entrega.

Pré-condições da instalação/atualização:

- Sistema instalado amd64, fora da sessão Live.
- Headers do kernel em execução presentes ou disponíveis no APT. Kernels personalizados sem headers disponíveis exigem intervenção administrativa.
- Secure Boot desativado, ou a chave padrão DKMS `/var/lib/dkms/mok.pub` já matriculada. Estado desconhecido bloqueia a operação; o botão **Ajuda NVIDIA** explica a preparação manual de MOK. A aplicação não desativa Secure Boot nem substitui certificados.

O helper reconsulta tudo após autenticar e inclui os headers exatos, `linux-headers-amd64` e `dkms` na transação APT com `--no-remove`. A confirmação informa a substituição de Nouveau após reiniciar. Não descarrega módulos ativos, não altera manualmente Xorg nem reinicia automaticamente. O sucesso indica instalação dos pacotes, não prova que o driver já está ativo. Após reiniciar, conferir a GPU em Dispositivos e, se necessário, `nvidia-smi` e o journal.

Testes: `python3 tests/test-nvidia.py` cobre recomendação, GPU desconhecida, conflito entre ramos, rejeição de pacotes arbitrários/legados, versão do detector, headers, Live, Secure Boot e revalidação privilegiada. Foram testados o detector Debian real com um ID PCI de teste e a resolução APT em simulação. Nenhum driver NVIDIA foi instalado no host e nenhuma GPU real foi usada na validação. Secure Boot/DKMS em máquina real permanecem por validar.

Fontes: [pacote nvidia-detect do Debian](https://packages.debian.org/trixie/nvidia-detect), [drivers NVIDIA no Debian](https://wiki.debian.org/NvidiaGraphicsDrivers) e [Secure Boot/MOK no Debian](https://wiki.debian.org/SecureBoot). Os padrões de inicialização/agrupamento do Dolphin seguem suas [configurações oficiais](https://invent.kde.org/system/dolphin/-/tree/v25.04.0/src/settings).

Pacotes finais desta revisão: `.cache/nvidia-computer-final.wSh5Sh/debs/`. A geração dos nove pacotes, validação de identidade/Calamares, testes dos lançadores/build e resolução das dependências pelo APT passaram. Não foi gerada uma nova ISO nesta revisão.


### Propriedades do sistema

A Central abre em **Sistema — Sobre**, com especificações do dispositivo e do
sistema, cópia das informações e atalhos para as demais categorias. Os dados
são lidos do sistema em execução, sem alterar hardware ou configurações.

O branding protege `/etc/xdg/kcm-about-distrorc` com `dpkg-divert`: o arquivo do
`desktop-base` fixa `emblem-debian` e versão `13`, sobrepondo `os-release`.
Linux BR usa seu SVG original e a versão completa de `os-release`; remover o
pacote restaura a configuração original. Configurações pessoais do KDE continuam
tendo precedência. A correção entra no live e no instalado após reconstruir a ISO.

Referência: https://develop.kde.org/docs/administration/kinfocenter/
Validação: navegação/cópia da página Qt e instalação, reinstalação e remoção do
branding em contêiner Debian 13. Não substitui validação visual da nova ISO.


### Broadcom b43 e b43legacy

O inventário inclui SSB e BCMA, além de PCI/USB. Os instaladores
`firmware-b43-installer` e `firmware-b43legacy-installer` aparecem relacionados
quando o módulo exato é identificado como driver ativo ou candidato pelo modalias
local. `b43legacy` não é confundido com `b43`; `brcmfmac`, `brcmsmac`, `wl` ou uma
ponte SSB/BCMA isolada não bastam para recomendar esses pacotes. Se o barramento
não estiver exposto pelo kernel, o gerenciador não afirma compatibilidade nem
carrega módulos automaticamente.

Instalação/atualização usa APT e autorização polkit; o helper confirma novamente o
hardware antes de executar. A interface avisa sobre downloads externos, necessidade
de internet (cabo ou outro adaptador) e reinicialização. Falhas são exibidas no log
e permitem tentar novamente após restaurar a conexão. A lista da ISO continua sem
os dois instaladores; nenhuma dependência nova os instala durante o build.

Referência: https://wireless.docs.kernel.org/en/latest/en/users/drivers/b43.html
Validação com fixtures de SSB/BCMA, distinção de módulos e bloqueio no helper.
Instalação real em hardware Broadcom ainda precisa ser validada.
