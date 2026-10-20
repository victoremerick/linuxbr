# Usuários e domínio corporativo

A Central do Sistema oferece duas páginas:

- **Usuários:** lista as contas locais, nome completo, tipo e bloqueio via AccountsService. “Gerenciar contas e senhas” abre o módulo de usuários do KDE, já utilizado pelo sistema, para criação, exclusão, senha e privilégios. Depois de fechar o módulo, use Atualizar. Contas corporativas não são tratadas como contas locais.
- **Organização:** descoberta de Active Directory, ingresso com conta autorizada e OU opcional, consulta de estado/formato de login/política e saída do domínio com confirmação explícita.

## Conectar

1. Configure a conexão ou VPN e o DNS da empresa. Confira a hora do computador.
2. Abra Organização, informe o domínio DNS completo e escolha Localizar domínio.
3. Selecione Conectar e informe a conta autorizada pela empresa. A OU opcional deve ser um DN LDAP, como `OU=Linux,DC=empresa,DC=com,DC=br`.
4. Atenda à autenticação administrativa local solicitada pelo polkit. Aguarde a conclusão e confira o estado.
5. Encerre a sessão. Na tela de login, use “Outro…” e o formato informado pela Central. O primeiro acesso precisa de conexão com o domínio.

O ingresso usa realmd com SSSD/adcli. A política de acesso permanece sob controle do domínio/SSSD; não há concessão automática de sudo a usuários corporativos. Preserve uma conta administrativa local. Certificados, GPOs personalizadas, gestão de grupos do AD e administração do servidor de domínio não são implementados por esta página.

A saída exige credenciais autorizadas e confirmação digitada do domínio. O acesso corporativo pode parar de funcionar; arquivos locais não são apagados pela interface. Em caso de erro ou timeout, atualize o estado antes de repetir uma operação.

## Integração e segurança

As operações usam D-Bus e as autorizações originais de realmd/AccountsService. Nenhuma regra permissiva de polkit foi adicionada. Senhas seguem por pipe para o processo auxiliar e D-Bus para realmd, sem argumentos de linha de comando nem arquivos. Erros exibidos ocultam a senha recebida. A janela aguarda operações pendentes antes de fechar.

O pacote instala realmd, adcli, SSSD AD, integração NSS/PAM e dependências. Na primeira instalação de linuxbr-system, `pam-auth-update --package --enable mkhomedir` habilita a criação do diretório pessoal no login, respeitando a proteção contra sobrescrita de configuração PAM manual. Atualizações não reativam uma escolha posteriormente desabilitada pelo administrador. Instalações existentes precisam habilitar esse perfil via `sudo pam-auth-update` caso ainda não esteja ativo.

## Validação

- `QT_QPA_PLATFORM=offscreen python3 tests/test-accounts.py`: valida domínio, redação de senha em erros, contrato D-Bus de credenciais e botões da interface.
- `QT_QPA_PLATFORM=offscreen python3 tests/test-system-central.py`: navegação e integração das páginas, preservando armazenamento.
- Consulta real de AccountsService e realmd em contêiner Debian Trixie descartável, incluindo conta local de teste.

O teste `python3 tests/domain-vm-smoke.py` inicia duas VMs descartáveis com KVM: um Samba Active Directory e um cliente Linux BR, ligados por uma rede privada entre processos QEMU. Os pacotes são instalados apenas nas VMs; senhas são geradas por execução e apagadas com o ambiente temporário. A ISO é somente leitura. Os registros e hashes ficam em `.cache/domain-vm.*/`.

O teste usa o backend atual injetado no live e a configuração PAM do SDDM para autenticação, autorização e abertura/fechamento de sessão, incluindo criação de home. Esse modo padrão não automatiza a tela gráfica. A validação gráfica complementar está descrita abaixo. A ISO precisa ser recompilada para incorporar os novos componentes. Políticas específicas de um domínio Windows empresarial ainda exigem validação nesse ambiente.

