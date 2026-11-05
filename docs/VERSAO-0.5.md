# Linux BR 0.5 Beta 1

## Situação

Versão de preparação: `0.5.0~beta1`. O sufixo mantém a ordenação dos pacotes Debian antes da versão final `0.5.0`. A identificação exibida é `0.5.0 Beta 1`.

ISO gerada e conferida por checksum. Instalação UEFI e boot BIOS validados em máquinas virtuais, com área de trabalho em 1280×768. Consulte [os resultados e limites](VALIDACAO-0.5-BETA1.md).

## Entregas integradas

- Área de trabalho, atalhos, execução de comandos e ferramentas de arquivos familiares ao público que vem do Windows.
- Gerenciador de Tarefas independente, acesso pela barra e tela de ações de Ctrl+Alt+Del.
- Terminal com localização dentro do prompt, letras de unidade e navegação correspondente aos caminhos do gerenciador de arquivos. O interpretador continua sendo Bash.
- Loja com aplicativos Linux, programas Windows via Wine e aplicativos web no Chromium. Compatibilidade varia conforme o programa, proteção e requisitos; não há garantia geral de executar todo programa ou jogo Windows.
- Aplicativos web com favicon, contas persistentes e perfis separados. Um perfil abre diretamente; vários permitem escolha múltipla.
- Configuração inicial opcional pelo menu e pela tela de boas-vindas. Sete etapas cobrem rede, idioma, tela, dispositivos, backup, atualizações e aplicativos. As marcações são pessoais, persistem por conta e não representam verificações automáticas.
- Backup e recuperação com acessos próprios e na Central. O Kup configura planos de cópia com versões ou sincronização; o explorador de versões permite escolher um repositório para restauração. Nenhum plano ou exclusão é aplicado automaticamente.
- Atualizações e aplicativos instalados pelo Discover, ajuda para recuperar dados pelo ambiente Live e exportação do relatório de suporte.

## Uso

No menu, abra **Preparar meu computador** ou **Backup e recuperação**. Na Central, use **Backup e recuperação** ou **Atualizações**. As configurações de backup ficam na conta atual; escolha um disco externo e confira a primeira cópia antes de depender dela. Para restauração inicial, prefira uma pasta diferente da original.

As novas dependências do sistema são `kup-backup`, `bup` e `rsync`. A instalação e atualização de pacotes permanece nas ferramentas Debian e Discover. Esta etapa não cria um repositório próprio de atualizações nem atualiza automaticamente entre versões principais da distribuição.

## Validação e próximas etapas

A validação cobre instalação UEFI, atualização de componentes preservando configurações, programas Windows de teste, perfis Chromium, restauração de arquivos e boot BIOS. Hardware físico, jogos com proteção, contas reais autenticadas e agendamentos automáticos de backup ainda exigem avaliação. O resumo do instalador apresenta rótulos incompletos de fuso e modelo de teclado; o leiaute aplicado foi br, com modelo pc105.

## Referências

- [Kup no Debian Trixie](https://packages.debian.org/trixie/kup-backup).
- [Arquivos e tradução do pacote Kup](https://packages.debian.org/trixie/amd64/kup-backup/filelist).
- [Bup](https://packages.debian.org/trixie/bup) e [rsync](https://packages.debian.org/trixie/rsync).

