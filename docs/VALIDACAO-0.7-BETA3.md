# Validação da 0.7 Beta 3

Imagem: `linuxbr-0.7.0~beta3-amd64.iso`, com 3.563.077.632 bytes.

SHA256: `3a165f96be0eb2613d46652350cb12b8c750c15fe4cbe640dcf143205be7e8c4`.

O build final terminou com código 0. A integridade da ISO e suas entradas de boot BIOS e UEFI foram verificadas. A presença dessas entradas não substitui a inicialização e a instalação reais.

Foram aprovadas **35 de 35 suítes de componentes**, incluindo 17 testes de recuperação. A execução utilizou a fonte final em uma área separada da VM de QA; o sistema instalado nessa rodada ainda era a Beta 2 e os componentes Qt foram executados fora da tela. Os seis hashes das correções de recuperação, menu e SMB conferem com o congelamento final.

A auditoria conferiu os **534 arquivos da fonte congelada**, os **540 arquivos do tar de fontes** — incluindo seis wrappers executáveis — e **363 arquivos de payload dos pacotes**. Os dois arquivos de identificação gerados durante o build foram comparados com o conteúdo esperado para a versão. O ZIP de atualização contém 12 DEBs, manifesto, script e instruções.

A simulação do atualizador na QA Beta 2 selecionou os oito componentes Linux BR com versão anterior, preservou os três pacotes Dolphin iguais e excluiu Calamares. Nenhum APT ou sudo foi invocado; inventário de pacotes e histórico APT permaneceram idênticos. Dez testes locais adicionais verificaram as guardas do atualizador.

O repositório **local HTTPS em PHP está ativo para a Beta 3**. Foram conferidos assinatura, índices, hashes dos 12 pacotes, identidades TLS e `apt update` com fonte local exclusiva. Esse ensaio não instalou pacotes. Os metadados têm validade de 14 dias e renovação manual; não há homologação de um serviço público na internet.

A correção SMB foi exercitada em laboratório isolado sobre uma instalação Beta 2, usando o conector atualizado e configuração pessoal privada. A autenticação nativa, o uso de carteira criptografada, a reconexão e a leitura/escrita pelo KIO foram verificados. A abertura pelo Explorador nesse perfil privado exibiu seletor de aplicativo e não foi concluída. Esses resultados não equivalem a homologação de um servidor Windows físico nem a desbloqueio da carteira após reiniciar.

## Integração da imagem final

| Etapa | Estado neste registro |
|---|---|
| Instalação limpa UEFI e primeiro login pelo disco | **PASS**: Calamares concluído, disco sem ISO, Wayland, 1280×768, oito pacotes Beta 3 e nenhuma unidade com falha |
| Instalação limpa BIOS e primeiro login pelo disco | **PASS**: Calamares concluído, MBR, GRUB legado, Wayland, 1280×768 e nenhuma unidade com falha |
| Atualização instalada, preservação e FULL rollback final | **PASS**: Live final restaurou o ponto 0.6, 1.807 arquivos pessoais conferidos sem alteração, login pelo disco e retorno à Beta 3 por HTTPS assinado |
| 7-Zip pelo Wine na instalação UEFI Beta 3 | **PASS**: criação e teste de arquivo com código 0, ícone principal lido pelo Qt e metadados preservados |

O ciclo completo de restauração usou a ISO final Beta 3, com uma única execução do Timeshift RSYNC. A base de pacotes e o marcador de controle corresponderam exatamente ao snapshot, incluindo a revisão de ícones da 0.6. A unidade criada para simular a falha foi removida.

O log preserva uma mensagem de falha ao remover diretório após concluir a restauração; o processo retornou 0, a verificação independente de ext4 somente de leitura retornou 0 e os dois logins pelo disco foram observados. A reinstalação do GRUB ficou fora do ensaio; o Timeshift regenerou seu menu.

Testes físicos em processadores Intel/AMD foram adiados por orientação do usuário. Wi-Fi, Bluetooth, áudio, periféricos, suspensão, Secure Boot, jogos Steam/Proton e contas web reais continuam sem homologação nesta rodada.

O [relatório detalhado da Beta 3](../../reports/0.7-beta3/RELATORIO.md) reúne os resultados, arquivos de evidência, limites dos ensaios e artefatos. A versão permanece Beta.
