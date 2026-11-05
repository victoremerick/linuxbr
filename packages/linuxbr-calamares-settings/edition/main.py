"""Apply the edition after the filesystem and local accounts are installed."""
from pathlib import Path
import os
import libcalamares


def pretty_name():return 'Configurar a edição do Linux BR'


def run():
    selected=libcalamares.globalstorage.value('packagechooser_packagechooser')
    if selected not in ('desktop','server'):return ('Selecione uma edição válida.','Volte à página Edição e escolha Desktop ou Servidor.')
    root=Path(libcalamares.globalstorage.value('rootMountPoint')).resolve()
    if root==Path('/') or not os.path.ismount(root) or not (root/'etc/debian_version').is_file():
        return ('Destino de instalação inválido.','A edição só pode ser configurada no sistema de destino montado pelo instalador.')
    marker=root/'var/lib/linuxbr/installer-edition-authorized'
    if not marker.parent.resolve().is_relative_to(root) or marker.is_symlink():
        return ('Configuração de destino indireta.','A pasta reservada do instalador deve estar dentro do sistema de destino.')
    marker.parent.mkdir(parents=True,exist_ok=True);marker.write_text(selected+'\n');marker.chmod(0o600)
    try:
        result=libcalamares.utils.target_env_call(['/usr/bin/python3','/usr/lib/linuxbr-boot/install_edition.py',selected])
        if result:return ('Não foi possível configurar a edição.','Confira o registro do instalador e o plano de pacotes. Nenhum disco adicional foi selecionado por esta etapa.')
    except Exception as error:return ('Não foi possível configurar a edição.',str(error))
    finally:marker.unlink(missing_ok=True)
    return None
