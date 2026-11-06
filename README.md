# Linux BR 1.0 RC 2

Distribuição experimental baseada em Debian 13, KDE Plasma 6 e Calamares, com interface em português e uso familiar para quem vem do Windows.

A 1.0 está em desenvolvimento como candidata RC 2, a partir da 0.9 Beta 1. O trabalho concentra configuração inicial, consistência da interface, Loja, compatibilidade documentada e critérios verificáveis de publicação. Consulte o [escopo e a matriz da 1.0](docs/VERSAO-1.0.md). Esta identificação ainda não representa uma versão estável aprovada.

A Loja Linux BR, o gerenciador gráfico de máquinas virtuais, as propriedades de arquivos e as ferramentas de migração continuam integrados ao sistema. O histórico abaixo reúne as alterações de cada versão.

A versão é candidata. A validação em máquinas virtuais não substitui homologação de vídeo, Wi-Fi, Bluetooth, áudio, periféricos ou suspensão em equipamentos físicos. Compatibilidade com programas e jogos Windows varia por aplicativo.

Consulte o [escopo da 0.9](docs/VERSAO-0.9.md), o [guia de Servidor e recuperação](docs/SERVIDOR-RECUPERACAO-0.9.md), as [máquinas virtuais](docs/MAQUINAS-VIRTUAIS-0.8.5.md), as [propriedades de arquivos](docs/PROPRIEDADES-0.8.md) e o [catálogo de webapps](server/webapps/README.md). As evidências e checksums entregues com os artefatos identificam os cenários efetivamente executados.

## Histórico de versões — notas de lançamento

As entradas abaixo distinguem imagens ISO, revisões de código e atualizações por pacote. As revisões incrementais não alteram retroativamente uma ISO já construída. Este histórico reúne os registros disponíveis; a ausência de uma validação não equivale à aprovação daquele recurso.

### 1.0 RC 2 — 1.0.0~rc2 — em desenvolvimento

- Revisão posterior à ISO: site de apresentação do sistema, loja pública Linux/web/Windows e administração preservada. Links `linuxbr-store://` selecionam aplicativos de fontes já habilitadas sem instalar silenciosamente. Fluxo de publicação no GitHub Releases com notas, checksums e divisão de ISOs grandes; consulta automática das versões no site. Consulte [Publicação no GitHub](docs/PUBLICACAO-GITHUB.md).
- Revisão posterior à ISO: recuperação do catálogo de aplicativos com definição de menu Plasma validada antes da reconstrução, incluindo fontes Flatpak. A opção aparece em Solução de problemas → Atalhos e menu Iniciar. O ensaio de mudança temporária de resolução preservou a abertura dos atalhos; a reconexão completa do PiKVM ainda não foi reproduzida. Consulte as [evidências do catálogo](docs/validations/application-cache-2026-11-06.json).
- Revisão posterior à ISO: lançador de janelas individuais para Bottles, com X11/Xwayland limitado ao aplicativo e preparação opcional sem área de trabalho virtual. Minimizar, restaurar e maximizar o Word foram conferidos no gerenciador de janelas do computador de referência; isso não aprova todos os recursos do Microsoft 365. Consulte [Office e janelas](docs/OFFICE-E-JANELAS.md).
- Revisão posterior à ISO: preparação do cofre seguro no início da sessão, desbloqueio pelo provedor nativo e diagnóstico de gravação/leitura com entrada temporária. Cofres existentes são preservados. Dependências do serviço e integração PAM explícitas; compilação e conferência da imagem rejeitam cofres de usuário pré-criados em contas novas. Consulte [Credenciais e logins](docs/CREDENCIAIS.md).
- Detecção de perfis web em execução compatível com o formato de título de processo usado pelo Chromium atual, inclusive quando o caminho contém espaços.
- Identificação de perfis separados mantém a distinção entre o navegador principal, processos de renderização e diretórios com nomes semelhantes.
- Verificador de pacotes usa o mesmo parser de rótulos Alpha/Beta/RC/Estável da compilação.
- Compilação verifica o espaço disponível antes de iniciar o container e recusa prosseguir abaixo de 32 GiB livres.
- A nova candidata terá seus próprios pacotes, hashes e ensaios da ISO; as evidências da RC 1 permanecem identificadas como históricas.

### 1.0 RC 1 — 1.0.0~rc1 — candidata anterior

