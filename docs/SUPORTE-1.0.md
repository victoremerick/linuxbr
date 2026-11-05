# Suporte e homologação — Linux BR 1.0

Estado: candidata RC 2. A publicação estável exige a aprovação dos equipamentos, dos cenários e da política de manutenção. Os resultados da RC 1 ficam vinculados aos artefatos daquela candidata.

## Matriz de validação

| Alvo | Estado na 1.0 | Critério |
| --- | --- | --- |
| Desktop UEFI em VM | Pendente na mídia final | Instalar pela ISO exata, autenticar, conferir rede e pacotes |
| Desktop BIOS em VM | Pendente na mídia final | Instalar pela ISO exata e validar o primeiro boot |
| Servidor UEFI em VM | Pendente na mídia final | Instalar pela ISO exata, autenticar e conferir ausência de Plasma |
| Atualização a partir da 0.9 | Pendente | Atualização natural, snapshot, dados preservados e retorno após restauração |
| UEFI com Secure Boot | Pendente | Inicialização com verificação habilitada e evidência do estado real |
| Computadores físicos | Estabilidade da 0.9 Beta 1 relatada pelo usuário | Três configurações registradas abaixo; validação da mídia final da 1.0 pendente |
| GPU, Wi-Fi, Bluetooth, áudio e suspensão físicos | Não homologados | Testes por modelo e versão de driver |
| Convivência com Windows e volumes cifrados | Não homologada | Ensaio de particionamento e preservação dos sistemas e dados existentes |

As evidências da 0.9 continuam históricas. Um relatório da 1.0 precisa identificar a versão, o firmware, a edição, os recursos da VM ou modelo físico e o SHA256 dos artefatos usados.

### Testes físicos relatados em 5 de novembro de 2026

O usuário informou que utilizou a última ISO gerada da 0.9 Beta e encontrou o sistema estável nas seguintes configurações. O artefato correspondente é `linuxbr-0.9.0~beta1-amd64.iso`, SHA256 `e6c34cd34f7a106a819ccc2537ae6fca958c6ac0b402ad26dd024a03167f628d` (identificação pelo histórico de entrega; não foi relatada uma conferência independente do hash no equipamento).

| Processador informado | Memória informada | Resultado relatado |
| --- | --- | --- |
| Ryzen 5800H | 16 GB DDR4 | Estável |
| i9 10900 | 64 GB DDR4 | Estável |
| i7 14700 | 16 GB DDR5 | Estável |

O modelo completo dos computadores, o firmware e os testes individuais de vídeo, rede, áudio, reinício e suspensão não foram informados. Esses relatos ampliam o histórico de uso físico, mas não constituem validação da ISO final da 1.0 nem aprovação individual desses recursos. Os nomes dos processadores foram preservados conforme informados.

## Recursos e requisitos

Os ensaios da 0.9 usaram Desktop com 4 GiB e duas CPUs virtuais, e Servidor com 3 GiB e duas CPUs virtuais. Esses números identificam o laboratório anterior. A recomendação da 1.0 será consolidada com as medições da mídia final, incluindo memória em repouso e espaço ocupado após a instalação.

Jogos, edição de vídeo, múltiplos perfis web e máquinas virtuais exigem recursos adicionais conforme o aplicativo. A virtualização precisa de aceleração disponível no equipamento e memória suficiente para hospedeiro e convidados.

## Manutenção

A proposta de lançamento precisa definir responsável pela manutenção, canal de distribuição, período de correções, procedimento de atualização e aviso de descontinuação. Enquanto essa política e a matriz de homologação estiverem pendentes, o canal permanece RC.

O repositório APT do laboratório e o catálogo público de webapps têm destinos distintos. A disponibilização do catálogo na internet não disponibiliza automaticamente o repositório de pacotes do sistema.

O [repositório do projeto](https://github.com/victoremerick/linuxbr) reúne os fontes, o histórico e as evidências públicas. Ao relatar um problema, informe versão, etapa, modelo do equipamento e mensagem apresentada, preservando senhas e dados pessoais.
