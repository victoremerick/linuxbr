# Loja e programas Windows na versão 0.7

A Loja reúne três tipos de aplicativo: Linux, aplicativo web e Windows / Wine. O tipo aparece na lista e nos detalhes. A instalação Linux continua no Discover, com a origem, as permissões e as confirmações apresentadas pelo gerenciador de pacotes.

## Informações de instalação

Em **Meus aplicativos**, selecione um aplicativo para consultar:

- Pacote DEB: nome do pacote proprietário do arquivo de aplicativo, versão instalada e tamanho instalado declarado pelo pacote. O Discover apresenta o repositório e as atualizações disponíveis.
- Flatpak: versão, tamanho informado pelo Flatpak, origem e instalação para o usuário ou para o sistema, quando esses dados estão disponíveis.
- Programa Windows: ambiente Wine correspondente e tamanho do EXE. Esse tamanho não inclui as bibliotecas, os outros arquivos do programa ou o ambiente. Consulte a versão em Sobre / Ajuda no próprio programa.
- Aplicativo web: endereço do fornecedor, atualização pelo próprio serviço e indicação de armazenamento variável por perfil. O navegador é compartilhado entre os aplicativos; as contas continuam em perfis separados.

O catálogo não inventa uma versão ou um tamanho de download. Dados indisponíveis aparecem como tal. Consultas locais têm limite de tempo e não atualizam repositórios nem instalam pacotes. Aplicativos registrados manualmente podem não ter pacote de origem identificado.

## Abrir e remover

O botão **Abrir aplicativo** utiliza o registro de aplicativos da sessão. Atalhos Linux que usam o mesmo executável com argumentos diferentes continuam separados, como Writer, Calc e Impress.

**Atualizar / desinstalar no Discover** abre o gerenciador nativo. Escolha a instalação e confirme a operação na janela do Discover. Na Loja, **Remover atalho do menu** continua preservando programas e arquivos dos aplicativos Windows e os dados dos perfis web.

**Gerenciar / desinstalar no ambiente Wine** seleciona o programa e o ambiente corretos. O botão **Desinstalar programas** solicita confirmação antes de abrir o desinstalador do Wine. A seleção e a confirmação final do programa são feitas nessa janela. Não é uma remoção automática de toda a pasta do ambiente.

## Ícones dos executáveis

Ao adicionar ou renomear um atalho Windows, o sistema lê os recursos de ícone do EXE com `wrestool`, do pacote `icoutils`. O EXE não é executado para extrair o ícone. O recurso ICO é validado, salvo na conta do usuário e utilizado no menu, na lista de programas e na Loja.

Quando houver vários grupos, a seleção prefere o recurso de identificador 1, depois o menor identificador numérico disponível. Grupo e idioma são informados explicitamente à extração para evitar que um logo secundário substitua o ícone principal. A listagem tem limite de 64 KiB e quatro segundos; a leitura do ICO tem limite de 16 MiB e oito segundos. Arquivos EXE maiores que 256 MiB usam o fallback.

Para atalhos já existentes, selecione **Atualizar ícone do EXE**. Quando não houver recurso utilizável, a extração exceder o limite ou a ferramenta não estiver disponível, permanece o símbolo do Wine. Remover um atalho também remove sua cópia local de ícone e mantém o EXE.

Os aplicativos web continuam usando o favicon do site. Os aplicativos Linux usam seus ícones registrados.

## Diagnóstico

**Diagnóstico do programa** consulta o arquivo, o formato x86/x64, o ambiente e a presença do Wine sem abrir o EXE. **Diagnóstico da última execução** acrescenta o código de saída e os indícios encontrados no registro. As orientações diferenciam biblioteca ausente, mistura de arquiteturas e referências a componentes gráficos, sem apresentar esses indícios como causa comprovada.

Há orientações específicas para os executáveis do 7-Zip e do OpenTTD e orientação geral para os demais. Elas apontam alternativas Linux e documentação do fornecedor. Nenhuma biblioteca ou ajuste é aplicado automaticamente pelo diagnóstico.

Atalhos iniciados pelo menu acompanham o resultado em segundo plano. Se o processo retornar erro, a ferramenta abre o diagnóstico. Um código de sucesso confirma somente o retorno do processo; não comprova todos os recursos do programa nem o comportamento de processos auxiliares que ele possa ter iniciado.

Os registros ficam em `~/.local/share/linuxbr/windows/jobs`, respeitando `XDG_DATA_HOME`. Podem conter nomes de usuário, caminhos e mensagens do aplicativo. O diagnóstico e os registros permanecem locais; confira o conteúdo antes de copiá-los para compartilhar.

## Validação

`tests/test-store-windows-07.py` cobre metadados DEB e Flatpak, dados indisponíveis, consultas com limite de tempo, seleção de grupo e idioma em um PE com múltiplos ícones, extração e leitura do ICO pelo Qt, limites de saída e tempo, fallback, proteção contra links simbólicos, preservação do EXE ao remover um atalho, diagnóstico sem execução, cancelamento de desinstalação e apresentação de erro ao iniciar pelo menu.

Execute também as suítes existentes de Loja, registro de aplicativos, compatibilidade Windows, comandos Windows e regressão da 0.6. Os testes de unidade não substituem a abertura de aplicativos reais na VM nem a homologação de cada programa ou jogo em hardware físico.

Referências de implementação: [wrestool no Debian](https://manpages.debian.org/trixie/icoutils/wrestool.1.en.html) e [comandos do Flatpak](https://docs.flatpak.org/en/latest/flatpak-command-reference.html#flatpak-list).
