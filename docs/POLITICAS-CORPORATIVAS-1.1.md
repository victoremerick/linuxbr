# Linux BR 1.1 — Políticas da organização

**Estado da Alpha 1.** O painel distribui perfis assinados por dispositivo. A preparação aplica pastas da conta e apresenta sugestões na Loja. Os controles obrigatórios `store-snap` e `store-brew` passam por revisão administrativa, preservam os valores anteriores e podem ser revertidos. Uma regra obrigatória fora desse catálogo mantém o preparo pendente. Atribuição por grupos de domínio, certificados, VPN, bloqueio por inatividade e firewall continuam no escopo de evolução descrito abaixo.

A equipe de TI deve conseguir definir regras uma vez e aplicá-las às máquinas e contas da organização. O Linux BR consulta um serviço instalado na infraestrutura da empresa ou escola, aplica as políticas atribuídas e informa se o estado do computador corresponde à revisão publicada. O serviço deve funcionar na rede interna ou por VPN, com identidade, políticas e registros sob controle da organização.

## Serviço de políticas na organização

- Fornecer um pacote de instalação para servidor Linux, com API HTTPS, armazenamento de revisões e painel web em português. Documentar instalação, atualização, backup e restauração, incluindo a recuperação segura das chaves de assinatura.
- Reaproveitar a integração com Active Directory para o primeiro recorte. A TI cadastra dispositivos e grupos de dispositivos no painel e atribui políticas a usuários e grupos do diretório. O servidor valida essas identidades e os vínculos ao montar a política efetiva. O cliente não escolhe livremente a identidade nem os grupos que receberão regras.
- Permitir criar políticas em rascunho, simular a regra efetiva para uma máquina e uma conta, publicar para um grupo piloto e ampliar a atribuição depois da conferência. Registrar autor, data, revisão e alterações. Restaurar uma configuração anterior por meio de uma nova revisão assinada.
- Separar permissões de editar, publicar e consultar auditoria. Exibir por dispositivo a revisão atribuída, a revisão aplicada, o horário do último contato e as pendências. Sinalizar máquinas sem contato para que um resultado antigo não seja confundido com conformidade atual.

## Regras e precedência

| Escopo | Controles propostos para a 1.1 |
| --- | --- |
| Dispositivo | Tempo máximo de inatividade antes do bloqueio, configuração suportada do firewall, fontes de aplicativos aprovadas e configuração de certificados de confiança. |
| Conta | Atalhos e pastas de trabalho, aplicativos e webapps atribuídos e preferências iniciais do ambiente. |

Cada regra declara seu escopo e se é obrigatória ou uma preferência. A preferência fornece um valor inicial que a pessoa pode ajustar. O controle obrigatório é aplicado pelo componente responsável e aparece na interface como **Gerenciado pela organização**, com a origem e a revisão da regra.

As regras específicas têm prioridade sobre os padrões da organização dentro do mesmo escopo. Quando duas atribuições específicas disputam o mesmo ajuste, vale a prioridade explícita configurada pela TI. Empates incompatíveis impedem a publicação até que a TI resolva o conflito. Regras por conta respeitam as restrições obrigatórias da máquina. O painel e o cliente mostram a origem da regra efetiva para facilitar o diagnóstico.

## Cliente Linux BR

1. Em **Preparar para trabalho ou escola**, a TI autoriza o vínculo e estabelece a confiança no servidor por meio do perfil de cadastro assinado. O cliente autentica o dispositivo nas consultas e associa as regras por conta à sessão autenticada.
2. O serviço local consulta as políticas no preparo inicial, no login corporativo, em intervalos configurados pela TI e por **Sincronizar agora**. Valida o servidor, a assinatura, o destinatário, a validade e a revisão do documento antes de aplicar qualquer mudança. Uma revisão antiga recebida fora de ordem não substitui uma mais recente.
3. Aplicar apenas operações previstas no catálogo de controles do Linux BR, com validação de parâmetros e privilégios separados entre máquina e sessão. Confirmar o resultado de cada controle antes de informar conformidade. Uma falha mantém a etapa pendente e permite nova tentativa sem duplicar mudanças já aplicadas.
4. Durante uma interrupção, conservar os controles obrigatórios já aplicados e indicar a última revisão e a falta de sincronização. Se o documento em cache vencer, sinalizar a pendência e exigir uma atualização válida para concluir um preparo novo. A indisponibilidade do serviço de políticas preserva o acesso de recuperação pela conta administrativa local.
5. Ao retirar uma regra ou desvincular o computador com autorização administrativa, remover ou restaurar somente as configurações que o serviço passou a gerenciar. Preservar contas e arquivos pessoais e registrar o resultado. Excluir senhas, tokens e chaves privadas dos diagnósticos e da auditoria.

O serviço entrega regras declarativas do Linux BR. Importação de GPOs do Windows e execução de scripts enviados pelo servidor ficam fora do escopo inicial. A integração com a tela de preparo segue a [jornada de trabalho ou escola](VERSAO-1.1.md).

## Critérios de aceite

1. Instalar o servidor em uma rede de laboratório isolada e distribuir uma política assinada a dois grupos, verificando regras diferentes para dois dispositivos e duas contas, inclusive em um computador compartilhado.
2. Publicar para um grupo piloto, conferir o resultado no painel e ampliar a atribuição. Resolver um conflito antes da publicação e restaurar uma configuração anterior com nova revisão e histórico preservado.
3. Comprovar que uma regra obrigatória prevalece nos pontos de configuração suportados e que uma preferência pode ser alterada pela pessoa. Confirmar o estado efetivo no cliente e no painel.
4. Simular indisponibilidade, documento expirado, pacote adulterado, revisão antiga e destinatário incorreto. Conferir a continuidade dos controles já aplicados, a atualização após o retorno da rede e a indicação de máquinas com estado desatualizado.
5. Testar falha durante a aplicação, nova tentativa e desvinculação. Conferir que a auditoria explica a pendência, que os arquivos pessoais permanecem acessíveis pela conta autorizada e que a recuperação local continua disponível.
