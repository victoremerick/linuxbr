# Comandos Windows e arquivos BAT/CMD

Atualização para o Linux BR 0.6 Beta 1. Os pacotes incrementais usam a revisão `0.6.0~beta1+terminal1`.

## Terminal

No perfil Linux BR do Konsole, execute `comandos-windows` para consultar a ajuda. Abra uma nova janela de terminal após instalar a atualização.

| Comando | Comportamento disponível |
|---|---|
| `dir [/s] [/b] [/a] [pasta]` | Lista arquivos; recursão, uma entrada por linha e arquivos ocultos |
| `cls` | Limpa a tela |
| `copy [/y] origem destino` | Copia; pergunta antes de substituir, exceto com `/y` |
| `move [/y] origem destino` | Move; pergunta antes de substituir, exceto com `/y` |
| `del [/p] arquivo` | Pergunta antes de apagar cada arquivo |
| `rd pasta` | Remove uma pasta vazia |
| `md pasta` | Cria uma pasta |
| `type arquivo` | Exibe o conteúdo de um arquivo |
| `explorer [pasta]` | Abre a pasta no gerenciador de arquivos |
| `ipconfig` | Mostra interfaces e endereços de rede |
| `tasklist` | Mostra processos, usuários, CPU e memória |
| `where comando` | Localiza um executável no PATH |
| `cd /d "D:/Minha pasta"` | Entra na unidade e pasta escolhidas |
| `bat "C:/caminho/arquivo.bat"` | Abre a seleção do ambiente e a confirmação de execução |

Use aspas para espaços e barras normais nos caminhos:

```bash
copy /y "C:/home/maria/Documentos/arquivo.txt" "D:/Backup/arquivo.txt"
dir /s "D:/Backup"
bat "C:/home/maria/Downloads/configurar.bat"
```

O terminal continua usando a sintaxe Bash: `%VAR%`, `if` e `for` do CMD pertencem aos arquivos BAT/CMD, não à linha interativa do Bash. Barras invertidas sem aspas são interpretadas pelo Bash como escapes. As saídas e opções disponíveis são as descritas na tabela; não reproduzem integralmente os comandos do Windows. Opções desconhecidas falham, sem serem executadas como comandos de shell. Para usar o comando ou builtin original, use `command dir` ou `command type`.

Os comandos Linux continuam disponíveis. Esta atualização configura o perfil Bash do Linux BR; não instala nem configura PowerShell.

## BAT e CMD

O clique duplo abre o arquivo no Kate para leitura e edição. No menu de contexto do Dolphin estão disponíveis **Editar script Windows** e **Executar script Windows…**. Também é possível selecionar ou arrastar o arquivo para **Programas Windows e jogos**.

Para executar, escolha um ambiente existente ou crie um novo e confirme **Executar script**. Cancelar não inicia o Wine. O botão **Editar BAT / CMD** abre o editor sem executar o conteúdo.

A execução usa o CMD do Wine em uma janela de terminal com entrada pelo teclado. A janela permanece aberta ao terminar e informa o código de saída. O diretório inicial é a pasta do script, permitindo acessar arquivos relativos. O gerenciador também registra o código de saída do trabalho.

O `C:` do terminal Linux BR representa a raiz Linux conforme o gerenciador de unidades. O `C:` dentro do BAT/CMD representa o disco virtual do ambiente Wine. São espaços de caminhos distintos. Wine não é uma barreira de acesso aos arquivos da conta.

Variáveis, `if`, `for`, `call`, `goto`, `set /p`, redirecionamentos e códigos de saída foram verificados. Programas externos, serviços, drivers, Registro e recursos específicos do Windows continuam dependendo do suporte do Wine. Arquivos BAT/CMD com caminhos contendo `%`, aspas ou quebras de linha precisam ser renomeados antes da execução. Scripts com caracteres nulos não são aceitos por esta integração.

## Instalação dos pacotes incrementais

Na pasta dos dois pacotes `.deb`, confira `SHA256SUMS` e instale:

```bash
sha256sum -c SHA256SUMS
sudo apt install ./linuxbr-drive-manager_0.6.0~beta1+terminal1_amd64.deb ./linuxbr-system_0.6.0~beta1+terminal1_all.deb
```

Os pacotes foram instalados e validados na máquina virtual UEFI da versão 0.6. A ISO original da 0.6 Beta 1 permanece inalterada; novas compilações a partir dos fontes incluem os recursos.

Referências técnicas: [regras de escrita do Bash](https://www.gnu.org/software/bash/manual/html_node/Quoting.html) e [interpretação de arquivos em lote no Wine](https://www.winehq.org/pipermail/wine-devel/2018-September/132656.html).
