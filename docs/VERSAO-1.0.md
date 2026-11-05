# Linux BR 1.0 — desenvolvimento e critérios de lançamento

Estado: desenvolvimento da candidata RC 2, a partir da 0.9 Beta 1. Esta identificação não representa aprovação de uma versão estável. A RC 1 forneceu os primeiros ensaios de instalação, atualização, restauração e recuperação; uma correção de detecção de perfis Chromium motiva a nova candidata e a repetição dos ensaios com seus artefatos exatos.

Guias: [instalação e primeiros passos](INSTALACAO-1.0.md) e [suporte e homologação](SUPORTE-1.0.md).

## Entregas

1. Configuração inicial com migração, rede, idioma, teclado, tela, dispositivos, backup, atualizações e aplicativos. Separar o que foi conferido automaticamente das marcações pessoais.
2. Interface consistente nas edições Desktop e Servidor: ícones por função, teclado, foco, português, escalas e mensagens que permitam recuperar operações.
3. Loja Linux BR como ponto de entrada para aplicativos, fontes, biblioteca, fila, histórico, atualizações e revisões de webapps. Falhas de consulta precisam ficar visíveis e permitir nova tentativa.
4. Compatibilidade documentada por programa, versão, ambiente, data, sistema testado e limitações. Uma prova antiga não aprova uma nova distribuição. Não atribuir aprovação genérica a jogos Steam/Proton.
5. Webapps com favicon, sessões persistentes e perfis independentes; atualização de metadados preserva os dados locais e exige revisão para mudança de domínio.
6. Administração gráfica de serviços, tarefas, inicialização, ambiente, compartilhamentos e máquinas virtuais, com autenticação e operações reversíveis.
7. Atualização assinada, proteção anterior à transação, recuperação e manutenção automática, com separação explícita entre candidata e estável.
8. Guia de instalação, matriz de equipamentos, requisitos medidos, limitações e política de manutenção.

## Validação obrigatória

Cada resultado precisa identificar a versão e o SHA256 da mídia ou dos pacotes efetivamente usados. O relatório de liberação verifica os artefatos e as evidências; ausência de resultado é pendência.

- Compilação e estrutura dos pacotes; comparação de arquivos instalados com os pacotes finais.
- Inicialização Live UEFI e BIOS da ISO exata de lançamento.
- Instalação limpa Desktop UEFI e BIOS e Servidor UEFI pela ISO exata, com primeiro login, kernel, edição, rede e auditoria de pacotes.
- Atualização natural da 0.9, sem reinstalação forçada, com criação de snapshot, reinício e conferência dos arquivos pessoais.
- Restauração do snapshot e nova atualização, preservando os dados pessoais.
- Recuperação, segurança, segurança com rede, terminal, vídeo básico, diagnóstico, Shift + Reiniciar e retorno à inicialização normal.
- Fluxos de Loja, webapps, perfis, serviços, agendador, variáveis, rede e virtualização; resultados por cenário, sem inferir aprovação de simples abertura de janela.
- Autenticação administrativa, validação de assinaturas, rejeição de conteúdo alterado e proteção dos dados locais.
- Ensaios de teclado, foco, navegação e escalas em resoluções suportadas.
- Homologação física nos equipamentos declarados como suportados. O usuário adiou ensaios com processadores diferentes; não executar em discos físicos sem um destino de testes autorizado.

## Canais e suporte

`1.0.0~rc2` é uma candidata. `1.0.0` só poderá ser publicada como estável depois da aceitação documentada da matriz acima e de uma política de manutenção definida. Nenhum prazo de suporte ou equipamento homologado será inventado para preencher essa etapa.

O catálogo público de webapps permanece separado do repositório APT local. Os artefatos da 0.9, a publicação anterior e as evidências históricas devem ser preservados. Não substituir uma publicação estável por uma candidata automaticamente.

## Referências técnicas

- [Guia de instalação Debian 13](https://www.debian.org/releases/trixie/installmanual).
- [Metadados AppStream](https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html).
