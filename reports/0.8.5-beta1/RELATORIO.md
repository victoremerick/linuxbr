# Linux BR 0.8.5 Beta 1 — implementação e validação

Versão dos componentes: `0.8.5~beta1`. Base Debian 13, Plasma 6 e Calamares. Data: 4 de novembro de 2026.

## Funcionalidades entregues

- **Loja Linux BR:** navegação por categorias, cartões, detalhes, biblioteca, favoritos, downloads e histórico; fontes APT e Flatpak, importação de chaves, aplicativos Linux, catálogos Windows e webapps. Instalação de DEB local com conferência de integridade. Atalhos do Discover encaminhados à Loja, preservando os serviços nativos.
- **Configurações:** 12 categorias e 106 destinos, pesquisa por termos familiares, navegação e detecção de disponibilidade. Inclui área de transferência, permissões de aplicativos isolados, serviços, eventos, variáveis de ambiente e agendamento. Alterações administrativas usam autorização nativa.
- **Máquinas virtuais:** criação rápida e assistente gráfico completo; editor após a criação, recursos, CPU, inicialização, discos, mídias e múltiplos adaptadores. Redes NAT, internas, privadas e pontes existentes; armazenamento, console, estados salvos, checkpoints, cópias completas, importação e clonagem com hashes.
- **Windows em VM:** UEFI, Secure Boot e TPM 2.0. Modelo local com autoridades Microsoft de 2023; atualização de variáveis de VMs existentes com checkpoint, preservando PK e revogações. Assistente e editor completos integrados ao virt-manager.
- **Continuidade da 0.8:** propriedades nativas com Aplicar, segurança, validação, compatibilidade, versões anteriores e compartilhamento; perfis Chromium isolados e favicons; Wine/BAT, ferramentas de migração e manutenção permanecem integrados.

O histórico por versão está no README das fontes. A [matriz de Configurações](MATRIZ-CONFIGURACOES.md) distingue abertura de páginas, disponibilidade de módulos e recursos dependentes de hardware.

## Compilação e integridade

A ISO final contém os 18 DEBs conferidos. Foram comparados 1.410 arquivos regulares em `usr/` entre pacotes, raiz de compilação e o SquashFS extraído da própria ISO; 378 arquivos de conteúdo também conferem com as fontes congeladas. Foram conferidas 623 entradas usadas na compilação e as entradas de inicialização UEFI e BIOS.

- ISO: `linuxbr-0.8.5~beta1-amd64.iso`, 3.637.100.544 bytes.
- SHA-256 da ISO: `c952c0b6db28c5df2a618eb157b2e2524a6c9cd5c46b3692a64d3add488f0d2e`.
- SHA-256 do arquivo público de fontes: `e122e0c8007eed44e28db52b076efa7680115040d4eca744a6325c3cd211ed5d`.

O arquivo público de fontes exclui uma nota interna antiga sem conteúdo empacotado. A equivalência é conferida para as entradas da compilação e os arquivos distribuídos; não representa uma promessa de recompilação binariamente idêntica de todos os pacotes de terceiros.

## Resultados já concluídos