### Resultado do laboratório AD

A autenticação usa uma conta corporativa real no Samba AD. O laboratório aplica `realm permit employee@lab.example.test` apenas no cliente descartável para autorizar explicitamente esse usuário. No AD Samba recém-provisionado, a senha foi aceita com a política padrão, mas a etapa de autorização PAM retornou erro; isso é registrado como `DEFAULT_AD_POLICY_LOGIN=denied`. Portanto, esse teste não comprova que as políticas padrão ou GPOs de qualquer empresa permitirão o login automaticamente. Não foi aplicado relaxamento de GPO na distribuição.

O ciclo completo verifica descoberta, ingresso pelo backend da Central, resolução NSS, ausência de grupo sudo para o usuário corporativo, login PAM com permissão explícita, criação do diretório pessoal, recusa de senha incorreta, saída pelo backend e recusa de login corporativo após a saída. A conta local administrativa é conferida antes, durante e depois do ingresso. As chamadas de ingresso/saída neste teste rodam como root na VM; o diálogo gráfico de autorização polkit não faz parte deste ensaio.

Execução concluída em 19/10/2026: **11 verificações passaram** no ciclo com permissão explícita. Evidências locais: `.cache/domain-vm.6532rg8d/summary.txt`, `client.log`, `dc.log` e `manifest.json` (hash da ISO e dos fontes testados). As duas VMs e os arquivos temporários contendo credenciais foram removidos.


### Validação gráfica do SDDM e Plasma — 19/10/2026

Concluída em duas VMs descartáveis, usando o mesmo Samba AD e permissão explícita para `employee@lab.example.test`:

- Autologin desativado apenas na VM; entrada pelo botão **Outro…**, usuário completo e senha no formulário real do SDDM.
- SDDM registrou autenticação SSSD bem-sucedida; `loginctl` confirmou `Service=sddm`, `Desktop=KDE`, `Type=wayland`, `State=active` e o UID do domínio.
- `plasmashell` e `kwin_wayland` executaram com o UID corporativo. Foram capturados o desktop e um Konsole com `whoami`, `id` e o processo Plasma.
- Entrada gráfica de `localadmin` também abriu o Plasma. A senha local autorizou `sudo id -u`, que retornou `0`.
- Um segundo login corporativo passou. O encerramento normal das sessões local e corporativa via serviço de logout do KDE retornou ao SDDM.
- Depois, a saída do domínio passou, o login corporativo foi recusado e a autenticação local continuou funcionando. As VMs e credenciais foram removidas.

Evidências: `.cache/domain-vm.smmrryk2/graphical-summary.txt`, `domain-session.txt`, `local-session.txt`, `sddm-journal.txt`, `domain-desktop.png`, `local-desktop.png`, `after-logout.png`, `summary.txt` e `manifest.json`.

A primeira troca entre sessões usou encerramento forçado por `loginctl`, que interrompeu o helper do SDDM e exigiu reiniciar esse serviço no laboratório. Depois, foi repetido o login corporativo e verificado o logout normal do KDE, que retornou ao greeter sem essa intervenção. O evento está preservado nos registros.

O runner `python3 tests/domain-vm-smoke.py --graphical` prepara a validação **supervisionada**: expõe um socket QMP privado e um diretório temporário de controle, mostra seus caminhos e aguarda ações do operador. Não é um teste gráfico completamente automático. O canal é exclusivo da VM de teste e nunca é instalado na distribuição. Permite executar ações em `command.sh`, colher respostas em `output.txt`, capturar a tela via QMP e finalizar com `done`. A conclusão exige evidências das duas sessões e do sudo local. O timeout remove o ambiente se o operador não concluir.

Escopo: ISO live existente, somente leitura, com backend atual injetado e dependências instaladas nas VMs. Não valida uma nova ISO compilada nem GPOs específicas de uma empresa. Nenhuma configuração de produção foi modificada.
