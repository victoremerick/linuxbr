# Programas Windows e jogos — Linux BR 0.4.2

Abra **Programas Windows e jogos** no menu ou na Central do Sistema. A imagem
inclui Wine 10, bibliotecas de 32 e 64 bits, o iniciador da Steam, Vulkan/Mesa
nas duas arquiteturas e regras de dispositivos para controles Steam.

## Programas EXE e MSI

1. Baixe o instalador do site do fornecedor.
2. Abra o EXE/MSI no Explorador ou escolha **Selecionar arquivo** na ferramenta.
3. Escolha um ambiente e clique em **Abrir / instalar**.
4. Siga o instalador. Depois procure o programa no menu do Linux BR. Se ele não
   criar atalho, selecione seu EXE em **Arquivos do ambiente → drive_c → Program Files**.

O ambiente padrão de 64 bits também executa programas Windows de 32 bits.
Use **Novo ambiente** para separar programas que exigem configurações diferentes.
Existe uma opção de ambiente de 32 bits para aplicativos antigos. Um executável
Windows x64 não pode ser iniciado nesse ambiente de 32 bits.

**Configurar Wine** abre as opções do ambiente selecionado. **Desinstalar
programas** abre seu desinstalador. O estado fica em
`~/.local/share/linuxbr/windows/` (ou no diretório definido em `XDG_DATA_HOME`).
Os registros da ferramenta ficam em `windows/jobs/` dentro desse diretório.

Wine não é uma máquina virtual nem uma barreira de segurança. O programa pode
acessar arquivos da conta. Use instaladores confiáveis, faça backup dos documentos
e nunca inicie Wine com sudo. A ferramenta recusa execução como root.

## Jogos Steam e Proton

Clique em **Abrir Steam**. Na primeira abertura, o iniciador Debian baixa o cliente
oficial. Entre em sua conta e instale jogos que você possui ou jogos gratuitos.
Para um título Windows, abra **Propriedades → Compatibilidade** na biblioteca e
selecione Proton quando necessário. A Steam gerencia o download de Proton e dos
componentes do jogo. A imagem não inclui jogos comerciais nem uma conta Steam.

A opção **Verificar Vulkan** mostra as GPUs e os drivers disponíveis. Jogos 3D
exigem hardware e drivers adequados; uma VM sem aceleração não comprova desempenho
em jogos. AMD/Intel usam as bibliotecas Mesa incluídas. A instalação de NVIDIA
pelo gerenciador de dispositivos inclui a biblioteca de 32 bits do mesmo ramo
quando i386 está habilitado; continuam valendo as verificações de hardware,
headers e Secure Boot do gerenciador.

## Bottles e dependências especiais

**Instalar / abrir Bottles** instala a edição Flatpak do Flathub somente para a
conta atual e depois abre o aplicativo. São necessários internet e espaço livre;
o download dos runtimes pode ocupar vários GB. Nada é baixado ao entrar na sessão.
O progresso e eventuais erros aparecem em uma janela de terminal.

No Bottles, crie um ambiente **Application** ou **Gaming**. Ele gerencia versões
do Wine/Proton, DXVK e dependências específicas. Instale componentes como Visual
C++ ou .NET apenas quando o aplicativo exigir, usando as opções do próprio Bottles.
Os ambientes do Bottles são separados dos ambientes Wine da ferramenta Linux BR.

Para programas com falhas ao minimizar ou maximizar, consulte o
[perfil de janelas individuais](OFFICE-E-JANELAS.md). Ele oferece um lançador
com X11/Xwayland da sessão sem trocar o modo gráfico de outros aplicativos.

## Limites e validação

Não há compatibilidade universal. Antitrapaça, DRM, drivers próprios, alguns
recursos de Microsoft Office/Adobe e programas profissionais podem exigir
Windows ou a versão web/Linux. A existência de um instalador que abre não prova
que todas as funções do programa funcionam. Avalie cada título e versão.

Testes automatizados cobrem assinatura/arquitetura dos arquivos, argumentos sem
shell, ambientes separados, recusa de root, MSI e encaminhamento do instalador.
Os testes reais usam executáveis x86/x64 compilados com MinGW e um MSI gerado
com WiX/msitools; não representam uma homologação de todos os programas.

Validação em 28/10/2026, na ISO 0.4.2 e em sua instalação UEFI:

| Verificação | Resultado |
| --- | --- |
| Compilação e verificação do sistema de arquivos | Aprovadas; Wine, Steam e bibliotecas i386 presentes |
| Instalação UEFI e início do sistema instalado | Aprovados, área de trabalho em 1280×768 |
| EXE Windows x86 e x64 | Ambos executaram APIs Windows e gravaram os arquivos esperados |
| MSI de teste | Instalou o arquivo esperado no ambiente Wine |
| 7-Zip Windows 26.05 x64 | Instalado pela interface; compactação, teste de integridade e extração aprovados, com comparação do conteúdo |
| SuperTux Windows 0.7.0 x64 | MSI instalado; interface, introdução e mapa em português; primeira fase abriu e respondeu ao teclado |
| Steam | Cliente baixado e atualizado; tela de login exibida |
| Bottles 67.5 | Instalado pelo auxiliar, por usuário; tela inicial exibida em português |
| BIOS, checagem final | ISO Live iniciou até a área de trabalho em 1280×768 |

Não foi usada uma conta Steam: execução de jogos via Proton não foi validada.
A instalação e a abertura do Bottles foram verificadas; a criação de ambientes
e seus runners não foram homologadas nesta rodada. A VM usa vídeo emulado,
sem passagem de GPU: estes resultados não medem desempenho 3D, compatibilidade
com antitrapaça nem o driver NVIDIA em hardware real.

Imagem no computador de desenvolvimento:
`/home/emericv/git/linuxbr/dist/linuxbr-0.4.2-amd64.iso`.

SHA-256: `8e4cb04dfa4683b34145dde5446b6062af184537da6f04e8212df365be92b69b`.

Referências oficiais:

- [Wine no Debian](https://wiki.debian.org/Wine)
- [Steam no Debian](https://wiki.debian.org/Steam/)
- [Steam e Proton](https://partner.steamgames.com/doc/steamhardware/proton)
- [Instalação do Bottles](https://usebottles.com/docs/getting-started/installation)
