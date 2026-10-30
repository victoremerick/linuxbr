# Sessão, terminal e ícones — 30/10/2026

Implementação em código-fonte da versão **0.4.8**, atendendo aos quatro requisitos
registrados em 29/10. Testes, compilação, instalação de pacotes e geração de ISO
permanecem adiados. A última ISO continua sendo a 0.4.4 e o último pacote
anteriormente validado continua sendo o 0.4.6.

## Ícones dos aplicativos web

O novo `webapp_icons.py` consulta a página inicial do serviço, procura seus links
de favicon e tenta `/favicon.ico` como alternativa. O ícone é convertido em PNG
e guardado em `~/.local/share/linuxbr/webapps/icons/`, compartilhado pelos perfis
do mesmo aplicativo. Não acessa cookies, senhas ou dados de login.

A busca ocorre em processo separado, com limites de tamanho, dimensões, tempo e
redirecionamentos. Apenas HTTPS com endereços públicos é aceito. O endereço de
conexão é fixado após resolver o domínio; redirecionamentos passam pela mesma
verificação. Os decodificadores aceitos são PNG, ICO, JPEG, WebP, GIF e BMP;
favicon disponível somente como SVG pode exigir a alternativa `/favicon.ico`.

A loja e a lista de aplicativos web atualizam os ícones sem interromper a
interação. Instalar ou abrir um aplicativo agenda a busca e atualiza os atalhos
dos perfis existentes. Os atalhos passam a apontar para o arquivo do favicon.
As janelas do Chromium mantêm sua identificação por perfil e pelo próprio site.
Quando o download não é possível, permanece o ícone alternativo existente.

Um ícone válido é reutilizado por sete dias; uma tentativa sem êxito aguarda ao
menos uma hora. O gerenciador não apaga contas nem recria perfis para mudar ícones.

## Gerenciador de Tarefas independente

O programa `linuxbr-task-manager` já possuía janela própria. Foram removidas a
instância embutida e a categoria da Central, que antes criava e consultava os
processos mesmo sem abrir a página. Os acessos no menu Iniciar, em Windows+X e
na administração agora lançam diretamente o aplicativo separado.

Ctrl+Shift+Esc continua associado ao programa. A chamada antiga da Central com
`--page 'Gerenciador de tarefas'` redireciona ao aplicativo independente para
preservar atalhos antigos. O menu usa o nome Gerenciador de Tarefas.

O mecanismo reversível de personalização do Plasma recebe a entrada de tarefas
no menu de contexto do painel, na área livre da barra de aplicativos e no menu
de uma tarefa. As alterações usam trechos reconhecidos da versão de origem;
se o arquivo mudar de estrutura, o componente é preservado e uma mensagem é
registrada pelo instalador. O pacote de ícones de tarefas usa a implementação
compartilhada do gerenciador de tarefas do Plasma.

## Ctrl+Alt+Del

`linuxbr-session-actions` abre uma janela azul em tela inteira na tela do
ponteiro, com Bloquear, Trocar usuário, Sair, Alterar uma senha, Gerenciador de
Tarefas e Cancelar. Tab navega, Enter ativa o botão em foco e Esc cancela.
Uma trava por conta evita duplicar a tela.

Bloquear usa a interface de bloqueio do desktop. Trocar usuário bloqueia antes
de solicitar a tela de entrada ao gerenciador de sessão; quando indisponível,
apresenta uma explicação. Sair abre a confirmação nativa de encerramento.
Alterar uma senha abre o módulo nativo de usuários e autenticação, onde a conta
e suas permissões são verificadas. O aplicativo não coleta senhas.

O atalho é preparado em `/etc/skel/.config/kglobalshortcutsrc`, com a associação
de saída original liberada para evitar conflito. Isso prepara contas novas;
preferências de atalhos já personalizadas em contas existentes não são
sobrescritas. Nessas contas, o novo programa também aparece no menu e pode ser
associado em Configurações → Atalhos. Não se trata de uma tela de bloqueio ou
de uma sequência de atenção segura; o bloqueio real é responsabilidade do desktop.

## Localização no terminal

O modo de letras agora escreve a pasta antes de cada comando, por exemplo
`D:\Projetos> `. O caminho é atualizado pelo mesmo serviço de unidades usado
pelo Explorador de arquivos, incluindo letras de compartilhamentos de rede.
A apresentação usa barras invertidas. C: continua correspondendo à raiz do
sistema conforme o mapeamento existente, sem inventar pastas ou outra base de letras.

O título da aba passa a ser Terminal e deixa de receber o caminho pelo novo
adaptador. Para navegar, usar `D:`, `cd 'D:\Minha pasta'` ou `cd D:/Projetos`.
As aspas são necessárias para preservar barras invertidas e espaços no Bash.
O shell e seus comandos permanecem Bash; esta alteração não implementa CMD.
`terminal-modo linux` continua disponível como escolha por janela.

O prompt expande uma variável de caminho sem transformar nomes de diretórios
em comandos. Hooks anteriores e funções pessoais de `cd` continuam preservados.
O perfil Konsole e a ajuda do terminal foram atualizados.

## Fontes de implementação

- [Interfaces de sessão Plasma 6.3](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/libkworkspace/sessionmanagement.cpp)
  e [atalhos de sessão](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/startkde/session-shortcuts/main.cpp).
- [Painel Plasma 6.3](https://github.com/KDE/plasma-desktop/blob/Plasma/6.3/containments/panel/contents/ui/main.qml),
  [barra de tarefas](https://github.com/KDE/plasma-desktop/blob/Plasma/6.3/applets/taskmanager/package/contents/ui/main.qml)
  e [menu de tarefa](https://github.com/KDE/plasma-desktop/blob/Plasma/6.3/applets/taskmanager/package/contents/ui/ContextMenu.qml).

## Validação futura

Nada desta versão foi executado nesta etapa. Conferir os patches QML na versão
Debian instalada, os menus do painel e de ícones, o atalho sem conflitos em conta
nova, a seleção de tela e as ações de sessão, inclusive permissões de troca de
usuário. Conferir favicons de diferentes formatos, ausência de rede, redirects,
perfis existentes e identificação de janelas no Wayland e no X11. Conferir prompt,
diretórios com espaços e caracteres especiais, unidades removíveis e redes.

O agendamento automático permanece pausado. Esta implementação foi solicitada
diretamente, sem reativar a recorrência.
