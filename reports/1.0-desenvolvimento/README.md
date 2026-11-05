# Validações de desenvolvimento — Linux BR 1.0

Estes resultados identificam separadamente as candidatas `1.0.0~rc1` e `1.0.0~rc2`. Não representam a liberação estável nem substituem os ensaios da ISO final.

## Candidata RC 2

- `source06`: a compilação da ISO falhou por falta de espaço. Nenhuma ISO RC 2 foi produzida nessa tentativa. Os 78 roteiros Python passaram antes da compilação; esse resultado não aprova uma instalação RC 2.
- A verificação real de perfis Chromium identificou o formato de título de processo com argumentos em uma única cadeia. A correção preserva caminhos com espaços e distingue processos principais, renderizadores e diretórios semelhantes. `web-profiles05-validation.json` identifica explicitamente a execução com o módulo corrigido sobre a instalação RC 1; `webapps06-unit.log` registra a regressão automatizada.
- `source07`: 739 arquivos; arquivo de fontes com SHA256 `1b1b7761efa3e9beaac080937ad57173ccabf10df4c3e52e6a150550c321223d`. Acrescenta a verificação de espaço antes do container; dois testes de limites e quinze testes dos comandos de compilação passaram em Linux.
- A nova compilação usa um serviço de sistema independente da sessão gráfica. Instalações em VMs serão executadas separadamente para evitar consumo simultâneo do volume. A conclusão dessa compilação e a validação da mídia RC 2 ainda estão pendentes.

## Fontes e pacotes

- `source05`: 737 arquivos; arquivo de fontes com SHA256 `282812ed1460fcce65f8a6a2e20b3ae926af9fb823733062118aa07bac3bc004`.
- 78 roteiros Python executados com sucesso no conjunto `source05`; o ensaio de controles nativos foi executado separadamente, com dispositivos virtuais e sessão local autenticada. Os testes que exigem contexto administrativo e o helper Places também têm resultados separados.
- Os oito pacotes nativos sem mudanças de código preservam as versões e os arquivos binários exatos da 0.9. Os componentes próprios do sistema usam `1.0.0~rc1`.
- O verificador de pacotes recebeu uma correção apenas de teste: usar o parser comum de versões também para o rótulo RC. Essa correção posterior não altera os pacotes nem a ISO compilados de `source05`.

## Resultados disponíveis

| Cenário | Resultado | Limite da evidência |
| --- | --- | --- |
| Regressões Python | 78 roteiros passaram | Alguns casos dependentes de contexto têm relatórios separados |
| Serviços, repositórios e ambiente | 23 testes administrativos passaram | Executor isolado; não modifica fontes APT existentes |
| Places e KIO | Passou | D-Bus privado, helper nativo e resolução de unidades |
| Controles de Wi-Fi, Bluetooth e áudio | Passou | Wi-Fi hwsim, Bluetooth VHCI e áudio virtual; não homologa hardware físico |
| Assistente inicial com fontes de 10, 14 e 20 pontos | Passou | Interface dos fontes em sessão Wayland; dez páginas em 1280×768 |
| Loja com fonte de 20 pontos | Passou | Fonte efetiva conferida nos cartões e ausência de rolagem horizontal nos detalhes |
| Consulta parcial e nova tentativa na loja | Passou | Interface instalada com resposta parcial controlada; sem instalar pacotes |
| Cancelamento PackageKit | Passou | Transação real de consulta; pedido autorizado pelo gerenciador; sem alterar pacotes |
| APT com TLS e assinatura | Passou | Download real em diretórios temporários; CA desconhecida e conteúdo adulterado recusados |
| Publicação estável sem aceitação | Recusada corretamente | Nenhuma saída criada e nenhuma assinatura solicitada |
| Atualização natural da 0.9 | Pacotes e dados conferidos | 11 pacotes atualizados, sem remoções ou reinstalação forçada; ponto de restauração automático |
| Conteúdo após atualização | Passou | 1.505 arquivos instalados correspondem aos pacotes; 1.793 arquivos pessoais preservados |
| Desktop UEFI e Secure Boot | Passou na ISO RC 1 `source05` | Instalação limpa, login Plasma, 1.505 arquivos de pacotes conferidos; não aprova a mídia RC 2 |
| Restauração e nova atualização | Passou na RC 1 | Retorno à 0.9, nova atualização, reinício e preservação de 1.793 arquivos pessoais |
| Modos de inicialização | Seis modos passaram na RC 1 | Segurança, rede restrita, terminal, recuperação, vídeo básico e diagnóstico; bloqueios sem exceção SSH nos modos restritos |
| Serviços, tarefas e variáveis | Passou na RC 1 | Operações reais de criação, edição, execução e reversão; relatórios separados |
| Máquinas virtuais e redes | Passou na RC 1 | VM de ensaio sem sistema convidado e redes privadas, internas e NAT; não comprova compatibilidade de sistemas convidados |
| Equipamentos físicos | Estabilidade da 0.9 relatada pelo usuário | Ryzen 5800H, i9 10900 e i7 14700; não valida a mídia final da 1.0 |

## Interpretação dos arquivos

Os nomes com `02`, `03` e `04` identificam ensaios anteriores. As imagens `store03-large-font.png` e `setup02-preview.png` registram problemas encontrados antes das correções; os resultados `store05-*` e `setup05-*` mostram o conjunto atual. O arquivo `setup03-layout-validation.json` usa um método anterior que não recriava a janela após mudar a fonte: para escala, usar `setup05-layout-created-fonts.json`, que confere a fonte efetiva.

Nos ensaios Qt da VM, há avisos do backend gráfico virtual e de componentes Qt/KDE nos logs. Eles foram preservados e não são apresentados como problemas corrigidos. O teste de controles executado inicialmente por SSH não tinha autorização de sessão local; o resultado válido é `quick-seat04.json`, obtido pelo terminal da sessão autenticada. O código desse teste não mudou entre `source04` e `source05`.

A instalação limpa Desktop UEFI, a restauração e a matriz de recuperação da RC 1 têm relatórios próprios. O disco descartável dessa instalação foi removido após coleta das evidências. A instalação Servidor RC 1 foi interrompida no incidente de espaço e não é apresentada como aprovada. Instalações Desktop UEFI/BIOS e Servidor UEFI da RC 2 permanecem pendentes até os respectivos relatórios.
