# Loja de aplicativos — Linux BR 0.4.4

A Loja reúne um catálogo selecionado de 27 opções: 18 programas Linux,
7 sites instaláveis e 2 versões Windows testadas no Wine. Abra **Loja de
aplicativos** pelo menu, pelo painel de uma nova conta ou pela Central do
Sistema → Programas. Digite um nome ou finalidade e filtre por tipo e categoria.
A busca desconsidera acentos: “ilustracoes” também encontra “ilustrações”.

## Instalação

- **Linux:** “Encontrar / instalar no Discover” pesquisa o programa nas fontes
  configuradas. Confira o resultado, a origem e as permissões e confirme a
  instalação no Discover. A loja não adiciona repositórios automaticamente.
  Alguns fornecedores também oferecem download Linux em “Abrir site oficial”.
- **Aplicativo web:** usa o mesmo índice local da extensão Chromium. O botão
  abre a confirmação existente; depois, cria o atalho com perfil separado.
  Se o site já foi instalado, o botão passa a abrir o aplicativo. Serviços que
  também possuem edição Linux são identificados na descrição.
- **Windows / Wine:** abre o site oficial para baixar o instalador. Depois use
  “Já baixei o EXE/MSI” e selecione o arquivo no gerenciador Windows. Nenhum EXE
  é baixado ou executado automaticamente. As notas informam versão e alcance
  dos testes, sem prometer compatibilidade para versões futuras.

Os dois registros Windows iniciais são 7-Zip 26.05 (instalação, compactação e
extração testadas) e SuperTux 0.7.0 (MSI, primeira fase e controles testados).
SuperTux também aparece como Linux, opção recomendada. Ark é a alternativa
nativa para arquivos compactados. Esses testes foram realizados na etapa 0.4.2.

**Pesquisar mais no Discover** permite ir além do índice selecionado. A loja
não pretende listar todos os programas da internet. O catálogo local funciona
sem conexão; downloads e serviços online exigem internet. Assinaturas, contas,
licenças, DRM e restrições dos fornecedores continuam aplicáveis.

## Manutenção

Os registros Linux/Windows ficam em `/usr/share/linuxbr/store/catalog.json`.
Os sites vêm de `/usr/share/linuxbr/webapps/catalog.json`, compartilhado com a
extensão. Atualizações do pacote linuxbr-system distribuem as revisões; não há
coleta de histórico nem serviço remoto de indexação na loja.

Cada registro define id, nome, tipo, categoria, descrição e URL oficial.
As ações usam argumentos separados e apenas ferramentas fixas. URLs passam
pela validação HTTPS do gerenciador web. Metadados são apresentados como texto,
sem executar HTML ou comandos vindos do catálogo.

## Verificação

`tests/test-store.py` verifica busca sem acentos, filtros, catálogo compartilhado,
URLs, estado vazio e separação entre descoberta e confirmação de instalação.
`tests/check-rootfs.py` exige os arquivos da loja na imagem final.
O gerenciador reutiliza os fluxos já testados do Discover, webapps e Wine.

Validação realizada em VM UEFI com resolução 1280×768:

| Verificação | Resultado |
| --- | --- |
| Quatro testes da loja com widgets Qt reais | Passaram |
| Central do Sistema, navegação e pesquisa | Passou |
| Layout inicial, preservação do painel existente e lançadores | Passaram |
| Busca VLC → Discover → autenticação → instalação | VLC 3.0.24 instalado |
| Busca Canva → confirmação → criação do aplicativo web | Instalado; botão passou a Abrir |
| 7-Zip → download oficial | Página oficial aberta no navegador padrão |
| Já baixei EXE/MSI | Gerenciador Windows aberto |
| Atualização dos pacotes release, desktop e system para 0.4.4 | Instalada na VM |
| Verificação do sistema instalado com check-rootfs.py | Passou |

A instalação do VLC e do Canva acima pertence apenas à conta de teste.
Não foram adicionados às instalações automáticas da distribuição.

## Imagem 0.4.4

ISO gerada no computador de compilação:
`/home/emericv/git/linuxbr/dist/linuxbr-0.4.4-amd64.iso` (3,3 GB).

SHA-256: `bec063959d871a737b4f805ac5c861b0ec73d4ec327915a03489a37989ecc38d`.

A compilação, a verificação da ISO e a validação do sistema Live passaram.
O boot UEFI chegou à área de trabalho em 1280×768; a loja abriu pelo novo
atalho do painel, exibindo os 27 registros na sessão nova.
Ao final, um único teste de boot BIOS também chegou à área de trabalho em
1280×768. A VM BIOS foi encerrada após a verificação; a sessão UEFI permaneceu
com a loja aberta. Não foi repetida uma instalação completa do sistema nesta
etapa; foram validados a atualização dos pacotes na VM instalada e os dois
modos de boot Live da ISO final.
