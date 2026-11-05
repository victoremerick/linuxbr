# Propriedades de arquivos e pastas na 0.8

O pacote `linuxbr-file-properties` estende o `KPropertiesDialog` do KDE. O Explorador e a área de trabalho continuam abrindo a janela nativa por **Propriedades** ou **Alt+Enter**. Não há um segundo menu de propriedades de arquivos.

## Integração

O plugin C++ `liblinuxbrfileproperties.so` é instalado em `/usr/lib/<multiarch>/qt6/plugins/kf6/propertiesdialog/`. Sua descoberta usa os metadados incorporados do KPluginFactory. A integração não depende de interceptar atalhos de teclado, manipular janelas ou abrir um diálogo substituto.

| Página | Comportamento |
| --- | --- |
| Geral | Preserva nome, ícone, associação, tamanho, datas e cálculo de pastas do KIO. Acrescenta caminho real selecionável e a localização com letra de unidade fornecida pelo serviço existente. Não usa `ctime` como criação. |
| Detalhes | Preserva a extensão nativa de metadados quando presente. Para EXE, acrescenta os campos reconhecidos do recurso VERSIONINFO, incluindo fabricante e versão, identificados como declarações do arquivo. A leitura tem limites de tamanho e profundidade. |
| Segurança | Enriquece a própria página nativa de permissões. Preserva proprietário, grupo e editor avançado de ACL de acesso/padrão. Consulta acesso efetivo da conta atual e `getfacl --all-effective`, incluindo a máscara. Informa limites de NTFS, FAT, exFAT e CIFS. |
| Validação | Substitui apenas o conteúdo visual da página nativa de checksums, mantendo seus objetos válidos. Calcula SHA-256/SHA-512 sob demanda em processo separado, com progresso, copiar, comparar e cancelar. Mudança do arquivo ou substituição do caminho durante a leitura descarta o resultado. |
| Compatibilidade | Aparece para EXE/MSI locais. Consulta os cabeçalhos pelo runner existente, oferece seleção explícita de ambiente, diagnóstico sem execução, configuração Wine e abertura/instalação confirmada. O `msiinfo` fornece a arquitetura declarada em instaladores quando disponível. |
| Compartilhamento | Preserva o editor de publicação, contas, grupos, ACL e acesso convidado do `kdenetwork-filesharing`. Acrescenta consulta do serviço/firewall, endereços UNC/SMB, copiar e abertura no Explorador para conferir o acesso. Início do serviço e liberação de uma zona ativa exigem confirmação própria; persistência é opcional. |
| Versões anteriores | Relaciona o caminho aos planos pessoais de `kuprc`, respeita inclusões e exclusões, consulta apenas destinos já disponíveis e verifica a presença do item em cada versão listada. O Kup abre o item para escolher a data e o destino de restauração. Planos rsync sem histórico, destinos desconectados e ausência de versões são informados. |
| Atalho | Mantém o editor nativo de lançadores `.desktop` e URL. Links simbólicos exibem o destino no diálogo nativo. `.lnk` recebe indicação de formato Windows e não é convertido em lançador Linux. |

A leitura de propriedades não inicia Wine, não executa o item e não altera permissões. O diagnóstico importa somente as APIs existentes de `windows_runner.py`. `start_job` continua responsável por execução, configuração, registros e proteção contra manutenção concorrente. Depois da confirmação, a ponte inicia o job uma única vez e abre `linuxbr-windows --watch-job ...` para acompanhar seu resultado sem executar novamente. Nenhum comando Wine é iniciado com autorização administrativa.

## Aplicar sem fechar

A base KIO 6.13 oferece OK/Cancelar e uma sequência interna assíncrona que aplica renomeação, permissões, extensões e ícone antes de fechar. O patch `packages/linuxbr-file-properties/patches/kio-6.13-apply.patch` acrescenta o slot `apply()` e o botão **Aplicar**, usando essa mesma sequência e mantendo a janela aberta.

O patch evita solicitações concorrentes de OK/Aplicar, remove conexões de tentativas anteriores, restabelece os botões após erro e atualiza os dados de referência por consultas KIO assíncronas, preservando URLs da área de trabalho e ACL para aplicações consecutivas. Ele mantém os símbolos existentes e acrescenta somente um slot público. Não há emulação por fechar e reabrir a janela. Sem o KIO recompilado, o plugin preserva o funcionamento original com OK/Cancelar; essa combinação não cumpre o requisito de Aplicar da 0.8.

