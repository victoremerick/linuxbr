# Loja e programas Windows na 0.8

A Loja oferece instalação, atualização e remoção DEB e Flatpak em **Instalar / atualizar / remover**. O Discover permanece disponível para busca de outros pacotes, fontes e confirmações especiais. O fluxo Windows continua usando a janela do instalador escolhido pelo usuário.

## Pacotes Linux

Cada opção informa o gerenciador, o identificador, a origem e o alcance. DEB pertence ao sistema; Flatpak distingue instalação da conta e instalação do sistema, inclusive quando o mesmo aplicativo existe nas duas. O catálogo usa identificadores revisados. Aplicativos locais com pacote desconhecido encaminham a pesquisa ao Discover. Fontes Flatpak precisam estar previamente configuradas; a Loja não adiciona um repositório silenciosamente.

**Atualizações**, também acessível por `linuxbr-store --updates`, consulta PackageKit e o cache Flatpak e apresenta os alvos disponíveis na mesma janela. A consulta não renova índices. Se uma fonte não puder ser consultada, a lista informa que o resultado é incompleto. A atualização DEB inclui a verificação prévia de espaço, estado dos pacotes e alimentação na confirmação, quando esse diagnóstico estiver disponível na instalação. A interface considera a instalação Flatpak padrão de sistema e a da conta; instalações adicionais com nome exigem gerenciamento nativo específico.

Para DEB, a Loja usa transações D-Bus do PackageKit. Primeiro resolve a versão para a arquitetura do sistema, simula a operação e apresenta o alvo e os componentes previstos. Somente após confirmação envia a transação real; a autorização é solicitada pelo mecanismo nativo. Pacotes sem assinatura confiável, novas chaves, licenças ou mídia adicional exigem revisão pelo Discover. Não são aceitas automaticamente. O catálogo não promete uma versão ou tamanho que o gerenciador não tenha informado.

Para Flatpak, a Loja executa o gerenciador nativo com identificador, origem e alcance explícitos. As permissões, componentes, tamanho e perguntas são exibidos no painel. **Confirmar etapa** e **Recusar etapa** respondem à pergunta atual; o campo de resposta permite escolher uma opção numérica apresentada pelo gerenciador. Não há aceite automático das perguntas. A saída nativa pode usar o idioma disponível no gerenciador.

As solicitações entram em fila. Há somente um processo ativo por janela; o bloqueio por gerenciador também serializa outras janelas da mesma conta. PackageKit e Flatpak continuam responsáveis pelos bloqueios do sistema e por operações iniciadas em outros aplicativos. A porcentagem aparece quando fornecida; nos demais momentos o indicador permanece indeterminado. Uma solicitação aguardando pode ser retirada da fila. A janela não encerra um gerenciador que esteja alterando pacotes.

O histórico registra nome, operação, origem, alcance, início, término e resultado em `~/.local/share/linuxbr/store/jobs/`, respeitando `XDG_DATA_HOME`. Há registros JSON e texto. Um registro incompleto não comprova sucesso: confira o estado no gerenciador antes de repetir. A fila aguardando existe enquanto a Loja está aberta. Falha ou recusa não implica reversão de componentes que o gerenciador já tenha concluído.

**Remover programa** não faz limpeza de dados pessoais, purge, remoção de runtimes não usados ou limpeza automática de dependências. A remoção DEB usa `allow_deps=false` e `autoremove=false`; se exigir remover outros pacotes, o gerenciador pode recusá-la. **Remover atalho do menu** para Windows ou perfil web continua sendo uma operação separada e preserva programas e dados. Não existe ação de apagar todo um ambiente Wine nesta tela.

## Receitas e reparação Windows

**Receitas e compatibilidade** apresenta catálogo com esquema e revisão próprios, separado da identificação da distribuição. As receitas informam aplicativo, versão, arquitetura, versão Windows, escala, dependências, fornecedor, alternativa Linux e limites da validação. O catálogo inicial contém:

| Receita | Estado e alcance da evidência |
| --- | --- |
| 7-Zip 26.05 x64 | Testado em laboratório na base anterior: instalação, compactação, teste e extração com comparação de conteúdo. Revalidação completa na 0.8 pendente. |
| SuperTux 0.7.0 x64 | Parcial: MSI, interface e primeira fase com teclado na base anterior. Campanha completa, GPU real e revalidação na 0.8 pendentes. |
| Aplicativo x64 com Visual C++ 2015–2022 | Não testado; receita inicial, sem aplicativo específico validado. |
| Steam / Proton | Nenhum título é aprovado pela existência da integração. A compatibilidade depende do jogo, versão, antitrapaça, DRM e equipamento. |

