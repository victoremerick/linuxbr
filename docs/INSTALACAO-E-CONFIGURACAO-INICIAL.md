# Instalação e configuração inicial do Linux BR Desktop

O fluxo Desktop foi implementado em duas etapas obrigatórias em tela cheia. A primeira instala o sistema no disco. A segunda começa no primeiro boot e prepara o computador antes de liberar a área de trabalho. O empacotamento e as telas foram testados em laboratório. A [operação e os testes pendentes](CONFIGURACAO-INICIAL-OPERACAO.md) descrevem a homologação da mídia e dos ambientes corporativos.

O Windows 11 serve de referência para a transição entre a instalação e o primeiro uso, com uma ação principal por tela, navegação por teclado e indicação clara do progresso. [Instalação com Windows Setup](https://learn.microsoft.com/en-us/windows/iot/iot-enterprise/get-started/quickstart-pepare-lab-environment) · [Configuração inicial do Windows 11](https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/customize-oobe-in-windows-11)

## Instalação

O instalador ocupa toda a tela, sem bordas e sem a barra de título externa. A janela da instalação fica centralizada sobre esse fundo e concentra as etapas e os controles.

1. **Termos.** Exibir os termos em português e pedir o aceite antes de continuar.
2. **Disco.** Identificar os discos por modelo e capacidade. Apresentar as opções de particionamento disponíveis e resumir o que será formatado, apagado ou preservado antes da confirmação.
3. **Instalação.** Exibir progresso e falhas do Calamares. Após concluir, solicitar o reinício no sistema instalado.

Até a confirmação final, fechar a janela central cancela o fluxo e retorna ao ambiente Live. Ao confirmar **Instalar**, o assistente desativa o botão de fechar e bloqueia os pedidos de fechamento por atalhos ou pelo gerenciador de janelas, antes de iniciar qualquer alteração no disco. A tela mostra o progresso até a conclusão ou uma falha. Se houver falha, mostra o estado do disco e as ações de recuperação disponíveis.

## Configuração inicial

O sistema inicia o assistente automaticamente antes da primeira sessão de trabalho. A tela fica em modo de tela cheia até a conclusão, sem botão de fechar ou opção de pular o assistente. **Voltar** permite rever escolhas e **Reiniciar** permite recuperar a sessão quando necessário. Uma falha do assistente ou um reinício mantém a configuração pendente e faz o fluxo retornar ao primeiro passo incompleto.

| Tela | Comportamento esperado |
| --- | --- |
| Teclado | Sugerir Português (Brasil) ABNT2 e oferecer escolha de layout e um campo de teste. Aplicar a escolha imediatamente, inclusive aos campos de senha das telas seguintes. |
| Rede | Detectar Ethernet e oferecer seleção de Wi‑Fi. Distinguir rede conectada, internet disponível e acesso à rede corporativa. Permitir continuar sem internet. |
| Fuso horário | Com internet, tentar identificar o fuso e apresentá-lo para confirmação ou ajuste. Se a detecção falhar ou a internet estiver indisponível, pedir a escolha manual por região ou cidade. |
| Conta | Oferecer **Criar conta local** e **Entrar com conta da organização**. A conta local funciona offline. O fluxo corporativo oferece Active Directory e LDAP com TLS. Verifica a conexão e a identidade do servidor, orienta o ingresso no domínio quando necessário e confirma que a conta escolhida consegue entrar. Uma rede corporativa acessível pela LAN pode atender essa etapa mesmo sem internet pública. |
| Programas | Com internet e catálogo disponível, mostrar aplicativos por categoria a partir da Loja Linux BR, com fonte, seleção e progresso. Permitir continuar com a seleção vazia. Se a rede cair ou uma instalação opcional falhar, permitir tentar de novo ou concluir e abrir a Loja mais tarde. |
| Concluir | Mostrar as escolhas aplicadas e marcar a configuração como concluída após confirmar os requisitos essenciais. Abrir a sessão da conta escolhida pelo fluxo normal de autenticação. |

A detecção de fuso pela internet segue o padrão de sugerir a configuração ao usuário. No Brasil, o fluxo deve considerar os diferentes fusos regionais. [Referência de detecção de fuso na configuração inicial do Windows](https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/oobexml)

## Integração e critérios de aceite

- Reaproveitar o Calamares para a instalação, o NetworkManager para conexões, a integração realmd/SSSD para Active Directory, o fluxo de preparação corporativa para políticas e a Loja para instalar aplicativos. O suporte a LDAP independente deve ser validado separadamente do ingresso em Active Directory. [Contas e domínio](USUARIOS-E-DOMINIO.md) · [Preparação para trabalho ou escola](VERSAO-1.1.md)
- Gravar o progresso de forma persistente sem incluir senhas ou tokens. Ao retomar, validar o que já foi aplicado para evitar duplicar contas, vínculos e instalações. Restaurar o assistente se a sessão de configuração falhar.
- Validar instalação limpa em UEFI e BIOS com a janela centralizada e o fundo sem bordas preenchendo a tela. Conferir que o fechamento cancela antes da confirmação, que o botão e os atalhos deixam de fechar a janela ao confirmar **Instalar** e que o bloqueio já está ativo quando a primeira alteração no disco começa.
- Validar a retomada no passo pendente após reiniciar no meio do primeiro uso. Confirmar que a área de trabalho normal só fica disponível depois de concluir.
- Validar conta local totalmente offline, Ethernet, Wi‑Fi com senha incorreta, fuso sugerido e corrigido manualmente, Active Directory ou LDAP em rede interna, catálogo indisponível e retomada da fila após perda de conexão. Conferir navegação por teclado, foco e legibilidade a 1280 × 768.
