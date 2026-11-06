# Credenciais e logins de aplicativos

O armazenamento seguro da sessão deve estar disponível antes de entrar em aplicativos que lembram contas. O Linux BR inclui GNOME Keyring, integração PAM e libsecret explicitamente no pacote da Central, além do gerenciador de cofres. O KWallet continua disponível para aplicativos KDE.

Ao entrar no desktop, `linuxbr-credentials --prepare-session` consulta o cofre padrão. Se estiver bloqueado, o próprio provedor apresenta a solicitação de desbloqueio. Se não existir, o provedor pode solicitar a criação de um cofre protegido. Cancelar não bloqueia o desktop. Nenhuma senha é recebida pelo comando do Linux BR, passada como argumento ou registrada em arquivo.

A RC 3 também corrige a ordem de inicialização em contas novas: o PAM prepara e desbloqueia o cofre no login, e a ativação D-Bus inicializa o serviço depois. As unidades globais antecipadas do GNOME Keyring são desabilitadas uma vez na configuração do pacote. A política não reinicia processos da sessão nem modifica arquivos de cofres; contas já abertas recebem a nova ordem no próximo login. Preferências posteriores do administrador são preservadas.

A senha do cofre pode ser diferente da senha atual da conta depois de uma redefinição administrativa. Nessa situação, use a senha anterior do cofre e altere-a pelo gerenciador de credenciais. O sistema não apaga, substitui ou redefine automaticamente cofres existentes, mesmo que pareçam vazios. Entradas e logins de outros aplicativos são preservados.

## Conferência e recuperação

- **Configurações → Contas → Desbloquear credenciais e senhas** solicita o desbloqueio seguro.
- **Configurações → Contas → Gerenciar senhas e cofres** abre o gerenciador nativo.
- **Cuidados com o computador → Login e senhas dos aplicativos** consulta o estado e testa o armazenamento quando já está desbloqueado.
- `linuxbr-credentials --check` retorna apenas o estado, sem ler senhas salvas e sem abrir solicitações.
- `linuxbr-credentials --check --probe` cria uma única entrada aleatória, confere a leitura e a remove. Não consulta credenciais de outros aplicativos.

A verificação inicial de contas também sinaliza cofre bloqueado, ausente ou indisponível. As consultas têm prazo; uma falha do provedor não deve travar a Central. Cancelar um desbloqueio nunca transforma o cofre em armazenamento sem senha.

## Contas novas e instalação

A compilação dos pacotes e a conferência do sistema montado recusam cofres pré-criados em `/etc/skel/.local/share/keyrings` e `/etc/skel/.local/share/kwalletd`, inclusive links indiretos. Contas novas devem criar o próprio armazenamento com suas credenciais. Não copie o cofre da sessão live, de contas de laboratório ou de outro usuário para a conta instalada.

A integração PAM acompanha logins por senha e alterações normais de senha. Entrada automática, biometria e redefinição administrativa podem exigir o desbloqueio separado do cofre; essas situações não autorizam apagar senhas existentes.

## Microsoft 365 pelo Bottles

O navegador retorna ao Bottles pelo protocolo `ms-appx-web`. Essa passagem faz parte do login e deve voltar ao aplicativo que iniciou a autenticação. Se houver um seletor, escolha o Bottles instalado. Não associe esse protocolo a uma receita fixa de Word ou a um perfil específico: a sessão de origem deve receber a resposta.

Na investigação no computador de referência, o retorno chegou ao processo de autenticação, mas a gravação falhou porque o cofre de login estava indisponível/bloqueado. O cofre vazio foi preservado e corrigido nessa máquina. O procedimento de recuperação manual não se torna uma rotina de exclusão no sistema.

O desbloqueio do cofre e o retorno do navegador não comprovam ativação do Office. Confira a conta, o estado da licença e os testes de edição, salvamento e reabertura. O suporte experimental depende também das versões do Bottles, do Wine e do aplicativo.

Esta revisão de código será incorporada aos próximos pacotes/imagens; não altera retroativamente a ISO 1.0 RC 2 já distribuída.

Referências: [integração PAM do GNOME Keyring](https://wiki.gnome.org/Projects/GnomeKeyring/Pam/Manual), [cofre padrão](https://help.gnome.org/seahorse/keyring-change-default.html), [compatibilidade experimental do Microsoft 365](https://github.com/bottlesdevs/programs/issues/500).
