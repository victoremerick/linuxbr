# Aplicativos web na versão 0.7

O gerenciador de aplicativos web mostra cada perfil com o favicon do site, o nome escolhido, o domínio e os indicadores **Em execução**, **Fechado** e **Padrão**. A busca encontra aplicativos por nome, perfil ou endereço. O estado é atualizado a cada dois segundos, sem alterar o perfil selecionado.

## Perfis e abertura

- Com apenas um perfil salvo, o aplicativo abre diretamente.
- Com vários perfis, a caixa central permite escolher um ou mais para abrir. O perfil padrão aparece marcado inicialmente.
- É possível renomear o perfil e escolher ou retirar o padrão tanto pelo gerenciador quanto pela caixa de escolha. Alterar o padrão não muda as caixas já marcadas na seleção atual; a nova preferência vale para as próximas aberturas.
- Cada site possui seu próprio padrão. A preferência utiliza o identificador permanente do perfil e continua válida após uma mudança de nome.
- Renomear não move nem recria o diretório do Chromium. Cookies, armazenamento local, contas e favicon são preservados.
- Remover do menu preserva os dados para restauração. Apagar os dados exige confirmação e bloqueia a operação se o perfil estiver em execução ou possuir o bloqueio do Chromium.

## Significado do estado

**Em execução** significa que existe um processo principal do Chromium pertencente ao usuário atual e usando o diretório exato daquele perfil. O gerenciador não lê títulos de janelas, URLs visitadas, cookies ou identidade de contas. O indicador não informa quantas janelas estão abertas nem confirma se a conta está autenticada; um navegador que continua em segundo plano também pode aparecer em execução.

Um arquivo de bloqueio antigo não é suficiente para marcar um perfil como aberto. Por precaução, esse arquivo continua impedindo a exclusão dos dados, como nas versões anteriores. Quando não há processo acessível correspondente, o indicador exibe **Fechado**. Processos de outros usuários, outros programas e perfis externos não entram na lista.

## Validação

`tests/test-webapps-07.py` exercita preservação de dados e favicon ao renomear, padrão independente por site, retirada do padrão, preferências inválidas, detecção de processos, bloqueio de exclusão, busca, atualização da lista e seleção múltipla com os componentes Qt reais.

Executar no ambiente Linux com Python 3 e PyQt6:

```sh
QT_QPA_PLATFORM=offscreen python3 tests/test-webapps-07.py
QT_QPA_PLATFORM=offscreen python3 tests/test-webapps.py
QT_QPA_PLATFORM=offscreen python3 tests/test-webapps-gui.py
QT_QPA_PLATFORM=offscreen python3 tests/test-version-06.py
```

Os testes usam diretórios temporários e marcadores de dados, sem acessar contas reais. A verificação de sessões reais do Chromium continua sendo uma etapa separada de integração.