Aplicar uma receita ajusta versão Windows e escala somente no ambiente escolhido. É possível criar um ambiente separado. A confirmação informa que outros programas do mesmo ambiente compartilham a configuração. Dependências são instaladas em ação separada, por instalador escolhido explicitamente, a partir do endereço oficial indicado; não há download ou instalação automática. O nome de um arquivo não verifica sua origem nem sua assinatura. As confirmações finais e licenças permanecem na janela do instalador.

**Reparar ambiente selecionado** executa a atualização nativa `wineboot --update`. Antes da reparação, da aplicação de receita ou da instalação de dependência indicada, cria uma cópia em `windows/backups/`. Os programas do ambiente precisam estar fechados: a ferramenta consulta `wineserver --wait` e recusa a operação se houver atividade. Não encerra programas para conseguir copiar. Espaço insuficiente, erro de cópia ou arquitetura incompatível impedem a alteração.

A cópia preserva links como links, evitando copiar automaticamente pastas pessoais e unidades às quais o Wine oferece acesso. Arquivos fora do ambiente não entram nessa cópia. Cópias incompletas são identificadas no registro e não são usadas como autorização para continuar. A cópia anterior permanece disponível para inspeção; não há restauração automática por cima de um ambiente em uso.

O bloqueio de manutenção impede abrir novos programas pelo runner enquanto o ambiente está sendo alterado. Os demais ambientes, os dados da Steam e os ambientes do Bottles não são reconfigurados. Wine e os instaladores Windows sempre executam como a conta do usuário; execução como root é recusada.

Uma operação iniciada pelas propriedades pode ser acompanhada por `linuxbr-windows --watch-job REGISTRO --environment AMBIENTE --watch-action run|configure [ARQUIVO]`. Esse modo associa o registro existente à janela e não executa o programa novamente. Identificadores e caminhos são validados; registros que sejam links simbólicos são recusados.

## Steam e Proton

**Jogos e controles** lê manifestações locais nas bibliotecas Steam registradas, incluindo a edição Flatpak. A lista mostra cada título como **Não testado nesta versão**, oferece abrir seus detalhes na Steam e consultar a pasta local `compatdata` quando existir. Essas consultas não escolhem Proton, mudam opções de inicialização, executam jogos ou alteram saves.

A seleção de Proton e o Steam Input continuam nas propriedades nativas da Steam. A ausência de `compatdata` pode indicar edição Linux ou jogo ainda não iniciado. A abertura do cliente e a presença de um manifesto não comprovam áudio, controles, antitrapaça ou desempenho 3D.

## Validação e limites

Em 3/11/2026, a base Debian de laboratório separada recebeu fontes e testes em diretório privado. Passaram 48 testes: 22 da suíte `tests/test-store-windows-08.py`, quatro de Loja, 14 de metadados/Windows 0.7 e oito de compatibilidade anterior. A suíte 0.8 cobre identificadores, escopos Flatpak, confirmação em terminal nativo, recusa antes de transação, remoção sem dependentes, seleção multiarch, histórico de falha, ordem da fila, atualização do estado instalado, cópia com links, erro de cópia, ambiente ocupado, bloqueio de manutenção, isolamento de ambientes, recusa de root, matriz, leitura Steam, abertura das cópias e acompanhamento de execução sem duplicá-la. A consulta assíncrona real de atualizações apresentou nove alvos DEB e concluiu sem alterar pacotes.

Foi exercitada a API PackageKit real em consulta e simulação de instalação de `hello`; a etapa final foi inicialmente recusada, e a ausência do pacote permaneceu igual antes/depois. Isso confirmou o formato das transações e detectou a necessidade de selecionar a arquitetura nativa entre os resultados amd64/i386. A tentativa real por SSH foi recusada pela autenticação nativa, sem contornar a política. Em seguida, a janela da Loja foi aberta pela sessão KDE: a instalação de `hello` 2.10-5 foi confirmada na lista de componentes e autorizada no diálogo Polkit. O executável retornou “Olá, mundo!” com código zero. A remoção pela mesma janela também concluiu; depois, tanto o pacote quanto `/usr/bin/hello` estavam ausentes, como no baseline. Os registros preservam separadamente a tentativa recusada e as duas operações concluídas.

