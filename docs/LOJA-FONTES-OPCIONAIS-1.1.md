# Fontes opcionais e listas de aplicativos

Snap Store e Homebrew Core aparecem em **Loja → Fontes** e começam desabilitados para cada conta. Selecione a fonte e escolha **Configurar Snap ou Homebrew…** para abrir o pacote `snapd` na Loja ou o guia oficial do Homebrew. Depois de configurar o gerenciador, habilite a fonte na mesma página. A busca, a Biblioteca e as operações da Loja passam a incluir aquela fonte.

## Snap Store

Os detalhes mostram publicador, canal, revisão e confinamento declarado pelo pacote. A instalação pela Loja usa o canal estável. Aplicativos `classic` pedem uma confirmação específica pelo acesso ampliado a arquivos e recursos. Se o snapd confirma AppArmor utilizável com confinamento parcial, a Loja usa a instalação e a atualização nativas e informa que os perfis de isolamento são mais permissivos nesse kernel. Quando o suporte de isolamento está indisponível, o diálogo indica o requisito e bloqueia instalação e atualização. Atualizações automáticas e adiamentos seguem o estado do próprio snapd. [Instalação no Debian](https://snapcraft.io/docs/tutorials/install-the-daemon/debian/) · [AppArmor no snapd](https://github.com/canonical/snapd/blob/2.68.3/interfaces/backends/backends.go#L83)

Instalações, atualizações e remoções exigem autorização administrativa. Aplicativos gráficos usam os atalhos do snapd no menu Iniciar. Atualização e remoção atuam sobre a instalação Snap selecionada.

## Homebrew Core

A Loja reconhece o prefixo padrão `/home/linuxbrew/.linuxbrew` na conta proprietária. A busca oferece fórmulas do catálogo Homebrew Core com pacote binário para a arquitetura Linux em uso. As fórmulas aparecem em **Ferramentas de terminal** e usam o mesmo prefixo para instalação, atualização e remoção. Consulte a ficha da fórmula para conferir o comando disponível. O guia oficial descreve os pré-requisitos e a instalação inicial do Homebrew. [Homebrew no Linux](https://docs.brew.sh/Homebrew-on-Linux)

## Controle da organização

O arquivo `/etc/linuxbr/store-optional-sources.json` pertence a `root` e só pode ser gravado por ele. Cada chave booleana com valor `false` bloqueia a fonte correspondente na Loja. A Loja verifica a política ao consultar e antes de iniciar uma operação. As preferências pessoais ficam no diretório de configuração da conta.

```json
{
  "snap": false,
  "brew": false
}
```

## Reinstalar em outro computador

Use **Loja → Biblioteca → Exportar aplicativos…** para salvar uma seleção de Flatpak, Snap, Homebrew, DEB, webapps e Wine. O JSON guarda o formato, identificador, versão observada quando disponível, origem e escopo. Para Snap, guarda também o canal, a revisão e o confinamento. O arquivo contém apenas os metadados usados para localizar e reinstalar os aplicativos.

Em **Importar aplicativos…**, confira os itens existentes, a fonte, a versão anterior e a versão disponível quando o gerenciador a informa. Selecione os itens para adicionar à fila. Fontes desabilitadas, pré-requisitos ausentes e canais Snap fora do estável aparecem como ações manuais. Use **Revisar fontes…** para conferir a configuração. A importação reaproveita o gerenciador da origem registrada e lê também as listas anteriores de Flatpak.

Para referências DEB, webapps e Wine, selecione o item e use **Pesquisar na Loja**. A lista usa nomes e identificadores para localizar o aplicativo. A escolha da fonte, do site ou do instalador ocorre no fluxo correspondente da Loja. Perfis e instaladores locais são configurados no computador de destino.

## Evidência de compatibilidade

A janela de operações associa cada resultado de teste ao formato, origem e artefato que foram ensaiados. O ensaio de laboratório do **Hello 2.12.3** comprovou instalação, identificação na Biblioteca, execução e remoção do pacote Homebrew Core `x86_64_linux`. A ficha apresenta o SHA-256 do pacote e mantém separado o estado de teste da versão do Linux BR.

Na VM Linux BR 1.1 Alpha 1, o Snapd 2.68.3 consultou o GNOME Calculator e informou AppArmor utilizável com confinamento parcial. O kernel Debian `6.12.115+deb13.1-amd64` carece dos recursos de mediação `dbus` e `network`. A Loja anterior recusou a instalação por exigir confinamento completo. Os testes da correção conferem que a Loja aceita o perfil parcial suportado, apresenta seu estado e encaminha a operação nativa. O ciclo gráfico completo ainda requer ensaio com o pacote da Loja atualizado.
