# Ondas de atualização do Linux BR

Este serviço fica na infraestrutura da organização, na rede interna ou por VPN. Ele gerencia a autorização da revisão e o inventário básico. Os pacotes continuam no [repositório APT assinado](../../docs/REPOSITORIO-ATUALIZACOES.md). O serviço entrega uma autorização OpenPGP de curta duração vinculada ao dispositivo, à onda, à solicitação e ao SHA-256 de todos os DEBs do lote.

## Preparar o servidor

1. Instale Python 3, Gunicorn, GnuPG e um proxy HTTPS. Crie a conta de serviço `linuxbr-waves` e a pasta privada `/var/lib/linuxbr-waves`, com modo `0700` e propriedade dessa conta.
2. Coloque `waves_server.py`, `panel.html`, `panel.js` e `panel.css` em `/opt/linuxbr-waves`. Mantenha o código sob propriedade administrativa e sem escrita pela conta de serviço.
3. Crie uma chave de assinatura dedicada em `/var/lib/linuxbr-waves/gnupg`, sob a conta de serviço. Configure uma forma não interativa de assinatura e confira a impressão digital com a equipe de TI. A chave privada fica no servidor.
4. Sob a conta de serviço, inicialize o banco e cadastre operadores e dispositivos. Guarde o token individual mostrado por cada comando em um cofre. O banco mantém o hash do token.

```sh
cd /opt/linuxbr-waves
python3 waves_server.py --database /var/lib/linuxbr-waves/waves.sqlite init exemplo
python3 waves_server.py --database /var/lib/linuxbr-waves/waves.sqlite operator suporte
python3 waves_server.py --database /var/lib/linuxbr-waves/waves.sqlite device estacao-piloto pilot
python3 waves_server.py --database /var/lib/linuxbr-waves/waves.sqlite device estacao-geral general
```

O cadastro de operador aceita `--role admin|release|support|audit`. O papel `release` promove, pausa e retoma ondas. `support` solicita, consulta e descarta diagnósticos. `audit` consulta os estados e o histórico. O papel `admin` também gerencia dispositivos e atribuições de perfil. O serviço verifica o papel em cada operação, inclusive quando a chamada é feita fora do painel.

Configure `/etc/linuxbr-waves/server.env` com os valores da organização:

```ini
LINUXBR_WAVE_DB=/var/lib/linuxbr-waves/waves.sqlite
LINUXBR_WAVE_GNUPG=/var/lib/linuxbr-waves/gnupg
LINUXBR_WAVE_KEY=IMPRESSAO_DIGITAL_OPENPGP
LINUXBR_WAVE_ORIGIN=https://ondas.exemplo.interno
```