Uma fixture Flatpak e seu runtime mínimo foram assinados com chave temporária própria, em repositório local e instalação de usuário com HOME/XDG privados. Instalação, execução, recusa de atualização, atualização para outro commit, segunda execução e remoção passaram pelo worker real. A recusa manteve o commit anterior; a atualização mudou o commit; a remoção preservou os dados da fixture e o runtime. Os registros e as fontes Flatpak da conta normal e do sistema permaneceram idênticos ao baseline. O teste detectou e corrigiu a recusa automática do Flatpak quando recebe perguntas por pipes: o worker agora mantém um terminal privado e encaminha somente as respostas fornecidas no painel. O ciclo também passou pela janela real de operações, renderizada fora da sessão gráfica; as capturas estão identificadas como offscreen.

Um ambiente Wine x86 novo recebeu uma receita exclusiva de teste com Windows 10 e 96 DPI. A fixture PE32 de APIs Windows executou antes e depois de uma reparação nativa com `wineboot --update`. A cópia anterior foi criada, e permaneceram iguais os hashes do documento de teste, do EXE, do registro e arquivo desktop do atalho e da configuração de outro ambiente. Os arquivos da integração e as duas cópias ocuparam 1.285 MiB. Isso valida a manutenção com a fixture, sem acrescentar homologação ao 7-Zip, SuperTux, jogos, dependências comerciais ou ambientes pessoais.

O acompanhamento de uma execução externa também foi exercitado com a fixture PE32 real. A janela apresentou o código zero e o registro do job existente; um segundo monitor do mesmo registro manteve a data de modificação do marcador de execução, sem iniciar o programa novamente.

Os resultados JSON, logs, hashes dos fontes e capturas dessa rodada ficam em `reports/0.8-beta1/store-windows/` no workspace de validação. A atualização DEB real será exercitada pela atualização integrada da distribuição, separada do ciclo temporário de `hello`. Jogos Proton, equipamentos físicos e instaladores de dependências comerciais continuam sem validação por esta rodada.

## Roteiro da atualização integrada

1. Publicar os pacotes assinados e conferir que `linuxbr-release` depende das versões exatas dos oito componentes de desktop e execução. O pacote de instalação Calamares pertence à imagem e fica fora desse conjunto de atualização da sessão.
2. Registrar versões, hashes e preferências existentes; consultar proteção, destino e espaço disponíveis. Renovar os índices pelo gerenciador nativo, preservando os repositórios configurados.
3. Na sessão KDE do laboratório, abrir a janela de atualizações da Loja e selecionar a versão 0.8 de `linuxbr-release`. A consulta da Loja usa os índices existentes e não inicia uma atualização automaticamente.
4. Conferir a simulação completa, as origens, as versões e as dependências. O pacote âncora deve reunir os componentes do Linux BR em uma transação. Recusar se surgir uma alteração fora do escopo aprovado para o laboratório, incluindo atualização de kernel nesta rodada.
5. Confirmar a operação e a autorização Polkit na janela nativa. Aguardar o resultado; registrar os pacotes efetivamente alterados, o histórico, a eventual solicitação de reinicialização e o estado do `dpkg`.
6. Reiniciar a sessão e conferir versão, propriedades KIO, Loja, perfis web, atalhos e ambientes existentes. Comparar os arquivos e preferências com o baseline. Uma versão exibida ou um código zero, isoladamente, não substitui essa conferência.

A janela de operações apresenta blocos separados para aplicativo/origem, operações e andamento/histórico. A fila aparece quando contém solicitações. Nas receitas Windows, configuração, dependências e cópias/reparação têm grupos próprios, mantendo visível o alcance compartilhado do ambiente e os ícones de cada função.

Referências dos mecanismos nativos: [transações PackageKit](https://www.freedesktop.org/software/PackageKit/gtk-doc/Transaction.html), [uso do Flatpak](https://docs.flatpak.org/en/latest/using-flatpak.html), [Wine](https://www.winehq.org/), [Proton](https://partner.steamgames.com/doc/steamhardware/proton).
