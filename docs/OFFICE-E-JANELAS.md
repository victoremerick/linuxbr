# Office e integração de janelas

Revisão de código posterior à ISO 1.0 RC 2, em 06/11/2026.

O Microsoft 365 para Windows continua experimental. A conta reconhecida na tela
inicial não comprova ativação, edição ou gravação de documentos.

## Perfil de janela individual

O comando `linuxbr-bottles-window` abre um programa registrado no Bottles através
do Flatpak com X11/Xwayland da sessão. Cada janela fica sob controle do KWin.
O perfil gráfico vale para essa execução; não troca a sessão Plasma nem cria
uma permissão global do Flatpak. Não execute com sudo.

Feche os programas do ambiente antes de preparar o perfil. A preparação usa a
interface oficial do Bottles para desativar a área de trabalho virtual somente
no ambiente escolhido. Não encerra processos nem apaga o ambiente.

```sh
linuxbr-bottles-window --bottle "Meu ambiente" --prepare
linuxbr-bottles-window --bottle "Meu ambiente" --program "Meu programa"
```

A edição padrão é `com.usebottles.bottles`, instalada pelo Flathub. A opção
`--app-id com.usebottles.bottles.Devel` atende ambientes de desenvolvimento
instalados separadamente. O lançador não baixa versões experimentais nem migra
ambientes automaticamente. A edição estável não foi homologada com Microsoft 365.

## Resultado no computador de referência

O ambiente anterior utilizava um servidor X11 aninhado e suas superfícies não
eram janelas independentes do KWin. A alternativa nativa Wayland do runner Soda
testado permitiu maximizar/restaurar, mas minimizar deixou uma janela de 160×31
sem marcar o estado minimizado. Esse caminho não foi aprovado.

Foi preservado o ambiente anterior e feita uma cópia com reflinks para o Flatpak.
O perfil X11/Xwayland do lançador passou nos quatro controles do Word:

| Ação pelos controles do Word | Estado observado no KWin |
| --- | --- |
| Restaurar | Janela individual de 1200×640 |
| Maximizar | 1600×854, respeitando a barra de tarefas |
| Minimizar | `minimized=true` na janela correspondente |
| Abrir pela barra de tarefas | `minimized=false`, janela visível novamente |

Os sete atalhos locais do Office usam o perfil novo, mantendo ícones próprios.
O retorno `ms-appx-web` aponta para a mesma edição do Bottles. Outros aplicativos
e associações de documentos não foram alterados. Os controles dos demais
aplicativos do Office ainda precisam de ensaio individual.

Ambiente ensaiado: Linux BR 1.0 RC 2, Plasma Wayland, Intel/Mesa, Bottles 67.6
Development, Soda 11.0-36 experimental e DXVK 3.1.1. O runtime inclui os componentes
Compat.i386 e GL32 da série 25.08. Não substituir esse registro por uma promessa
de compatibilidade universal nem exigir esse perfil para jogos sem avaliação.

Build oficial do Bottles: [execução 42114942449](https://github.com/bottlesdevs/Bottles/actions/runs/42114942449),
artefato 13455439929. SHA-256 do ZIP conferido antes da instalação:
`295eea1a46964a065edcc59b50b624b692891051bd0ced01b6154becbfe1e69f`.

As evidências sem títulos de documentos ou credenciais estão em
[office-window-controls-2026-11-06.json](validations/office-window-controls-2026-11-06.json).
Não foi construída uma nova ISO nesta revisão. Edição, gravação, ativação e
demais recursos do Office permanecem fora da aprovação destes testes gráficos.
