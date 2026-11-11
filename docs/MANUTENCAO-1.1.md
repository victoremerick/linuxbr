# Linux BR 1.1 — Atualização, suporte e recuperação

## Estado da implementação

O [servidor de ondas](../server/update-waves/README.md) funciona na rede da organização e usa o repositório APT assinado existente. O gancho consulta o serviço por HTTPS e confere o documento OpenPGP, o dispositivo, a onda, a validade e o conjunto exato de SHA-256 dos DEBs. A pausa afeta novas autorizações. Um computador comum segue o fluxo local do APT. O manifesto local é útil para ensaios e tem validade própria.

O APT exige um ponto Timeshift antes de aplicar o lote gerenciado. Em **Backup e recuperação → Atualizações**, o administrador pode conferir os pacotes e registrar o resultado após revisar o funcionamento e o estado de reinício. A promoção exige a confirmação do piloto. A revisão restaurada fica suspensa na máquina. O assistente **Recuperar atualização** usa o Live e admite raiz ext4 com backup Timeshift RSYNC em outra partição ext4, no mesmo modo UEFI ou BIOS da instalação.

O diagnóstico oferece prévia por categoria, exportação JSON e resposta a solicitações da TI. O envio e a recusa são decisões separadas. A recusa registra apenas a identificação do pedido. Os campos gráficos incluem estado dos serviços e contagens de avisos recentes.

O inventário periódico é habilitado pela TI após cadastrar o dispositivo. O painel permite definir uma janela opcional para novas autorizações da revisão. Fora do intervalo, o cliente aguarda a janela. O agendamento de reinício, os controles fora do APT e o aceite de layouts adicionais de recuperação seguem nos critérios abaixo.

## Ordem de entrega

1. **Prioridade 1:** atualizações em ondas, diagnóstico para suporte e recuperação. Entregar o ciclo completo em conjunto, do piloto até a recuperação de uma máquina afetada.
2. **Prioridade 2:** inventário básico integrado ao painel da organização e migração guiada do Windows. O painel da prioridade 1 já precisa dos estados de atualização e do último contato. O inventário amplia essa visão.

## Atualizações em ondas

- Reaproveitar o painel instalado na organização e o repositório APT assinado. A TI associa uma revisão fechada de pacotes e dependências aos grupos **Piloto** e **Geral**. As duas ondas recebem a mesma revisão verificada. Alterar pacotes ou dependências exige uma nova revisão e uma nova passagem pelo piloto.
- Exigir aprovação explícita para promover ao grupo geral, com resultados e falhas do piloto visíveis. A TI pode pausar novas instalações, retomar ou retirar a revisão. Uma instalação já em andamento deve concluir ou seguir o fluxo de recuperação do gerenciador de pacotes. Retirar a revisão não dispara restauração automática.
- Aplicar a atribuição nas atualizações gerenciadas pela Loja e pelo serviço de atualização. Verificar autorização, assinatura, versões e dependências antes de instalar. Uma máquina que perdeu contato aguarda autorização atual para iniciar uma atualização gerenciada e consulta a onda vigente quando voltar à rede.
- Verificar espaço, estado do APT e disponibilidade do ponto de recuperação exigido antes de uma atualização protegida. Mostrar janela de manutenção, necessidade de reinício e opção de adiar dentro do prazo da organização. Agendar um reinício exige aviso local e registro no painel.
- Registrar revisão, onda, horário e estados **Aguardando**, **Instalando**, **Reinício pendente**, **Concluída**, **Falhou** e **Restaurada**. Exibir separadamente o último contato e o estado conhecido, com autoria das promoções e pausas.

**Aceite:** publicar uma revisão assinada para o piloto, provocar uma falha controlada, pausar a distribuição e confirmar que o grupo geral continua na versão anterior. Depois, aprovar uma revisão validada, verificar o mesmo conjunto de pacotes nas duas ondas e conferir a retomada de um cliente desconectado.

## Diagnóstico para suporte