| Cenário | Resultado e alcance |
| --- | --- |
| Regressão das fontes finais | 53 suítes aprovadas; fontes preservadas durante a execução. |
| Novos componentes | 23 testes aprovados em contexto administrativo. |
| Webapps | Três suítes aprovadas. |
| Interface de VMs | Assistente completo, seleção gráfica de ISO, criação rápida e editor completo abertos em português; cancelamento sem criar VMs indevidas. |
| Concorrência no editor | Tentativa de operação simultânea não deixa o editor desabilitado. |
| Atualização 0.8 → 0.8.5 | Restauração de uma cópia descartável ao ponto 0.8; instalação dos 17 pacotes de execução da ISO final, sem remover pacotes; reinício aprovado. |
| Integridade após atualizar | 1.390 arquivos de execução conferidos com a ISO; 1.789 arquivos pessoais e de perfis preservados. |
| VM principal de validação | Pacotes finais reinstalados, hashes conferidos, reinício e preservação dos 1.789 arquivos conferidos. |
| Instalação limpa UEFI | Calamares, conferência offline somente leitura, inicialização pelo disco e primeiro login aprovados em 1280×768. Loja, Configurações e gerenciador de VMs abertos; conexão KVM autorizada pelo diálogo nativo. |
| Instalação limpa BIOS | Calamares com MBR, conferência offline somente leitura, inicialização pelo disco e primeiro login aprovados em 1280×768. |
| Propriedades na instalação nova | SHA-256 calculado e comparado; Aplicar renomeou o arquivo, com persistência confirmada ao reabrir. |
| Checkpoint com memória BIOS | Criado em VM nova sem TPM; restauração pausada e retomada da execução aprovadas. VM vazia de laboratório, sem avaliação de carga de aplicativos. |
| Repositório PHP/HTTPS | Publicação final ativa; assinatura, índices, 18 DEBs e 32 arquivos públicos conferidos. APT isolado reconheceu 18 candidatos; publicação anterior e confiança dos clientes preservadas. 19 testes do publicador aprovados. |

Os registros finais ficam em `validacao-final7/`, `atualizacao-final7/`, `instalacao-final7/` e `repositorio-final7/`. Pastas com `diagnostico` identificam imagens anteriores e não substituem o resultado final.

O ZIP de atualização foi extraído novamente e teve seus hashes conferidos; o verificador também aprovou os 18 DEBs no Linux BR já atualizado. O instalador Calamares não é selecionado para atualização do sistema instalado. Os 55 arquivos integrados ao projeto remoto conferem com as fontes finais.

## Operações verificadas em laboratório

Uma comparação de hashes entre a revisão intermediária e a final confirmou 96 módulos de execução Python idênticos; três módulos de interface tiveram revisões posteriores e foram novamente verificados. Os testes funcionais anteriores devem ser lidos com essa procedência, enquanto as suítes, a atualização e as instalações finais se referem à ISO entregue.

Os registros específicos acompanham este relatório: fontes APT e chave pública, instalação local com recusa de hash alterado, fonte Flatpak isolada e permissões, tarefas de usuário/sistema, variáveis de ambiente, criação e edição de VMs, estados salvos, checkpoints combinados com firmware/TPM, exportação/importação e clonagem, recusa de arquivos adulterados e de discos graváveis compartilhados. Uma rede NAT foi conferida com DHCP, DNS e HTTPS, mantendo o firewall ativo.

Um Windows 11 Enterprise Evaluation 26H2 iniciou dentro do Linux BR; Secure Boot ativo e TPM 2.0 pronto foram observados nas ferramentas do convidado. O disco de referência permaneceu somente leitura, com gravação em uma cópia descartável. Após as capturas, essa cópia esgotou o espaço do laboratório e foi pausada por erro de I/O; o encerramento limpo do Windows não foi aprovado. O registro não comprova execução de Hyper-V dentro desse convidado.

## Limites

A edição permanece Beta. Homologação física de Intel/AMD, aceleração gráfica, Wi-Fi, Bluetooth, áudio, periféricos e suspensão foi adiada. A presença de um controle nas Configurações não comprova o funcionamento de cada equipamento.

Detalhe visual conhecido nas propriedades: depois de renomear pelo botão Aplicar, o campo de caminho no formato Windows e o título podem conservar o nome anterior até a janela ser reaberta. O arquivo é renomeado e o caminho real é atualizado corretamente.

Migração remota usa a API nativa do libvirt, mas não foi homologada entre dois hospedeiros. Não há replicação contínua, cluster nem failover automático. Checkpoints com memória são limitados a BIOS sem TPM; UEFI/TPM usam checkpoint desligado ou estado salvo.

Compatibilidade Wine/Proton depende de cada programa ou jogo. Uma VM Windows exige mídia e licença próprias. A integração da Loja com fontes externas depende da disponibilidade e confiança dessas fontes. O servidor PHP usa confiança local, publicação assinada e metadados com validade de 14 dias; a renovação é manual.
