# Linux BR 0.9 Beta 1 — validação

Estado: Beta 1 compilada e validada em laboratório. Data: 5 de novembro de 2026. As limitações de homologação estão descritas abaixo.

## Identificação

- Versão dos pacotes: `0.9.0~beta1`.
- Fonte final: `source18`, 728 arquivos; servidor do catálogo entregue separadamente, com 19 arquivos de fontes.
- SHA256 do arquivo de fontes: `fed5eef1453318ccfb1ff0f64e9caa954b36c0c09e1aa1c2a50e58d711aac557`.
- ISO compilada: 3.659.857.920 bytes; SHA256 `e6c34cd34f7a106a819ccc2537ae6fca958c6ac0b402ad26dd024a03167f628d`.
- SHA256 do arquivo de pacotes: `ed10442a1614205ba9c87355dc3e2efea55c457f837f1d8ef632cfabfd42f40f`.
- Catálogo: <https://linuxbr.homedeveloper.com.br>.
- Pacotes gerados: 13 componentes Linux BR, três componentes Dolphin e cinco componentes KIO.

## Resultados registrados

| Cenário | Resultado | Evidência e alcance |
| --- | --- | --- |
| Regressões gerais | Passou | 76 scripts na source16; alterações posteriores de vídeo, versões e dependências verificadas separadamente. Não significa que os 76 scripts foram repetidos na source18 |
| Casos internos inicialmente pulados | Passou | 23 casos da plataforma no executor administrativo e três casos do Drive Manager com helper nativo |
| Correção de vídeo básico | Passou | Seis testes novos, nove testes de boot e sessão Plasma X11 autenticada com renderização por software |
| Instalação UEFI Desktop | Passou | Calamares source16, disco virtual vazio de 40 GiB, edição correta e primeiro boot no kernel 6.12.115+deb13.1-amd64 |
| Instalação UEFI Servidor | Passou | Calamares source17 em disco vazio, 68 pacotes de desktop removidos, primeiro boot autenticado sem Plasma; cerca de 600 MiB em VM de 3 GiB |
| Componentes finais nos sistemas novos | Passou | Pacotes source18 aplicados às instalações UEFI anteriores; 1.500 arquivos no Desktop e 916 no Servidor, sem divergências; reinício, autenticação, dpkg limpo e nenhuma unidade com falha |
| Atualização natural 0.8.5 → source18 | Passou | Pedido somente de linuxbr-release; oito pacotes nativos atualizados por dependência; 1.500 arquivos iguais aos pacotes finais, snapshot automático, reinicialização e 1.793 hashes pessoais preservados |
| Restauração de sistema | Passou | Timeshift retornou a VM isolada à 0.8.5, sem reinstalar GRUB e sem alterar os 1.793 arquivos pessoais |
| Segurança, segurança com rede, terminal e recuperação | Passou | Boots autenticados na VM de atualização; serviços, sockets, timers, paths e autostart bloqueados conforme o modo; firewall preservado |
| Diagnóstico | Passou | Registro systemd em debug; seleção consumida após um boot; retorno ao nível normal de registro |
| Reparo de menu | Passou | Regeneração real do GRUB, backup e restauração do menu após falha simulada |
| Shift + Reiniciar no Plasma | Passou | Recuperação autenticada, UID 1000, rede inativa, SSH mascarado, firewall ativo e retorno normal; evidência `desktop17-recuperacao-politica.png` |
| F8 instalado | Passou | Menu real com sete opções avançadas; inicialização normal após sair da recuperação |
| Compilação da mídia final | Passou | Compilação completa source18, 21 pacotes, verificações de estrutura e SHA256 conferidos; cópias no disco D: verificadas |
| Live final UEFI | Passou | ISO source18, recuperação autenticada, UID 1000, NetworkManager inativo, SSH ausente, firewalld ativo; reinício e retorno ao desktop normal com rede |
| Live final BIOS | Passou | SeaBIOS, ISO source18, login Plasma, terminal, identidade 0.9 Beta 1 e resolução 1280×768. Este cenário não inclui instalação BIOS |
| Live Servidor | Passou | Mídia source16, credenciais temporárias visíveis, login obrigatório e console sem Plasma |
| Edição Servidor instalada por transição | Passou | 68 pacotes de desktop removidos; aproximadamente 587 MiB em repouso na VM de 4 GiB; ferramentas próprias abriram |
| Virtualização na edição Servidor | Passou | KVM, UEFI, Secure Boot, TPM, pausa/retomada, recursos, adaptador adicional e checkpoint combinado; oito definições anteriores preservadas |
| Remoção e reinstalação de virtualização | Passou | Oito definições anteriores preservadas; recusa de substituição indevida de arquitetura pelo APT |
| Guarda de compatibilidade Windows | Passou | Remoção bloqueada com processos reais wineserver32 e wineserver64 em execução |
| Proteção APT sem desktop | Passou | Uma atualização real de pacote criou snapshot na edição Servidor |
| Propriedades nativas | Passou | Provas executadas novamente com o plugin source18 instalado após atualização natural: quatro aplicações, duas renomeações, título/caminho, hashes, permissões e seleção múltipla |
| Rede estruturada | Passou | Ethernet e interface WireGuard temporária com múltiplos endereços, máscaras e conectividade limitada; sem teste de tráfego com par VPN externo |
| Controles rápidos | Passou em laboratório | Alternância de Wi-Fi/Bluetooth e volume/silêncio com dispositivos simulados; estados anteriores restaurados |
| Catálogo público | Passou | PHP/MySQL/Angular estático, HTTPS, assinatura, busca, autenticação, CSRF, origem, cron horário e backup cifrado restaurado em banco vazio |
| Atualização de metadados de webapps | Passou | Revisão aplicada preservando perfis; mudança de domínio recusada; sem login real em contas de fornecedores |
| Publicação e manutenção APT | Passou | 0.9-beta1 ativa na porta 8443, publicação anterior preservada, chave e CA mantidas, manutenção diária executada; cliente validou HTTPS/assinatura e baixou os 21 pacotes com hashes iguais ao manifesto final |
| Sincronização de fontes | Passou | 728 arquivos do sistema e 19 do servidor conferidos com as fontes congeladas; backups anteriores preservados e arquivos alheios mantidos |