- Identificação Alpha/Beta/RC/Estável nas ferramentas de compilação e metadados.
- Conferência de artefatos, versões, hashes e evidências antes de preparar uma publicação estável; ausência de instalação pela ISO exata permanece pendência.
- Assistente inicial com consultas de estado separadas das marcações pessoais, sem alterar configurações durante a conferência.
- Loja com avisos de consulta incompleta, nova tentativa e histórico de resultados; cancelamento DEB solicitado ao gerenciador somente quando permitido.
- Registros de compatibilidade por aplicativo e versão do Linux BR. Testes antigos permanecem históricos e não aprovam uma nova versão.
- Validação da candidata em andamento. Consulte a matriz da 1.0 para os critérios de lançamento.

### 0.9 Beta 1 — 0.9.0~beta1

- Recursos opcionais com prévia de pacotes, controle separado de serviços e reversão; central de configuração do sistema com programas de inicialização, serviços e opções de boot.
- Criação e edição gráfica de serviços, dependências, recuperação após falhas, limites, logs, importação/exportação e personalização de unidades de pacotes por overrides.
- Modos de segurança, rede restrita, terminal, vídeo básico, diagnóstico e manutenção; seleção por um boot, configuração persistente e integração Shift + Reiniciar.
- Edição Servidor com sessão mínima autenticada, terminal com caminho por letra, controles de host, contas, horário, SSH, rede, serviços, firewall e máquinas virtuais.
- Catálogo de webapps PHP/MySQL/Angular com publicação assinada, fontes confiáveis, revisões, cron e backup cifrado. Integração do cliente preserva os perfis ao aplicar alterações de metadados.
- Manutenção diária do repositório APT com renovação atômica dos metadados assinados, preservando índices, chave de confiança e pacotes publicados.
- Seleção ilustrada de Desktop ou Servidor no instalador, com identificação própria para cada edição. Inventário de recursos preserva a arquitetura dos pacotes e recusa substituições inesperadas durante remoções.
- Revisões próprias de Dolphin e KIO, com dependências que exigem os binários nativos corrigidos durante a atualização de versões anteriores.
- A distribuição permanece Beta. Consulte o [escopo e critérios da 0.9](docs/VERSAO-0.9.md) e o [guia de Servidor e recuperação](docs/SERVIDOR-RECUPERACAO-0.9.md). Os resultados de validação acompanham os artefatos, identificados por checksum; homologação física e compatibilidade de aplicativos devem ser conferidas por cenário.

### 0.8.5 Beta 1 — 0.8.5~beta1

- Configurações com 12 categorias, 106 destinos, pesquisa por nomes familiares, caminho da página, retorno e detecção dos módulos instalados. Integra páginas próprias e controles nativos do Plasma.
- Loja com início, cartões por aplicativo, categorias, biblioteca, favoritos, fontes APT/Flatpak e catálogos web/Windows. Pesquisa nas fontes, detalhes, licenças locais, fila e histórico de operações.
- Instalação de arquivos DEB e Flatpak integrada às transações da Loja, com integridade conferida. Atalhos antigos do Discover encaminhados para a Loja; serviços nativos de instalação preservados.
- Aplicação Máquinas Virtuais: criação, console, recursos, firmware UEFI/Secure Boot/TPM, dispositivos, discos, adaptadores, redes, armazenamento, estados salvos, checkpoints e hospedeiros por SSH.
- Preferências de criação por hospedeiro, histórico de conexões sem senhas, prioridade de boot e limite de CPU. Na Loja, a ação de instalar ou abrir permanece visível ao rolar descrições longas.
- CPU com recursos do hospedeiro em KVM, modelo Secure Boot com autoridades Microsoft de 2023 e atualização de certificados de VMs desligadas com checkpoint. PK, revogações e variáveis de outros namespaces são preservados.
- Cópias completas de VM desligada com discos, firmware e TPM, integridade SHA-256, importação com nova identidade e proteção contra substituição de VMs existentes. Checkpoints combinam disco e estado persistente de firmware/TPM.
- Área de transferência, permissões por aplicativo isolado, serviços, eventos, variáveis de ambiente e agendador gráfico. Alterações de sistema usam autorização administrativa nativa.
- Os resultados de compilação, instalação e regressão acompanham a imagem e os pacotes. Migração entre hospedeiros, alta disponibilidade e recursos de hardware exigem cenários próprios; a presença de um controle não comprova sua homologação.

