# Fechamento da versão 0.6

A 0.6 Beta 2 consolida as funcionalidades da Beta 1 e a atualização de terminal e BAT/CMD em uma imagem única. A identificação Beta permanece enquanto a hospedagem das atualizações e a homologação em computadores físicos não forem concluídas.

## Funcionalidades consolidadas

- Desktop em português, menu e barra de tarefas, atalhos, notificações e gerenciador de tarefas independente. Ctrl+Alt+Del abre a tela de opções da sessão; o menu de contexto da barra oferece o gerenciador de tarefas.
- Gerenciador de arquivos com letras de unidade, integração a discos e compartilhamentos, lixeira e aplicativos padrão.
- Loja com catálogo Linux/Windows/web e inventário dos aplicativos registrados no desktop, incluindo exportações Flatpak. Componentes como Writer, Calc e Impress permanecem separados mesmo quando compartilham o executável.
- Wine com ambientes separados, instalação guiada, atalhos e desinstalação. BAT e CMD têm edição e execução separadas, confirmação, entrada pelo teclado e código de saída.
- Webapps com favicon, sessões persistentes e independentes, perfil preferido e seletor central para uma ou mais contas. Remover atalho e apagar dados são operações distintas.
- Terminal com caminho no próprio prompt, letras de unidade e comandos familiares documentados em TERMINAL-WINDOWS-BAT.md.
- Uso diário e configuração inicial com orientações para rede, NTFS, som, Bluetooth, impressoras, teclado e acessibilidade.
- Backup com ferramentas nativas, restauração de versões, atualizações pelo Discover e guia de recuperação pelo ambiente Live.

## Critérios de aceitação

| Área | Evidência necessária |
|---|---|
| Imagem | Build concluído, checksum, pacotes, versões e entradas UEFI/BIOS verificados |
| Instalação | Instalação UEFI limpa, reinício pelo disco, autenticação e teclado brasileiro |
| Atualização | Pacotes finais instalados sobre a versão anterior, com perfis e preferências preservados após reiniciar |
| Aplicativos | Arquivos comuns, programas Windows e webapps exercitados em ambiente de teste |
| Desktop | Atalhos e ações de sessão verificados sem executar saídas ou exclusões não solicitadas |
| Recuperação | Backup e restauração verificados com arquivos de teste, sem tratar cópia de arquivos como imagem completa do sistema |
| Repositório | Assinatura APT aceita e adulteração rejeitada; publicação HTTPS e entrega confiável da chave concluídas antes de ativar clientes |
| Hardware | Instalação, vídeo, rede, áudio, periféricos, suspensão e retomada em equipamentos físicos identificados |

## Dependências para encerrar a condição Beta

É necessário definir o servidor ou domínio HTTPS para publicar o repositório. Nenhum endereço fictício deve ser ativado nos clientes, e nenhuma chave privada deve entrar na ISO ou no pacote público de evidências.

Também é necessário disponibilizar computadores físicos e periféricos para homologação. A capacidade da máquina virtual não comprova aceleração gráfica, compatibilidade de impressoras, Bluetooth, autonomia ou suspensão em um notebook real.

Steam e Proton oferecem o caminho de instalação e configuração para jogos compatíveis. O resultado de cada jogo depende de sua versão, driver, requisitos e sistemas antitrapaça. A documentação do fornecedor descreve requisitos de habilitação por título: [Steam e Proton](https://partner.steamgames.com/doc/steamhardware/proton).

Os resultados executados e as pendências ficam no relatório específico da imagem. Uma funcionalidade implementada não deve ser apresentada como testada em hardware quando foi verificada apenas em máquina virtual.
