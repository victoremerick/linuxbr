"""Packaging rules for private credential stores in new-account templates."""
from pathlib import Path

STORE_PATHS = ('etc/skel/.local/share/keyrings', 'etc/skel/.local/share/kwalletd')


def reject_seeded_credentials(root):
    root = Path(root).resolve()
    for relative in STORE_PATHS:
        path = root / relative
        if (not path.resolve().is_relative_to(root) or path.is_symlink()
                or (path.exists() and (not path.is_dir() or any(path.iterdir())))):
            raise ValueError('O pacote contém um cofre de usuário pré-criado ou indireto: '+relative)