### 0.8 Beta 1 — 0.8.0~beta1

- Propriedades integradas ao diálogo nativo do Explorador e da área de trabalho, com OK, Cancelar e Aplicar. Segurança e ACL com alcance explícito, SHA-256/SHA-512 com comparação e cancelamento, identificação de executáveis Windows, acesso às configurações do ambiente e histórico pessoal de versões.
- Compartilhamento de pastas pela extensão nativa do Samba, com estado do serviço e do firewall, endereços de rede e verificação de acesso. A publicação e a autenticação dependem das permissões reais da conta; acesso convidado exige escolha explícita.
- Importação de pastas de um disco ou backup, prévia de espaço e conflitos, cancelamento, conferência SHA-256 e relatório. A substituição preserva a versão anterior do destino; a origem permanece no lugar.
- Loja com instalação, atualização e remoção de pacotes DEB e Flatpak pelos gerenciadores nativos, confirmação de componentes e permissões, fila, progresso e histórico. A atualização de `linuxbr-release` seleciona as versões correspondentes dos componentes da edição.
- Receitas versionadas de compatibilidade, reparação de ambiente Wine com cópia de segurança e inventário Steam/Proton. Resultados são registrados por aplicativo; a presença de um mecanismo de compatibilidade não comprova funcionamento de todos os jogos.
- Perfis web com preferências próprias de downloads e permissões do Chromium, inicialização por perfil e tratamento de links externos. Favicons, contas salvas e seleção de múltiplos perfis são preservados.
- Páginas de pesquisa, programas na inicialização, aplicativos padrão e transferências, com agrupamentos, caminho da página e navegação por teclado. Alterações de inicialização e associação de arquivos podem ser desfeitas.
- Cuidados com o computador reúne estado do backup pessoal e da proteção do sistema, verificações antes de atualizar, diagnósticos guiados e limpeza conferida de cache ou lixeira. Perfis web, ambientes Windows, documentos e backups não entram na limpeza genérica.
- Manutenção do repositório PHP com verificação de assinatura, índices e certificado e renovação usando a mesma autoridade local. As entregas anteriores e seus registros permanecem preservados.

### 0.7 Beta 3 — 0.7.0~beta3

- Correção da proteção APT no ambiente de instalação: a inclusão de novos pacotes do carregador de boot não deve exigir um ponto de recuperação nem um diretório de lock previamente criado.
- Remoção da entrada duplicada do Gerenciador de Tarefas no menu da barra, preservando o acesso pelo fundo da barra e pelo menu dos programas.
- Reconexão SMB passa a abrir a listagem com autenticação nativa, permitindo solicitar credenciais já na primeira conexão e lembrar a conta no KWallet.
- Compilação, integridade da ISO, 35 suítes de componentes, instalações limpas UEFI/BIOS e primeiros logins em 1280×768 aprovados. A restauração pelo Live final retornou ao ponto 0.6, preservou 1.807 arquivos pessoais conferidos e permitiu atualizar novamente para a Beta 3 pela fonte HTTPS assinada, com reinicialização e login aprovados. Veja [validação da Beta 3](docs/VALIDACAO-0.7-BETA3.md).
- O 7-Zip 26.05 para Windows criou e verificou arquivos pelo Wine na instalação UEFI nova; ícone principal e preservação de metadados conferidos.
- A imagem Beta 2 foi reprovada para novas instalações e substituída pela Beta 3; os resultados anteriores de atualização e recuperação permanecem registrados.

### 0.7 Beta 2 — 0.7.0~beta2

- Correção da integração do menu da barra: a identificação do componente não confunde tasks com tasksModel.
- Ícone de recuperação compatível com o tema instalado.
- Documentação do servidor PHP e validação TLS ajustadas ao comportamento real do APT e do OpenSSL.
- Atualização pela fonte HTTPS assinada, proteção automática e reinicialização aprovadas. A instalação limpa UEFI revelou bloqueio do hook APT antes de instalar o GRUB no chroot; imagem reprovada para instalação e substituída pela Beta 3.

### 0.7 Beta 1 — 0.7.0~beta1

