# Rede e informações do sistema — 0.7

## Unidades Windows

O cadastro existente continua guardando apenas o endereço SMB, o nome e a letra da unidade na configuração pessoal. A senha não pode ser incluída na URL. As letras e os endereços permanecem disponíveis depois de reiniciar, mesmo quando a rede ou o computador de destino não está acessível.

O Gerenciamento de discos acrescenta **Reconectar**, também no menu de contexto da unidade, e **Senhas de rede**, que abre o Cofre de senhas do KDE. Abrir uma unidade de rede nessa janela primeiro confirma seu acesso, com limite de dois minutos. O estado mostrado informa o resultado da última tentativa, sem apresentar uma verificação antiga como disponibilidade atual. A atualização periódica da lista não estabelece conexões nem pede senhas.

A conexão usa `kioclient --interactive ls` do KDE. A listagem inicia o fluxo de autenticação do compartilhamento mesmo na primeira conexão; uma consulta apenas de metadados pode falhar antes de solicitar credenciais. A autenticação fica a cargo do KIO e a opção de lembrar credenciais, quando oferecida, usa o KWallet. O Linux BR não recebe a senha no cadastro, descarta a saída do cliente e não cria arquivos de credenciais, montagens de sistema, novos serviços ou tentativas automáticas em segundo plano. O acesso direto pelo Explorador continua usando o KIO SMB já existente.

Se a tentativa falha, a mensagem orienta conferir rede/VPN, computador de destino, compartilhamento, conta e permissões. Uma falha de autenticação não é apresentada como prova de que o servidor está desligado. O cadastro fica preservado para a próxima tentativa. A janela Mapear unidade também permite salvar sem conectar, ou reconectar após uma falha.

Dependências diretas: `kde-cli-tools`, `kio-extras` e `kwalletmanager`, além das dependências de desktop já existentes. No Debian 13 os executáveis são `kioclient` e `kwalletmanager5`; o código também reconhece nomes com sufixo 6 quando disponíveis.

Referências: [implementação do cliente KIO](https://github.com/KDE/kde-cli-tools/blob/master/kioclient/kioclient.cpp), [autenticação persistente do KIO](https://api.kde.org/kio-workerbase.html), [arquivos do kde-cli-tools no Debian 13](https://packages.debian.org/trixie/amd64/kde-cli-tools/filelist) e [arquivos do kwalletmanager no Debian 13](https://packages.debian.org/trixie/amd64/kwalletmanager/filelist).

## Sobre o Linux BR

A página Sistema da Central mantém os dados reais do computador e passa a destacar a versão instalada, lida de `/usr/share/linuxbr/release-info.json`, com alternativa em `os-release`. Versões alpha, beta e candidatas mostram aviso de desenvolvimento.

**Notas de lançamento** abre o README distribuído no pacote `linuxbr-system`, em `/usr/share/doc/linuxbr-system/README.md`, sem depender de Internet. Links executáveis ou caminhos locais presentes no documento não são abertos. Links HTTPS podem ser abertos por uma ação explícita do usuário.

**Salvar diagnóstico** reutiliza o relatório de suporte de Primeiros passos. O usuário escolhe o arquivo e pode revisá-lo antes de compartilhar. Cancelar não coleta nem grava o relatório. A documentação e o diagnóstico permanecem na Central existente.

## Validação

`QT_QPA_PLATFORM=offscreen python3 tests/test-network-about.py` verifica argumentos do cliente, sucesso e falha de conexão com processos locais controlados, timeout, cancelamento, preservação do cadastro, recusa de credenciais na URL, versão instalada, leitura offline das notas, bloqueio de links executáveis e exportação/cancelamento do diagnóstico. As suítes anteriores de unidades e interface devem continuar passando.

Também foi validado um compartilhamento SMB autenticado real em laboratório na VM: instância Samba temporária no loopback, porta 1445, com banco de contas e arquivos privados próprios. O cliente realizou escrita e leitura com conteúdo UTF-8 e nome de arquivo com espaços, preservando o SHA-256; SMB3 e criptografia foram exigidos. Senha incorreta e acesso anônimo foram recusados. O KIO sem credenciais também recusou a consulta. O servidor temporário foi encerrado e a configuração global do Samba e a senha da conta do sistema foram preservadas. Nenhum pacote precisou ser instalado para esse teste.

A autenticação gráfica também foi validada em uma instância separada, com rede apenas em loopback e sessão D-Bus, configuração pessoal e carteira próprias: a listagem abriu o diálogo nativo, aceitou a credencial de laboratório e criou uma carteira KWallet criptografada. Depois da autenticação, novas consultas de listagem e metadados retornaram sucesso. A primeira consulta de metadados havia falhado sem mostrar o diálogo, motivando o uso de listagem na conexão.

Um servidor Windows real e a desconexão/reconexão de rede física permanecem para homologação. A persistência das credenciais depende da configuração e do desbloqueio do cofre escolhidos pelo usuário; o sistema não desativa sua proteção para evitar uma solicitação de senha.
