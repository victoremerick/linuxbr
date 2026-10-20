"""Bounded filesystem queries, isolated from the UI and session service."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def measure(path):
    stat = os.statvfs(path)
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bfree * stat.f_frsize
    available = stat.f_bavail * stat.f_frsize
    if not 0 <= available <= free <= total or not total:
        raise ValueError('Estatísticas indisponíveis')
    return dict(total=total, used=total-free, free=available, reserved=free-available)


def query(row):
    if not row.get('mounts') or row.get('url'):
        return None
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), row['mounts'][0]],
                                capture_output=True, text=True, timeout=2, check=True)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def enrich(rows):
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row, usage in zip(rows, pool.map(query, rows)):
            row['usage'] = usage
    return rows


if __name__ == '__main__':
    print(json.dumps(measure(sys.argv[1])))
