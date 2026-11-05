"""Search the configured package indexes without executing catalog commands."""
import re
import subprocess


def search(query, with_status=False):
    query=query.strip()
    if not 2<=len(query)<=100 or not any(c.isalnum() for c in query):return []
    rows=[];errors=[]
    try:
        result=subprocess.run(['/usr/bin/apt-cache','search','--names-only',re.escape(query)],capture_output=True,text=True,timeout=15)
        if result.returncode==0:
            for line in result.stdout.splitlines()[:80]:
                name,separator,description=line.partition(' - ')
                if separator and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*',name):
                    rows.append(dict(id='deb:'+name,repository_package=name,name=name,kind='linux',category='Fontes configuradas',description=description,source='Repositórios APT configurados',note='Pacote dos índices locais. Confira descrição, dependências e origem antes de instalar.',icon='package-x-generic'))
        else:errors.append('Não foi possível consultar os índices APT.')
    except FileNotFoundError:errors.append('APT indisponível nesta instalação.')
    except (OSError,subprocess.TimeoutExpired):errors.append('A consulta APT não terminou. Tente novamente.')
    try:
        result=subprocess.run(['/usr/bin/flatpak','search','--columns=application,name,description,remotes','--',query],capture_output=True,text=True,timeout=20)
        if result.returncode==0:
            for line in result.stdout.splitlines()[:80]:
                values=line.split('\t')
                if len(values)==4 and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}',values[0]):
                    rows.append(dict(id='flatpak:'+values[0],flatpak_id=values[0],name=values[1],kind='linux',category='Fontes configuradas',description=values[2],source='Flatpak · '+values[3],note='Escolha a fonte e o alcance antes de instalar.',icon=values[0]))
        else:errors.append('Não foi possível consultar as fontes Flatpak.')
    except FileNotFoundError:errors.append('Flatpak não está instalado; a consulta ficou limitada às outras fontes.')
    except (OSError,subprocess.TimeoutExpired):errors.append('A consulta Flatpak não terminou. Tente novamente.')
    return dict(rows=rows,errors=errors) if with_status else rows
