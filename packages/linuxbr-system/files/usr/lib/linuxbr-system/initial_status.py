"""Read-only observations for the initial configuration checklist."""
import os
from pathlib import Path
import shutil
import subprocess


def command(argv):
    try:
        value = subprocess.run(argv, capture_output=True, text=True, timeout=6,
                               env={**os.environ, 'LC_ALL': 'C'})
        return value.stdout.strip() if value.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def observe(section):
    if section == 'accounts':
        import pwd
        try:name=pwd.getpwuid(os.getuid()).pw_name
        except KeyError:name='não identificada'
        return dict(state='information',text='Conta desta sessão: '+name+'. Confira suas opções de acesso nas Configurações. Nenhuma senha é consultada por esta verificação.')
    if section == 'network':
        state = command(['nmcli', '-t', '-f', 'STATE', 'general'])
        internet = command(['nmcli', '-t', '-f', 'CONNECTIVITY', 'general'])
        if state.startswith('connected'):
            text = 'O gerenciador de rede informa uma conexão ativa.'
            text += (' A verificação de conectividade informa acesso à internet.' if internet == 'full'
                     else ' Abra um site para conferir o acesso à internet; a conexão pode ser somente local.')
            return dict(state='information', text=text)
        return dict(state='attention', text='Não foi encontrada uma conexão ativa. Confira o cabo ou selecione uma rede Wi-Fi.')
    if section == 'region':
        zone = command(['timedatectl', 'show', '--property=Timezone', '--value'])
        locale = os.environ.get('LC_ALL') or os.environ.get('LANG', '')
        return dict(state='information', text='Idioma da sessão: '+(locale or 'não informado')+
                    '. Fuso horário: '+(zone or 'não informado')+'. Experimente acentos e confira se correspondem à sua preferência.')
    if section == 'updates':
        from update_status import release_status
        status = release_status()
        text = 'Versão instalada: '+(status['installed'] or 'não identificada')+'. '
        text += ('Fonte Linux BR configurada. ' if status['sources'] else 'Nenhuma fonte Linux BR ativa foi identificada. ')
        text += ('Versão nos índices locais: '+status['candidate']+'. ' if status['candidate']
                 else 'Não foi possível identificar uma candidata nos índices locais. ')
        text += 'Atualize os índices na Loja antes de revisar as atualizações.'
        return dict(state='information' if status['sources'] else 'attention', text=text)
    if section == 'backup':
        from protection_status import backup_plans
        plans = [plan for plan in backup_plans() if plan.get('enabled')]
        completed = [plan for plan in plans if plan.get('last_complete')]
        if completed:
            return dict(state='information', text='Há '+str(len(completed))+' plano(s) com registro de cópia concluída. '
                        'Confira o destino e experimente restaurar um arquivo; o registro não comprova que a restauração funciona.')
        return dict(state='attention', text='Não foi identificado um plano ativo com cópia concluída. Configure o backup e faça a primeira cópia.')
    if section == 'apps':
        browser = any(shutil.which(name) for name in ('chromium', 'firefox', 'firefox-esr'))
        return dict(state='information' if browser else 'attention',
                    text=('Há um navegador instalado. ' if browser else 'Nenhum navegador conhecido foi encontrado. ')+
                    'Abra os arquivos que você usa e escolha os aplicativos padrão nas Configurações.')
    manual = {
        'migration': 'Abra os arquivos copiados e confira as pastas. Esta etapa não inicia uma migração nem altera a origem.',
        'display': 'Confira se todos os textos estão legíveis e se janelas, resolução e escala atendem à sua tela.',
        'devices': 'Reproduza um som, grave o microfone e imprima uma página de teste nos dispositivos que pretende usar.',
        'daily': 'Experimente seus pendrives, compartilhamentos e tipos de arquivo. A verificação precisa dos dispositivos que você usa.',
    }
    if section not in manual:
        raise ValueError('Etapa desconhecida.')
    return dict(state='manual', text=manual[section])