- Pontos de restauração RSYNC com Timeshift, separados das cópias de documentos. Após configurar um destino, a proteção APT cria um ponto antes de atualizações importantes e interrompe a atualização se a criação falhar.
- Central com versão instalada, candidata nos índices locais, fontes de atualização e indicação de reinicialização recomendada.
- Servidor local HTTPS em PHP para o repositório APT assinado, com chave e certificado fora do conteúdo servido.
- Loja com tipo, origem e metadados locais disponíveis; gerenciamento Linux pelo Discover.
- Extração de ícones dos executáveis Windows e diagnóstico de falhas.
- Perfis web com busca, indicação de padrão e de processo Chromium em execução.
- Reconexão explícita de unidades SMB pelo KIO/KWallet e notas de lançamento e diagnóstico na página Sobre.
- Consolidação dos ícones funcionais na imagem. Validações e limites ficam em [escopo da 0.7](docs/VERSAO-0.7.md).

### 0.6 Beta 2 + ícones — pacote 0.6.0~beta2+icons1

- Ícones por função nas 30 categorias da Central do Sistema e nos atalhos, substituindo a repetição do ícone de configurações e da seta genérica.
- Ícones nas ações de Ctrl+Alt+Del: bloquear, trocar usuário, sair, alterar senha, Gerenciador de Tarefas e cancelar.
- Diferenciação dos lançadores da Central, acesso rápido, preparação e boas-vindas. Favicons dos webapps preservados.
- Pacote instalado na VM de testes da 0.6 Beta 2; arquivos conferidos, ícones disponíveis no tema e seis testes de sessão aprovados. Central aberta e conferida visualmente.
- **Distribuição:** atualização por pacote; a ISO da Beta 2 permanece inalterada.

### 0.6 Beta 2 — 0.6.0~beta2

- Consolidação dos comandos familiares ao Windows e da execução interativa de BAT/CMD na ISO.
- Loja com inventário dos aplicativos registrados no desktop, incluindo componentes separados do LibreOffice, além de perfis web e atalhos Windows.
- Atualização por pacotes com conferência de hashes e seleção dos componentes já instalados.
- Validação de 30 suítes de componentes, instalação limpa UEFI, primeiro login e atualização preservando perfis e preferências; inicialização Live em BIOS conferida ao final.
- Instalação e uso do 7-Zip para Windows; criação, salvamento e reabertura de partida do OpenTTD para Windows pelo Wine.
- Verificação de documentos ODT/DOCX/PDF, isolamento e persistência dos perfis Chromium, restauração de arquivos e assinaturas do repositório APT em ambiente local.
- **Distribuição:** ISO e pacotes. Permanecem pendentes a publicação HTTPS, a homologação física e os testes de jogos Steam/Proton. Detalhes em [validação da Beta 2](docs/VALIDACAO-0.6-BETA2.md) e [fechamento da 0.6](docs/FECHAMENTO-0.6.md).

### 0.6 Beta 1 + terminal — pacotes 0.6.0~beta1+terminal1

- Comandos familiares como dir, cls, copy, move, del, md, rd, type, explorer, ipconfig e tasklist, com tradução de caminhos e opções documentadas.
- Execução de arquivos BAT/CMD pelo CMD do Wine, com escolha de ambiente, confirmação, entrada interativa e código de saída.
- Clique duplo para editar scripts; ações separadas de edição e execução no Dolphin.
- **Distribuição:** pacotes incrementais instalados e validados na VM UEFI, preservando a ISO original da Beta 1. Recursos posteriormente consolidados na Beta 2. Veja [terminal e BAT/CMD](docs/TERMINAL-WINDOWS-BAT.md).

### 0.6 Beta 1 — 0.6.0~beta1

- Loja com Explorar catálogo e Meus aplicativos, busca, filtros e abertura dos perfis web e atalhos Windows registrados.
- Instalação Windows com detecção de arquitetura, escolha de ambiente e descoberta de executáveis para adicionar à biblioteca.
- Perfil web preferido, seleção múltipla centralizada e exclusão confirmada de dados, separada da remoção do atalho.
- Página Uso diário e configuração inicial ampliada para oito etapas, incluindo campo para experimentar o teclado.
- Correção dos marcadores de tradução do resumo do Calamares e configuração brasileira br/pc105.
- Preparação do repositório APT assinado, sem publicação pública nem ativação automática nos clientes.
- **Distribuição:** ISO e pacotes, com testes virtuais de instalação UEFI, BIOS, atualização da 0.5, EXE/MSI e perfis Chromium. Veja [escopo](docs/VERSAO-0.6.md) e [validação](docs/VALIDACAO-0.6-BETA1.md).