## Correções encontradas durante a validação

A opção anterior de vídeo básico com nomodeset podia deixar UEFI sem imagem. A correção usa sessão X11 temporária com renderização por software, driver genérico e retorno automático ao modo normal. Houve prova real nos kernels 6.12.113 e 6.12.115, além de seis testes de vídeo e nove de boot.

A comparação dos arquivos instalados revelou que a atualização source17 conservava oito pacotes nativos antigos porque repetiam as versões da 0.8.5. Essa candidata foi rejeitada. A source18 recompilou Dolphin e KIO com versões crescentes e passou a exigir esses componentes pelas dependências. A prova posterior restaurou a 0.8.5 e fez nova atualização natural, sem forçar reinstalação dos nativos. Consulte `upgrade17-payload-validation.json`, `cohort18-guard-validation.json` e `upgrade18-payload-validation.json`.

As instalações limpas usaram as mídias source16 (Desktop) e source17 (Servidor). A candidata source18 mudou versões, dependências e notas; seus pacotes foram aplicados, comparados e reiniciados nessas instalações. O boot Live final foi realizado com a ISO source18 em ambos os firmwares. Não foi repetida uma instalação completa a partir dessa última ISO.

## Entrega e evidências

Os artefatos estão em `D:/LinuxBR/0.9`: ISO, fontes, pacotes, fontes do catálogo, pacote de hospedagem, notas, documentação e evidências. `SHA256SUMS` identifica os arquivos públicos. Cópias intermediárias e parciais anteriores ficam identificadas em `validacao/`, fora dos artefatos finais.

Os relatórios JSON e capturas distinguem os ensaios das diferentes candidatas. Os arquivos `componentes-prototipo-evidencias.tar.gz` pertencem ao protótipo anterior e não comprovam execução na ISO final. A publicação APT é local ao laboratório; o catálogo de webapps é público na Hostinger.

## Limites

Esta versão é Beta. Não houve homologação física Intel/AMD, nem validação física de todos os adaptadores Wi-Fi, Bluetooth e áudio. O laboratório não comprova compatibilidade com todos os programas, jogos, periféricos ou firmwares. Há somente uma publicação Beta; não existe um canal Estável publicado.

Os modos de inicialização reproduzem objetivos familiares com mecanismos do Linux. Vídeo básico utiliza driver genérico, framebuffer quando necessário e renderização por software; sua resolução pode ser menor. Os arquivos temporários dessa seleção desaparecem no boot seguinte. A política de segurança não concede shell administrativo automático.

As VMs, discos virtuais e discos de restauração usados nestes ensaios são isolados. Os discos físicos e a VM visível de uso foram preservados.

O arquivo de fontes source18 corresponde à compilação e inclui o README final. As notas entregues são uma cópia desse README, sem alterações posteriores no código da ISO.

Referências técnicas da correção: [parâmetros do kernel](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html), [driver modesetting do X.Org](https://manpages.debian.org/trixie/xserver-xorg-core/modesetting.4.en.html).