- Em **Ajuda → Gerar diagnóstico**, coletar versão e kernel, espaço livre, estado de rede, falhas recentes de serviços selecionados, transação de atualização, reinício pendente, pontos de recuperação e revisão das políticas. Indicar quando uma consulta não pôde ser realizada. Para problemas gráficos, oferecer uma categoria com estado do portal de captura e registros selecionados do KWin.
- Mostrar prévia por categoria e permitir retirar itens antes de exportar. Usar uma lista explícita de campos, limite de tempo e tamanho e saneamento de registros. Excluir senhas, tokens, chaves, conteúdo pessoal e detalhes de identificação desnecessários. Gerar um resumo legível e dados estruturados com versão de formato.
- Permitir exportação local sem rede. Em máquinas gerenciadas, a TI pode solicitar o relatório pelo painel. O envio usa o serviço da organização após revisão e consentimento local. Limitar acesso e retenção, registrar solicitação, envio e descarte e permitir recusa sem bloquear a sessão.

**Aceite:** reproduzir uma falha de atualização e confirmar que o relatório identifica a transação e a etapa com erro. Inserir segredos fictícios e conferir que ficam fora da prévia e do arquivo. Validar exportação sem rede e recusa de envio sem transferência de dados.

## Recuperação após uma atualização com problema

- Reaproveitar o mecanismo de pontos de recuperação existente. Associar cada transação protegida ao ponto criado antes da instalação, com data, pacotes afetados e indicação do último estado funcional confirmado. Se o ponto obrigatório falhar, impedir o início da transação e explicar como corrigir a proteção.
- Oferecer **Recuperar atualização** na Central e no ambiente de manutenção acessível pela inicialização avançada. Mostrar o que será restaurado, qual disco e instalação serão afetados, os dados excluídos da restauração e a necessidade de reiniciar. Exigir confirmação administrativa e conferir a integridade e compatibilidade do ponto.
- Permitir restaurar o sistema sem rede a partir de um ponto acessível no ambiente de manutenção. Preservar os diretórios pessoais e manter a atualização problemática suspensa no dispositivo até revisão autorizada. Após o reinício, conferir a versão restaurada e os serviços essenciais. Se a restauração falhar, manter o diagnóstico disponível e indicar os próximos passos.

**Aceite:** em máquina virtual, instalar uma atualização de teste que impeça a sessão gráfica, entrar na manutenção, recuperar sem rede, validar o retorno da sessão e comparar o conteúdo dos arquivos pessoais antes e depois. Conferir que a revisão problemática não é reaplicada na sincronização seguinte.

## Inventário básico de máquinas

Exibir no painel somente o necessário para manutenção nesta etapa: dispositivo cadastrado, versão do sistema, espaço livre, onda, revisão aplicada, reinício pendente e último contato. Identificar dados desatualizados, filtrar por onda e estado e limitar consulta e exportação ao papel autorizado. Registrar horários e unidades para evitar confundir dados de máquinas diferentes.

**Aceite:** cadastrar dois dispositivos, interromper a comunicação de um e conferir que o painel sinaliza dados antigos sem perder o último estado conhecido. Um operador sem permissão deve receber recusa ao consultar ou exportar o inventário.

## Migração guiada do Windows

Ampliar **Trazer meus arquivos** na preparação inicial. Permitir escolher a origem, selecionar pastas pessoais e importar favoritos de formatos suportados. Mostrar espaço necessário e conflitos de nomes antes de copiar. Preservar a origem, pedir decisão antes de substituir arquivos, conferir a cópia e permitir retomada sem duplicatas. A partir da lista de programas indicada pela pessoa, sugerir alternativas disponíveis na Loja, com confirmação antes de instalar.

**Aceite:** migrar uma amostra com nomes acentuados, arquivos grandes e conflitos, interromper e retomar a cópia e conferir a integridade na origem e no destino. Validar a importação de favoritos e a abertura da ficha de um aplicativo sugerido.

Bases do projeto: [repositório de atualizações](REPOSITORIO-ATUALIZACOES.md), [recuperação](RECUPERACAO-0.7.md), [migração e manutenção](MIGRACAO-MANUTENCAO-0.8.md) e [políticas da organização](POLITICAS-CORPORATIVAS-1.1.md).