### 0.5 Beta 1 — 0.5.0~beta1

- Consolidação da experiência familiar ao Windows: desktop, atalhos, ferramentas de arquivos, terminal com caminho no prompt e letras de unidade.
- Gerenciador de Tarefas independente, acesso pelo menu da barra e tela de ações de Ctrl+Alt+Del.
- Loja integrada a aplicativos Linux, programas Windows e webapps com favicon e perfis separados.
- Preparar meu computador com sete etapas opcionais e progresso pessoal persistente.
- Backup com Kup, Bup e rsync, acesso ao histórico de versões, restauração, recuperação e atualizações pelo Discover.
- **Distribuição:** ISO e pacotes; instalação UEFI, inicialização BIOS, atualização e restauração de arquivos verificadas em VMs. Veja [escopo](docs/VERSAO-0.5.md) e [validação](docs/VALIDACAO-0.5-BETA1.md).

### 0.4.8 — sessão, terminal e personalização

- Favicons dos webapps, Gerenciador de Tarefas independente, entrada na barra e tela de Ctrl+Alt+Del.
- Localização dentro do prompt do terminal, com letras de unidade, barras invertidas e navegação correspondente ao gerenciador de arquivos.
- Integração das melhorias de desktop, Executar, acesso rápido, arquivos, biblioteca Windows e ampliação do catálogo e dos aplicativos da imagem.
- **Distribuição:** a implementação inicial foi registrada como código-fonte com testes adiados; há posteriormente uma ISO 0.4.8 preservada em dist/. A consolidação e as validações posteriores estão documentadas nas versões 0.5 e 0.6. Veja [sessão, terminal e ícones](docs/IMPLEMENTACAO-SESSAO-2026-10-30.md).

### 0.4.7 — revisão intermediária

- Não há notas individuais suficientes para atribuir mudanças ou validações exclusivamente a esta revisão.
- As melhorias desse período foram consolidadas na 0.4.8. O registro da etapa informa que não havia pacote ou ISO 0.4.7 produzido naquele momento.

### 0.4.6 — múltiplos perfis de webapps

- Um perfil abre diretamente; vários perfis apresentam seleção de um ou mais para abrir.
- Novo perfil cria outra janela na página inicial com dados de sessão separados.
- Atualização da extensão Chromium para perfis persistentes, preservando os dados existentes.
- **Distribuição:** pacote de sistema instalado e verificado na VM UEFI; isolamento e persistência de cookies e armazenamento local testados em site HTTPS de laboratório. A ISO 0.4.4 não foi regenerada nessa etapa. Veja [aplicativos web](docs/APLICATIVOS-WEB.md).

### 0.4.5 — revisão intermediária

- Não há notas individuais suficientes nos registros consultados para descrever uma entrega própria desta revisão. As próximas mudanças documentadas são as dos perfis web da 0.4.6.

### 0.4.4 — loja de aplicativos

- Catálogo inicial de 27 opções: 18 aplicativos Linux, sete sites instaláveis e duas opções Windows testadas pelo Wine.
- Busca sem distinção de acentos e filtros por tipo e categoria.
- Encaminhamento ao Discover, instalação de webapps, acesso a sites oficiais e instalação Windows com confirmação.
- **Distribuição:** ISO e pacotes; atualizações posteriores ampliaram o catálogo. Veja [loja de aplicativos](docs/LOJA-DE-APLICATIVOS.md).

### 0.4.3 — aplicativos web no Chromium

- Reconhecimento de sites do catálogo e oferta de instalação como aplicativo com janela própria.
- Identificação de alternativas Linux no catálogo, controles de preferências e privacidade e integração com o menu.
- **Distribuição:** ISO e pacotes; verificação de compilação, configuração do sistema de arquivos, checksum e entradas de boot. O fluxo ampliado de múltiplos perfis pertence à 0.4.6. Veja [aplicativos web](docs/APLICATIVOS-WEB.md).

### 0.4.2 — programas Windows e jogos

- Central de compatibilidade para EXE/MSI com escolha de ambiente Wine e confirmação antes da execução.
- Wine de 32/64 bits, iniciador Steam, suporte Vulkan/Mesa nas duas arquiteturas e acesso à instalação do Bottles pelo Flathub.
- **Distribuição:** ISO e instalação UEFI verificadas em VM. A inclusão dos componentes não garante compatibilidade universal nem equivale a testes de todos os jogos. Veja [programas Windows](docs/PROGRAMAS-WINDOWS.md).

