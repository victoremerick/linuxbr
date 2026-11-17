# Linux BR 1.1.1 Alpha 1

Pré-lançamento do Linux BR Desktop, baseado em Debian 13 e KDE Plasma.

- O Explorador reúne os comandos nas abas Início, Visualização e Pesquisar. As Opções de Pasta controlam separadamente a exibição de itens ocultos e de sistema. A busca apresenta o título sem códigos de escape.
- A Wiki funciona offline e oferece ajuda contextual pelo F1 nas telas documentadas.
- Configurações, Loja, Gerenciador de Tarefas, Discos, Dispositivos e Máquinas Virtuais receberam melhorias de navegação e de disponibilidade das ações. O seletor de perfis web mostra quantos perfis serão abertos.
- A migração limpa a prévia quando a origem ou o destino muda. O gerenciador de dispositivos localiza as ferramentas de consulta de módulos e firmware na sessão gráfica.
- O código inclui integração entre computadores e recursos do VM Server. Consulte o [escopo e estado da validação](https://github.com/victoremerick/linuxbr/blob/v1.1.1-alpha1/docs/VERSAO-1.1.1.md) para os cenários cobertos.
- A imagem instala os codecs adicionais do GStreamer de 32 bits quando o Debian oferece dependências compatíveis entre i386 e amd64.

Confira os arquivos com `SHA256SUMS`. Para usar a ISO em pendrive, reúna primeiro todas as partes e confira a imagem completa com `ORIGINAL-SHA256SUMS`.

Para atualizar uma instalação Desktop do Linux BR 1.1 Alpha 1, verifique e extraia o arquivo de pacotes em uma pasta vazia e execute `sudo apt install --no-remove ./*.deb` nessa pasta. A pasta deve conter somente os pacotes Desktop da publicação.
