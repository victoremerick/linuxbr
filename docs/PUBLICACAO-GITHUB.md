# Publicação do Linux BR no GitHub

O destino oficial das versões é
[GitHub Releases](https://github.com/victoremerick/linuxbr/releases).
A página inicial do site consulta as versões públicas desse repositório e mostra
até três lançamentos, diferenciando versões de avaliação das estáveis. Em caso
de erro ou ausência de releases, apresenta um aviso e mantém o link direto.

## Preparar uma versão

1. Compile e valide a ISO e os pacotes da versão indicada em `VERSION`.
2. Escreva as notas em Markdown: mudanças, requisitos, procedimentos de instalação
   e atualização, problemas conhecidos e resultados efetivamente verificados.
3. Faça commit das fontes correspondentes à compilação. Não use uma ISO antiga
   para representar mudanças de código posteriores nem renomeie uma candidata
   como estável sem validação.
4. Autentique o GitHub CLI (`gh`) na conta com permissão de publicação. Não grave
   tokens no repositório, nas notas ou nos arquivos públicos do site.
5. Confira o plano com `--dry-run` e prepare o rascunho:

```sh
python3 scripts/publish-github-release.py \
  --artifact /caminho/linuxbr-VERSAO-amd64.iso \
  --artifact /caminho/linuxbr-VERSAO-fontes.tar.gz \
  --notes /caminho/notas-da-versao.md --dry-run

python3 scripts/publish-github-release.py \
  --artifact /caminho/linuxbr-VERSAO-amd64.iso \
  --artifact /caminho/linuxbr-VERSAO-fontes.tar.gz \
  --notes /caminho/notas-da-versao.md
```

O comando usa a versão do repositório, cria uma tag como `v1.0.0-rc2`, marca
Alpha/Beta/RC como pré-lançamento e cria primeiro um rascunho. Após todos os
uploads, `--publish` permite torná-lo público. Sem essa opção, revise o rascunho
na interface do GitHub e publique por lá. Falhas de upload deixam o lançamento
como rascunho, sem apresentá-lo como download concluído no site. Uma tag já
existente não é substituída pelo utilitário.

Versões estáveis exigem `--acceptance-report`, usando as regras de
`scripts/release_gate.py`; os artefatos enviados precisam corresponder aos hashes
do relatório. Isso não substitui as políticas do repositório APT.

## ISOs grandes e integridade

Cada arquivo do GitHub Releases precisa ficar abaixo de 2 GiB. O utilitário
divide artefatos grandes em partes de até 1900 MiB, sem modificar o original.
Publica `SHA256SUMS` para os arquivos enviados e `ORIGINAL-SHA256SUMS` para o
arquivo completo, acrescentando às notas os comandos para reunir as partes em
Linux e PowerShell. O usuário deve reunir a ISO antes de gravar o pendrive.

São necessários espaço temporário equivalente ao tamanho total dos artefatos,
mais 256 MiB de margem, conexão de upload e GitHub CLI. A compilação, a assinatura
APT e a instalação não são executadas por esse utilitário.

Referência: [GitHub — Releases e limites de arquivos](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## Site, loja e links especiais

- `/`: apresentação do sistema e versões públicas no GitHub.
- `/loja/`: descoberta de programas Linux, webapps e opções Windows/Wine.
- `/admin/`: administração autenticada de webapps, revisão e publicação do catálogo.
- `api.php` e a descoberta assinada mantêm seus endereços atuais.

O catálogo público de programas Linux e Windows é uma projeção curada do arquivo
`packages/linuxbr-system/files/usr/share/linuxbr/store/catalog.json`. Após alterar
esse arquivo, compile o painel com `npm run build` em `server/webapps/admin`;
a etapa `prebuild` regenera `server/webapps/public/applications.json`. Publique
esse arquivo junto com o site.
Os webapps continuam gerenciados pelo banco e painel PHP/MySQL/Angular.

Os links seguem `linuxbr-store://app/FONTE/APLICATIVO`. `builtin` identifica o
catálogo distribuído com o sistema; webapps usam a identidade assinada da fonte,
por exemplo `linuxbr-official`. O identificador local escolhido pelo usuário para
a fonte não interfere no link.

O protocolo seleciona a ficha do aplicativo e preserva as confirmações normais
da Loja. Não aceita comandos, caminhos, URLs de download ou fontes para confiar.
Fonte ausente, desabilitada ou aplicativo não encontrado levam à revisão das
fontes, sem adição automática. Identidades duplicadas exigem revisão. Catálogos
assinados continuam sujeitos às regras de validade antes de aplicar mudanças.
Não há instalação silenciosa por um site. Outros sistemas podem não reconhecer
o protocolo; a loja web mantém o link ao site oficial do aplicativo.

Para empacotar o cliente, inclua `store_links.py`, `store_frontend.py`,
`signed_catalog.py` e o `linuxbr-store.desktop` atualizado. O pacote registra o
MIME `x-scheme-handler/linuxbr-store`; não é necessário associá-lo ao Wine.