`scripts/build-kio.sh` usa a fonte oficial Debian `kf6-kio=6.13.0-6`, aplica o patch sem tolerar contextos divergentes e produz a versão `6.13.0-6+linuxbr0.8.1`. A fonte e os binários possuem manifestos SHA-256 separados. O conjunto distribuído é `kio6`, `libkf6kiocore6`, `libkf6kiogui6`, `libkf6kiowidgets6` e `libkf6kiofilewidgets6`. Pacotes de desenvolvimento, documentação e símbolos de depuração não entram nesse conjunto.

## Alcance e operações

Na seleção única de pasta local, a opção recursiva nativa fica desabilitada até calcular e confirmar o alcance. A prévia conta arquivos/pastas sem seguir links, identifica montagens aninhadas, inclusive montagens no mesmo dispositivo, e informa erros parciais. Havendo outra montagem ou falha de leitura, a recursão permanece indisponível; o usuário seleciona separadamente as pastas elegíveis. As alterações continuam no mecanismo nativo do KIO e só começam ao aplicar.

O KIO 6.13 original carrega extensões externas de propriedades somente para seleção única. O patch permite seleção múltipla apenas para extensões que declarem `X-KDE-SupportsMultipleFiles=true`; o plugin deste pacote declara esse suporte e usa um caminho específico para vários itens. A seleção múltipla mantém Geral e Segurança nativas, seus totais, valores mistos e edição dos itens selecionados. A recursão fica desabilitada e orienta selecionar uma única pasta para conferir o alcance. Não são abertas páginas ou consultas que representariam somente o primeiro item. As permissões remotas seguem o protocolo e a autorização do servidor, sem um editor de ACL Windows fictício.

Hash de link simbólico fica desabilitado e orienta selecionar o arquivo de destino. FIFOs, dispositivos e outros itens que não sejam arquivos regulares são recusados. Um hash igual à referência não confirma segurança do programa nem identidade do fornecedor. Assinaturas permanecem **não verificadas** sem verificador e cadeia de confiança suportados.

Configurar Wine afeta o ambiente explicitamente selecionado e seus demais programas. Abertura/instalação tem confirmação própria e seu resultado fica no gerenciador existente. Publicar uma pasta não altera automaticamente serviço ou firewall. A extensão nativa faz a configuração da pasta e das contas; o complemento solicita operações de serviço pela autorização nativa do sistema e nunca escreve diretamente em `smb.conf`.

Início do SMB e liberação do firewall apresentam resultado em janela própria que acompanha a operação até terminar, mesmo se a janela de propriedades for fechada. A liberação exige uma zona de rede ativa escolhida pelo usuário. Cancelar as propriedades não desfaz publicação, instalação, configuração de rede ou restauração já concluída.

O histórico pessoal usa o ramo `kup` do repositório bup e abre `kup-filedigger --path <caminho> <repositório>`. A lista só inclui versões em que o item foi encontrado; a consulta informa quando foi parcial. O explorador nativo oferece abrir/restaurar e permite escolher outro destino. Não cria planos, não monta discos e não usa pontos Timeshift como versões de documentos.

## Compilação e testes

Dependências de compilação do plugin: `extra-cmake-modules`, `qt6-base-dev`, `libkf6coreaddons-dev`, `libkf6kio-dev` e `libkf6widgetsaddons-dev`. A compilação do KIO usa os `Build-Depends` da fonte oficial `kf6-kio` dentro do construtor Debian.

Dependências funcionais: `linuxbr-system`, `linuxbr-drive-manager`, `python3`, `python3-dbus`, `acl`, `kdenetwork-filesharing`, `samba`, `samba-common-bin`, `firewalld`, `kup-backup`, `bup` e `msitools`, além das bibliotecas obtidas por `dpkg-shlibdeps`.

```sh
cmake -S packages/linuxbr-file-properties/native -B build/properties -DBUILD_TESTING=ON
cmake --build build/properties -j2
ctest --test-dir build/properties --output-on-failure
python3 tests/test-file-properties-08.py -v
python3 tests/test-file-properties-integration-08.py -v
```

