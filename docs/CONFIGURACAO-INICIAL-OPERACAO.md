# Ativação da configuração inicial do Linux BR Desktop

O instalador grava `/var/lib/linuxbr/initial-setup/pending` na raiz do sistema recém-instalado. O marcador deve pertencer ao root. O SDDM aguarda `linuxbr-initial-setup.service`, que prepara a conta de sistema bloqueada `linuxbr-setup` e inicia o assistente em uma sessão X11 dedicada. A sessão normal fica disponível pelo SDDM após concluir e entrar com a conta escolhida.

O serviço grava as etapas em `/var/lib/linuxbr/initial-setup/progress.json` com acesso somente para root. A retomada utiliza a primeira etapa incompleta. Se a criação de conta já começou, o assistente usa a mesma conta e pede a senha novamente. A etapa final substitui de forma atômica o marcador `pending` por `complete`, remove o autologin temporário e reinicia o SDDM.

## Opções disponíveis

- O teclado começa em Português (Brasil) ABNT2. O campo de teste aplica as mudanças na sessão atual e o assistente grava a escolha para o login seguinte.
- **Teclado na tela** preenche os campos de texto, incluindo senhas protegidas. **Leitor de tela** inicia o Orca na sessão dedicada de configuração. [Manual do Orca no Debian](https://manpages.debian.org/trixie/orca/orca.1.en.html)
- Ethernet funciona com perfis automáticos do NetworkManager. A lista de Wi-Fi oferece redes abertas e redes WPA pessoais com senha. A autenticação 802.1X depende da configuração específica da organização.
- O assistente distingue conexão do NetworkManager de acesso HTTPS ao catálogo público do Linux BR. A sugestão de fuso consulta o serviço [WorldTimeAPI](https://worldtimeapi.org/) pelo endereço IP público. O fuso sempre depende de confirmação. A seleção manual funciona sem internet.
- A conta local pode ser criada offline. O assistente verifica também o ingresso em Active Directory com realmd e o login pelo PAM do SDDM. O login corporativo segue as permissões concedidas pelo domínio.
- O LDAP independente usa LDAPS na porta 636 e SSSD no esquema RFC2307. O certificado deve corresponder ao nome do servidor e ter uma cadeia confiável para o sistema. O diretório precisa permitir consulta anônima aos registros de identidade POSIX. O perfil inicial autoriza a conta escolhida e preserva configurações SSSD administradas anteriormente. Uma falha de verificação invalida o novo perfil. [Guia LDAP do SSSD](https://sssd.io/docs/quick-start.html)
- A lista inicial oferece aplicativos DEB do catálogo da Loja. A instalação usa as fontes APT configuradas e mostra o aplicativo em andamento. Com falha de rede ou de pacote, o usuário pode tentar novamente ou avançar com a seleção vazia.
- O resumo apresenta as verificações de hardware informadas durante a instalação, quando houver registro.

## Predefinições de implantação

Selecione **Exportar predefinições** no resumo para guardar idioma da edição, teclado, fuso horário e aplicativos em um JSON. Escolha um local já montado com permissão de gravação, como uma unidade externa. A opção **Importar predefinições** na primeira tela de outra instalação usa essas escolhas como ponto de partida. O assistente mantém as confirmações de cada etapa. Dados pessoais, credenciais, ajustes de rede e resultados de testes de hardware continuam no computador em que foram usados.

## Evidências e diagnóstico

- Execute `QT_QPA_PLATFORM=offscreen python3 tests/test-initial-setup.py` a partir da árvore do projeto para testar etapas, retomada, fechamento bloqueado, fila opcional, recusa de TLS e reversão de novo perfil LDAP.
- Execute `LINUXBR_SETUP_EVIDENCE=/caminho/de/evidencias xvfb-run -a -s '-screen 0 1280x768x24' python3 tests/test-initial-setup.py` com o diretório de evidências criado para reproduzir as capturas do ciclo offline em uma tela de 1280 × 768.
- Se o primeiro boot apresentar falha, a consulta administrativa `journalctl -b -u linuxbr-initial-setup.service -u sddm.service` identifica a inicialização do assistente e a transição entre sessões.

As capturas Xvfb exercitam a interface gráfica com respostas de serviço simuladas. O teste de uma ISO limpa deve comprovar a integração com SDDM e criação da conta no disco, a passagem de Ethernet e Wi-Fi, o login com um diretório disponível e a liberação da sessão normal.
