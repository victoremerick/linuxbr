# Migração e cuidados com o computador — 0.8

## Trazer meus arquivos

Abra **Trazer meus arquivos do Windows** pelo menu ou por **Central do Sistema → Arquivos e atalhos**. Selecione pastas de um disco, pendrive ou cópia de segurança e uma pasta de destino existente. A ferramenta copia arquivos; não importa contas, senhas, Registro do Windows nem programas instalados.

**Conferir importação** lê as origens, prevê espaço e conflitos e registra hashes estáveis. **Copiar e verificar** confere os dados escritos antes de concluir cada arquivo. Links simbólicos e arquivos especiais são relacionados como ignorados; erros de acesso produzem um resultado parcial. Feche os programas que alteram as pastas selecionadas.

Para nomes existentes, é possível manter ambos, ignorar o arquivo da origem ou substituir o destino. A substituição mantém a versão anterior em um arquivo oculto `.linuxbr-anterior-*`, com o caminho no relatório. Arquivos concluídos antes de um cancelamento permanecem no destino. A origem é preservada.

Um relatório JSON com horários, resultados, erros e SHA-256 é salvo no destino, acessível apenas à conta que o criou. Mudanças concorrentes, links introduzidos no caminho ou um novo arquivo que ocupa o nome esperado interrompem aquela cópia. Versões capturadas que não puderem voltar ao nome anterior são preservadas e identificadas no relatório.

Não há conversão automática de permissões NTFS em ACL POSIX. As cópias novas usam acesso privado da conta; o compartilhamento é uma ação posterior, explícita, nas propriedades. O destino deve oferecer as operações de arquivo utilizadas pelo sistema; falhas de capacidade ou leitura aparecem no resultado.

## Proteção e atualização

Em **Cuidados com o computador → Proteção e atualização**, confira os planos pessoais do Kup: habilitação, tipo, última conclusão registrada, disponibilidade do disco e espaço livre. O histórico pessoal é separado dos pontos de restauração do sistema pelo Timeshift.

A verificação antes de abrir atualizações consulta espaço da raiz, estado do gerenciador de pacotes, alimentação e condições conhecidas de backup. Um registro de sucesso informa o resultado daquela ferramenta; testar uma restauração continua sendo uma etapa própria.

Os índices locais exibem sua validade quando disponível. A consulta explícita ao certificado do servidor verifica o nome e a confiança TLS com a autoridade configurada para o repositório local. A manutenção do servidor é descrita em [repositório](REPOSITORIO-MANUTENCAO-0.8.md).

## Resolver um problema

Os fluxos de áudio, programa que não abre, impressora e pasta de rede consultam o estado disponível e oferecem ferramentas nativas relacionadas. O diagnóstico não instala drivers, altera conexões ou reinicia serviços por conta própria. Equipamentos ausentes e mecanismos indisponíveis aparecem como limitações da consulta.

## Armazenamento e limpeza

Escolha cache antigo ou lixeira, feche os aplicativos e use **Conferir**. A limpeza exige confirmação e revalida os itens antes de removê-los; alterações detectadas são preservadas. Cache recente, configurações, documentos, perfis web, ambientes Wine e backups ficam fora da limpeza genérica.

A prévia lê os arquivos elegíveis para conferir sua integridade e pode ser cancelada. Durante a limpeza, os dados de restauração de um item da lixeira são mantidos se o conteúdo não foi removido. Itens que precisarem ficar preservados sob outro nome são relacionados no resultado.

Arquivos em uso ainda podem mudar durante a operação. Por isso, fechar os aplicativos faz parte do fluxo. A ferramenta não promete recuperar itens definitivamente removidos nem substituir um backup.