A unidade `linuxbr-waves.service` serve apenas em loopback. Configure o proxy para encaminhar o virtual host HTTPS inteiro para `http://127.0.0.1:8780`, incluindo o cabeçalho `Authorization`. Ative o armazenamento temporário do corpo das solicitações no proxy, limite o corpo a 16 KiB e aplique limites de conexão. O navegador solicita o nome do operador e seu token ao abrir o endereço. Use a origem exata do navegador em `LINUXBR_WAVE_ORIGIN`. [Implantação do Gunicorn](https://docs.gunicorn.org/en/stable/deploy.html)

Faça backup consistente do SQLite e do material de assinatura de acordo com a política da organização. Relatórios de diagnóstico são removidos após sete dias a partir da solicitação. O comando `purge` pode ser agendado para aplicar essa retenção mesmo sem tráfego. Restrinja os backups e os logs do proxy. Evite registrar cabeçalhos de autenticação ou corpos.

## Cadastrar um cliente

Coloque o token individual em `/etc/linuxbr/update-wave-token` com proprietário root e modo `0600`. Coloque o chaveiro público OpenPGP da organização em `/etc/linuxbr/update-wave-keyring.gpg`. Confira a impressão digital antes de confiar na chave. Quando o proxy usa uma CA própria, instale o certificado público em `/etc/linuxbr/update-wave-ca.pem` e configure `ca_file`.

```json
{
  "schema": 1,
  "organization": "exemplo",
  "device": "estacao-piloto",
  "wave": "pilot",
  "endpoint": "https://ondas.exemplo.interno",
  "token_file": "/etc/linuxbr/update-wave-token",
  "ca_file": "/etc/linuxbr/update-wave-ca.pem"
}
```

Grave o cadastro em `/etc/linuxbr/update-waves.json`, com proprietário root e sem escrita por grupo ou outros usuários. Omita `ca_file` ao usar uma CA já confiável pelo sistema. Configure previamente o destino de recuperação do Timeshift.

Em um dispositivo já cadastrado, habilite a consulta periódica com `sudo systemctl enable --now linuxbr-update-inventory.timer`. Para conferir o primeiro contato imediatamente, execute `sudo systemctl start linuxbr-update-inventory.service`.

## Liberar e acompanhar uma revisão

1. Prepare um conjunto exato de DEBs e dependências para as máquinas com a mesma base de pacotes. Cadastre-o com `python3 waves_server.py --database /var/lib/linuxbr-waves/waves.sqlite stage REVISAO pacote1.deb pacote2.deb`. Alterações no lote exigem outro identificador.
2. No painel, selecione a revisão e libere-a para o piloto. O cliente cadastrado pede autorização fresca no gancho APT. Ausência de rede, pausa, revisão incompatível ou uma assinatura incorreta interrompem a transação de instalação. O gancho exige um ponto de recuperação antes de seguir.
3. A equipe de TI verifica a instalação, a reinicialização quando necessária e a saúde do equipamento. Abra **Backup e recuperação → Atualizações → Revisar resultado da atualização gerenciada** para conferir o lote e registrar o resultado. Para verificações administrativas pelo terminal, use `sudo /usr/lib/linuxbr-system/wave_review.py preview` e depois `sudo /usr/lib/linuxbr-system/wave_review.py submit REVISAO ESTADO` com o estado retornado. O painel separa autorização de resultado confirmado.
4. Promova a mesma revisão após todos os pilotos habilitados confirmarem conclusão. Pausar ou retirar bloqueia novas autorizações. Um piloto com falha ou restauração exige uma nova revisão para seguir.

Uma máquina cadastrada para gestão só instala lotes de arquivos DEB autorizados no fluxo APT. Misturar atualizações pendentes ou instalações fora do lote faz a validação falhar. As consultas de índices permanecem disponíveis. O cadastro local e a assinatura dos índices APT continuam necessários. A gestão por ondas não controla transações diretas do dpkg nem outros gerenciadores.

Para restringir novas autorizações a um horário, selecione a revisão no painel e configure **Janela de manutenção** antes de liberar o piloto. Informe início, fim e o fuso aplicado às duas datas. O painel mostra o intervalo em UTC para confirmação e registra no histórico quem cadastrou, reagendou ou removeu a janela. Operadores de liberação e administradores podem alterar a janela. Removê-la devolve a revisão ao controle normal pelas ondas e pela pausa.

A janela permite autorizações a partir do início e as bloqueia a partir do fim. Dentro do intervalo, a validade do manifesto assinado termina em até dois minutos ou no fim da janela, o que chegar primeiro. Pausar ou reagendar afeta as próximas solicitações. Uma autorização já emitida mantém a validade registrada. O usuário inicia a atualização e decide quando reiniciar pelos controles locais. O registro do resultado continua disponível depois do horário.

Use o cache do repositório APT ou copie um DEB de laboratório para um diretório administrativo antes de testar. O gancho aceita apenas arquivos regulares, protegidos e pertencentes ao root, em um caminho protegido contra substituição por outras contas. Essa proteção vale desde a conferência do lote até a abertura pelo dpkg.

Para atualizar apenas o inventário, use `sudo python3 /usr/lib/linuxbr-system/update_waves.py heartbeat`. O inventário inclui a versão do Linux BR, o espaço livre do sistema, a indicação de reinício e o último contato registrado pelo servidor.

## Diagnóstico

O painel pode solicitar diagnóstico de um dispositivo cadastrado. A solicitação expira após 24 horas. A máquina consulta a solicitação e o envio exige revisão local e consentimento. O servidor aceita somente campos estruturados, permite descartar os dados e registra a consulta administrativa no histórico. Uma solicitação para uma máquina não pode ser respondida por outra.

## Perfis de preparação

Cadastre uma lista JSON de regras com `stage-policy PERFIL arquivo.json`. Cada regra tem `id`, `required` booleano e `value`. As primeiras preferências são `work-folder`, com um único nome de pasta, e `store-search`, com uma lista de termos para procurar na Loja. O painel permite atribuir um perfil a cada dispositivo cadastrado. O cliente valida a assinatura, a solicitação e o dispositivo antes de mostrar a preparação à pessoa.

```json
[
  {"id": "work-folder", "required": false, "value": "Trabalho"},
  {"id": "store-search", "required": false, "value": ["editor de texto", "videoconferência"]},
  {"id": "store-snap", "required": true, "value": false},
  {"id": "store-brew", "required": true, "value": true}
]
```

Com `required: true`, `store-snap` e `store-brew` controlam as permissões das duas fontes na Loja Linux BR. `false` bloqueia a fonte para todas as contas; `true` permite que cada pessoa opte por habilitá-la. As regras não instalam nem removem pacotes ou gerenciadores e não controlam seu uso direto pelo terminal. Uma regra de fonte opcional não altera a máquina.

Nas configurações de preparação, um administrador local revisa os valores e autoriza a aplicação pelo Polkit. Na aplicação, o cliente busca de novo o perfil assinado e confirma a revisão e a impressão digital apresentadas. A mudança das duas permissões usa um único arquivo protegido do sistema. O histórico local registra as aplicações e reversões. Uma revisão que deixa de gerenciar uma fonte devolve a configuração anterior daquela fonte. A opção de restaurar desfaz as permissões gerenciadas; se um valor gerenciado tiver sido alterado manualmente, o cliente aponta o conflito e preserva os valores atuais.

Regras futuras podem ser distribuídas como valores declarativos limitados em tamanho. Uma regra obrigatória sem suporte impede a aplicação dos controles da máquina e mantém o preparo pendente. Uma nova revisão recebe outro identificador. Retirar uma atribuição interrompe sua distribuição; para desfazer controles já aplicados, restaure-os localmente ou atribua uma nova revisão que deixe de gerenciá-los.

## Validação

Execute `python3 test_wave_server.py` com GnuPG e OpenSSL. A bateria usa banco, certificados e chaves descartáveis. Ela cobre autorização antes, durante e depois da janela, registro de resultado após o fim e atualização de bancos anteriores. O cenário com HTTPS verifica a assinatura no cliente, aplica e restaura uma permissão da Loja em um diretório temporário e recusa uma nova autorização quando o servidor pausa a onda ou fica indisponível. A bateria `tests/test-organization-machine-policy.py` cobre conflitos locais e interrupções durante a gravação. Execute-a como root em um ambiente de teste para incluir a leitura do arquivo pela Loja.