Para exigir a integração Aplicar no ambiente de validação com o KIO recompilado:

```sh
LINUXBR_REQUIRE_APPLY=1 ctest --test-dir build/properties --output-on-failure
```

O teste nativo abre o `KPropertiesDialog` real com arquivo de nome acentuado, confirma a descoberta das páginas, calcula hashes e compara referências. Com o patch, verifica quatro aplicações consecutivas, duas renomeações e uma edição de permissões revertida, mantendo o mesmo diálogo. Um segundo teste abre duas pastas no diálogo real e verifica a preservação da seleção, a recursão desabilitada e a ausência de páginas referentes somente ao primeiro item.

Validações registradas entre 3 de novembro e 4 de novembro de 2026, 00:56 UTC:

- 15 testes do backend passaram em diretório privado, cobrindo SHA-256/SHA-512, arquivo vazio/alterado/substituído, recusa de links e FIFO, cancelamento de processo, árvore com links/montagem, configuração Kup, presença do item no histórico, recurso PE, recusa de Wine como root, execução única com acompanhamento e limites de serviço/firewall.
- KIO recompilado a partir da fonte oficial Debian 6.13.0-6; os cinco pacotes runtime passaram a conferência SHA-256. O plugin e os verificadores nativos compilaram em contêiner Debian 13, usando essas bibliotecas extraídas em prefixo isolado.
- Dois testes nativos passaram com `LINUXBR_REQUIRE_APPLY=1`: hashes SHA-256/SHA-512 e referência correspondente/divergente; quatro aplicações consecutivas, duas renomeações e permissões revertidas na mesma janela; seleção de duas pastas com recursão desabilitada e sem páginas referentes somente ao primeiro item. A presença do símbolo `apply()` e o carregamento das bibliotecas do prefixo foram conferidos.
- Quatro capturas offscreen foram inspecionadas em 1000×650, sem cortes ou sobreposição nas páginas Geral, Segurança, Validação e Versões anteriores. O ambiente de compilação usa locale de teste; isso não valida ainda a sessão Plasma em português.
- Na sessão de laboratório, como usuário normal, os 15 testes do backend passaram novamente. Um teste bup real criou duas versões, encontrou arquivo com acentos/espaços e pasta vazia, restaurou para outro destino, conferiu SHA-256 da versão antiga e preservou o arquivo atual.

Os logs, manifestos e capturas estão em `reports/0.8-beta1/properties/`. `ROTEIRO-INTERFACE.md` descreve os casos da fase instalada e os pré-requisitos observados. As fixtures persistentes ficaram em `/home/brasil/qa08-properties-integration/fixtures`, com configuração pessoal de teste separada. Preparar as fixtures não alterou contas, ACL, grupos, serviços ou publicações.

Permanecem necessários no ambiente instalado: clique direito e Alt+Enter no Dolphin e na área de trabalho Plasma Wayland; edição pela interface com Aplicar/Cancelar; ACL efetiva e recursão em árvore de laboratório; EXE/MSI no ambiente selecionado; leitura/gravação SMB autenticada e recusa de usuário; interrupção da publicação preservando arquivos; restauração pela interface do Kup com hash conferido; fontes remotas e somente leitura. Resultados de testes unitários, de restauração por comando e offscreen não substituem esses fluxos.

## Referências técnicas

- [KPropertiesDialog](https://api.kde.org/kpropertiesdialog.html) e [KPropertiesDialogPlugin](https://api.kde.org/kpropertiesdialogplugin.html).
- [Fonte Debian kf6-kio da base](https://packages.debian.org/source/trixie/kf6-kio).
- [Compartilhamento nativo no Debian 13](https://packages.debian.org/trixie/kdenetwork-filesharing) e [implementação do editor](https://invent.kde.org/network/kdenetwork-filesharing).
- [Fonte Kup: plano pessoal e explorador de versões](https://invent.kde.org/system/kup).
- [ACL POSIX e máscara efetiva](https://man7.org/linux/man-pages/man5/acl.5.html).
- [Formato PE e recursos de imagem](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format).
- [Fonte msiinfo](https://gitlab.gnome.org/GNOME/msitools).