### 0.4.1 — experiência brasileira

- Primeiros passos offline, equivalências com Windows, ajuda de recuperação e exportação voluntária de informações de suporte.
- Busca da Central sem distinção de acentos, termos familiares e atalhos para arquivos, configurações, execução, tarefas e captura.
- Padrões brasileiros de idioma, teclado, corretor e fuso, além de associações Office/OpenDocument para contas novas.
- Emulador configurado para desktop de 1280×768. Veja [experiência brasileira](docs/EXPERIENCIA-BRASILEIRA.md).

### 0.4.0 Alpha — dispositivos e drivers

- Inventário PCI/USB e demais dispositivos, identificação de drivers e módulos, consulta de firmware e exportação de diagnóstico.
- Instalação e atualização de firmware e kernel pelas ferramentas Debian, com autenticação administrativa.
- Orientação para NVIDIA proprietário, headers/DKMS e verificação das condições de Secure Boot, sem trocar o driver em uso.
- **Distribuição:** ISO preservada; detalhes e limites em [dispositivos e drivers](docs/ETAPA4-DISPOSITIVOS.md).

### 0.3.0 Alpha — Central do Sistema e unidades

- Central reunindo sistema, dispositivos, armazenamento, rede, usuários e administração.
- Gerenciador de unidades com montagem pelo UDisks2, letras persistentes por usuário e atalhos de rede SMB.
- Integração Este computador no Dolphin, com agrupamento de unidades locais, removíveis e rede.
- Correção documentada da transição Plymouth para SDDM após diagnóstico de tela preta na instalação BIOS.
- Veja [Central e unidades](docs/ETAPA3-DRIVE-MANAGER.md) e [correção da tela preta](docs/CORRECAO-TELA-PRETA.md).

### 0.2 — personalização do desktop

- Etapa de personalização do Plasma: tema Linux BR, painel inferior, favoritos, padrões de interação e identidade visual no desktop e instalador.
- ISO histórica mantida como referência. Os registros atuais não isolam todas as alterações e validações dessa imagem; os detalhes de desktop e identidade foram ampliados nas versões seguintes.

### 0.1 — protótipo inicial

- Estrutura inicial de distribuição Live amd64 baseada em Debian 13, KDE Plasma e Calamares.
- Construção via Podman/live-build, geração de checksum e scripts de teste em QEMU para BIOS e UEFI.
- O README histórico classificava a construção e a instalação como experimentais e ainda pendentes de validação naquele estágio.

## Construir no Fedora

Dependências do host: Python 3, Podman, QEMU/KVM, qemu-img, edk2-ovmf e xorriso. Os nomes dos pacotes QEMU podem variar na versão do Fedora.

```bash
sudo dnf install python3 podman qemu-system-x86 qemu-img edk2-ovmf xorriso
./init-build.sh
```

O container de build é privilegiado e monta este repositório em `/src`. Cada execução cria um diretório novo `build/linuxbr-VERSAO.XXXXXX`, sem apagar a compilação anterior. São exigidos 32 GiB livres no volume do projeto; recomenda-se reservar pelo menos 40 GiB, além do espaço para VMs e compilações anteriores. A verificação inicial não reserva espaço: evite instalar VMs ou executar outros trabalhos que consumam o mesmo volume durante a compilação. Para uma sessão remota longa, execute o trabalho em um serviço de sistema que sobreviva ao encerramento da sessão gráfica. O processo não é reproduzível byte a byte: os repositórios Debian e a imagem `debian:trixie` podem atualizar.

Saídas:

- `dist/linuxbr-VERSAO-amd64.iso`
- `dist/linuxbr-VERSAO-amd64.iso.sha256`
- `dist/linuxbr-VERSAO-upstream.sha256`, hashes dos pacotes de origem do Calamares e Breeze
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

O emulador usa VGA com EDID de 1280×768 como padrão, inclusive no diagnóstico. A tela da sessão pode ser ajustada pela Central. Para testar VirtIO, use `QEMU_VIDEO_DEVICE=virtio-vga` (a resolução inicial pode variar conforme o backend gráfico do QEMU).

## Testes em VM

