# Linux BR 0.7 Beta 3

A versão 0.7 concentra atualização, recuperação e clareza nas tarefas de uso diário. A base continua Debian 13, KDE Plasma 6, Chromium e Wine.

## Atualização e recuperação

A Central informa a versão instalada e a candidata conhecida pelos índices locais, as fontes Linux BR e a recomendação de reinicialização. O Discover mantém as confirmações e a instalação de pacotes. Um servidor local HTTPS em PHP pode distribuir o repositório APT assinado; os clientes precisam confiar no certificado local e na chave vinculada à fonte.

Timeshift em modo RSYNC protege arquivos e configurações do sistema; Kup continua responsável pelos documentos. O destino de restauração precisa ser escolhido. Depois disso, o hook APT cria um ponto antes de atualizar pacotes centrais do Linux BR, kernel, Plasma, libc, systemd, APT e dpkg. Falhas na criação interrompem essa atualização. Instalações diretas por dpkg, Flatpak e firmware não passam por esse hook. Sem destino configurado, não existe proteção automática e essa condição é informada.

A recuperação é acessível pelo ambiente Live. A restauração deve usar o mesmo modo de firmware da instalação e exige conferir o disco e o ponto escolhidos. A cópia de documentos permanece separada; não inclua pastas pessoais nos pontos automáticos do sistema.

## Aplicativos e rede

- Loja identifica o tipo e a origem, apresenta versão e tamanho quando disponíveis nos metadados locais e encaminha o gerenciamento Linux ao Discover.
- Programas Windows recebem ícone extraído do executável quando disponível, diagnóstico de falhas e orientações. A extração não executa o programa.
- Webapps preservam favicon e dados ao renomear perfis ou escolher o padrão. O indicador de execução observa o processo Chromium da própria conta; não comprova login autenticado.
- Unidades SMB podem ser reconectadas pelo KIO, com credenciais tratadas pelos mecanismos KDE/KWallet. Mensagens distinguem unidade indisponível e falhas sem prometer identificar toda causa de rede.
- Sobre oferece notas de lançamento e exportação voluntária de diagnóstico.

Veja também [servidor local PHP](REPOSITORIO-LOCAL-PHP.md), [recuperação](RECUPERACAO-0.7.md), [webapps](WEBAPPS-0.7.md), [loja e programas Windows](COMPATIBILIDADE-0.7.md) e [rede e Sobre](REDES-SOBRE-0.7.md).

## Validação e condição Beta

Os resultados de compilação, suites, atualização, instalação, repositório e restauração são registrados por imagem no relatório de validação. Testes não executados devem permanecer identificados como pendentes.

Homologação física Intel/AMD, Wi-Fi, Bluetooth, áudio, periféricos e suspensão depende dos equipamentos disponíveis. Jogos e programas reais precisam ser avaliados individualmente; a instalação de Wine, Steam ou Proton não comprova suporte a todos os títulos. Secure Boot permanece sem homologação.

Referências: [Timeshift](https://github.com/linuxmint/timeshift), [pacote Debian](https://packages.debian.org/trixie/timeshift) e [hooks do APT](https://manpages.debian.org/trixie/apt/apt.conf.5.en.html).
