# Linux BR 1.0 RC 3

Esta é uma versão candidata, baseada em Debian 13 e KDE Plasma. A ISO reúne
as revisões posteriores à RC 2 em uma nova compilação. Ainda não representa
a aprovação de uma versão estável nem compatibilidade universal com hardware
ou programas Windows.

## O que mudou

- Cofre de credenciais: preparação na sessão, desbloqueio pelo provedor nativo,
  diagnóstico com entrada temporária e dependências explícitas. A ordem entre
  autenticação PAM e ativação D-Bus evita o cofre indisponível no primeiro login.
  Cofres existentes
  são preservados e a compilação rejeita cofres pré-criados em contas novas.
- Janelas de programas Windows: lançador de perfil X11/Xwayland para Bottles,
  mantendo as janelas sob controle do desktop. O ensaio do Word no computador
  de referência confirmou minimizar, maximizar e restaurar. Microsoft 365 é
  experimental; ativação, edição e gravação não foram homologadas por esse ensaio.
- Menu Iniciar e atalhos: recuperação do catálogo do Plasma com validação da
  definição de menu e preservação das fontes Flatpak.
- Loja: suporte a links `linuxbr-store://`, abrindo a ficha do aplicativo em vez
  de instalar silenciosamente. A identidade assinada da fonte é respeitada;
  sites não podem executar comandos ou impor uma nova fonte por esses links.
- Projeto: novo site de apresentação, loja web e painel de gerenciamento,
  com versões disponibilizadas pelo GitHub Releases.

## Downloads e verificação

Os arquivos anexos incluem os resultados da validação da candidata, o código
correspondente e os checksums. Use os relatórios desta release para identificar
os cenários efetivamente aprovados; ensaios de versões anteriores permanecem
históricos.

Se a ISO estiver dividida em arquivos `.partNNN`, baixe todas as partes,
confira `SHA256SUMS` e siga as instruções de recomposição abaixo. A ISO completa
deve corresponder ao hash em `ORIGINAL-SHA256SUMS` antes de gravar o pendrive.

## Instalação e limites

Faça backup dos seus arquivos. Inicialize a mídia no modo UEFI recomendado ou
BIOS, experimente o modo Live e use o instalador para escolher o disco de destino.
A seleção de um disco pode apagar seus dados: confira o resumo do instalador.

Os programas comerciais, jogos, contas e licenças do usuário não são incluídos
na ISO. Wine e Steam/Proton dependem da compatibilidade de cada título, dos drivers
e do hardware. O Microsoft 365 instalado no computador de referência não faz
parte da distribuição. Serviços web exigem internet e seguem as condições dos
respectivos fornecedores.

As atualizações APT continuam usando seu repositório assinado. GitHub Releases
distribui as imagens e informações de versão; não substitui a validação de
assinaturas das atualizações do sistema.
