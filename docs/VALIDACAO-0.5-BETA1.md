# Validação da 0.5 Beta 1

Realizada em 31/10/2026.

ISO: `linuxbr-0.5.0~beta1-amd64.iso`.

SHA-256: `3f53748125141b565532f0071a19798014d5ec74d9cabb9e22c8410111de3990`.

- Build, checksum, entradas UEFI/BIOS e cópia local: aprovados.
- Instalação e entrada na sessão UEFI; boot Live BIOS em 1280×768: aprovados.
- 26 suítes de componentes e seis testes de ações de sessão: aprovados.
- EXE x86, EXE x64 e MSI executados no Wine; SuperTux Windows instalado, menu renderizado e encerramento com código zero. Jogabilidade não validada.
- Dois perfis Chromium com cookies e armazenamento local isolados e persistentes após reabrir, usando o ambiente completo do KDE. Contas reais não testadas.
- Backup com versões em outro disco virtual e restauração gráfica com verificação de SHA-256: aprovados.
- Atualização de instalação anterior preservou sete arquivos e quatro registros web, inclusive após reiniciar.
- Loja, favicons, seleção múltipla de perfis, progresso da configuração inicial e Gerenciador de Tarefas pelo menu da barra: observados na execução.

O relatório detalha os testes feitos no candidato inicial e as verificações repetidas na imagem final após duas correções visuais. Evidências no computador de compilação: `.cache/evidence/0.5-beta1/`.

Limites: hardware físico, antitrapaça, outros programas Windows, contas autenticadas e planos de backup agendados não validados. Não foi publicado um repositório próprio de atualizações. O instalador usa leiaute br/modelo pc105 e exibe rótulos incompletos de fuso/modelo no resumo; fuso aplicado America/Sao_Paulo.