```bash
./tests/test-iso.sh bios
./tests/test-iso.sh bios installed
./tests/test-iso.sh uefi
./tests/test-iso.sh uefi installed
```

Instale pelo Calamares antes de executar a variante `installed`. Encerre a VM anterior antes de reutilizar seu disco. O modo `installed` não conecta a ISO.

Os discos padrão são separados: `vm/linuxbr-0.5.0~beta1-bios.qcow2` e `vm/linuxbr-0.5.0~beta1-uefi.qcow2`. A NVRAM UEFI é copiada uma vez e preservada ao reiniciar. O script procura pares OVMF sem Secure Boot; se necessário, informe `OVMF_CODE` e `OVMF_VARS_TEMPLATE`. Outros ajustes: `ISO`, `DISK_IMAGE`, `OVMF_VARS`, `RAM_MB`, `CPUS`, `DISK_SIZE` e `QEMU_DISPLAY`.

Verificar hash e entradas El Torito não prova que o sistema inicia ou instala. Execute ambos os modos e acompanhe a matriz em [Experiência brasileira](docs/EXPERIENCIA-BRASILEIRA.md).

## Organização

- `VERSION`: versão usada pelos scripts.
- `build.sh` e `scripts/build-in-container.sh`: construção em Podman/live-build.
- `config/package-lists/`: pacotes Debian.
- `config/includes.chroot/`: reservado para arquivos adicionais; a identidade foi migrada para pacotes.
- `packages/`: recursos e configurações Linux BR.
- `scripts/build-packages.py`: gera os pacotes `.deb` locais.
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

## Primeiros passos e ajuda

O aplicativo **Primeiros passos Linux BR** abre no primeiro acesso, funciona sem internet e pode ser reaberto pelo menu. Inclui equivalências com Windows, programas, arquivos, atalhos, recuperação e exportação local de informações para suporte. A Central reúne Primeiros passos e Recuperação e ajuda; sua busca aceita termos familiares e informa quando não há resultados.

Contas novas recebem Windows+E para arquivos, Windows+I para a Central, Windows+R para pesquisar/executar, Ctrl+Shift+Esc para tarefas e Print para capturas. Os arquivos padrão incluem documentos Office e OpenDocument. O Live usa locale pt_BR.UTF-8 persistente, ABNT2 e dicionário brasileiro; a escolha de idioma do instalador continua disponível. Preferências de contas existentes não são substituídas.

Veja [implementação e validação](docs/EXPERIENCIA-BRASILEIRA.md).

## Programas Windows e jogos

Abra **Programas Windows e jogos** pelo menu ou pela Central. EXE e MSI abrem
nessa ferramenta para escolher um ambiente Wine e confirmar a execução. A imagem
inclui Wine de 32/64 bits, iniciador Steam e Vulkan/Mesa nas duas arquiteturas.
Steam baixa seu cliente e Proton quando necessários; Bottles pode ser instalado
para a conta pelo botão dedicado via Flathub. Nenhum jogo comercial é incluído.
Veja [como usar, dependências e validação](docs/PROGRAMAS-WINDOWS.md).

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

A Central reúne **Firewall**, **Áudio**, **Endereços IP e DNS**, gerenciamento de grupos locais em **Usuários** e um atalho para o aplicativo independente **Gerenciador de Tarefas**. Ele também pode ser aberto pelo menu de contexto da barra e pela tela Ctrl+Alt+Del. O clique direito no botão Iniciar oferece as ações principais do sistema e o diálogo **Executar**. Consulte [escopo e validação dessas páginas](docs/CENTRAL-FIREWALL-REDE-AUDIO.md).

## Aplicativos web

Chromium é o navegador inicial para novas contas. A extensão Aplicativos web Linux BR reconhece serviços do catálogo e manifestos PWA, oferece instalação confirmada pelo usuário e evita sugestões para serviços com aplicativo Linux conhecido. O gerenciador cria atalhos e perfis separados, sem servidor de histórico. Veja [o guia e os limites da detecção](docs/APLICATIVOS-WEB.md).

## Loja de aplicativos

Catálogo selecionado com busca por nome ou finalidade, filtros por tipo e categoria, integração ao Discover, instalação confirmada de webapps e links oficiais para instaladores Windows. Veja [como usar e ampliar o catálogo](docs/LOJA-DE-APLICATIVOS.md).
