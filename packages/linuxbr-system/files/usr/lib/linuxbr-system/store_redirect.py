"""Compatibility entry point for existing desktop software links."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit,unquote


def search_term(value):
    if value.startswith('apt:'):return unquote(value.split(':',1)[1].lstrip('/')).split('?',1)[0]
    if value.startswith('appstream:'):
        parsed=urlsplit(value);return unquote(parsed.netloc+parsed.path).strip('/').removesuffix('.desktop')
    return value


def command(arguments):
    result=['/usr/bin/linuxbr-store']
    for option in ('--local-filename','--local-filename='):
        for index,value in enumerate(arguments):
            filename=(arguments[index+1] if index+1<len(arguments) else '') if value==option else value[len(option):] if option.endswith('=') and value.startswith(option) else ''
            if filename and Path(filename).is_file():return ['/usr/bin/linuxbr-install-package',filename]
    if '--update' in arguments or '--mode=update' in arguments or any(arguments[i:i+2]==['--mode','update'] for i in range(len(arguments))):return result+['--updates']
    if any('fwupd' in value for value in arguments):return result+['--firmware']
    for index,value in enumerate(arguments):
        if value in ('--search','--application') and index+1<len(arguments):return result+['--search',search_term(arguments[index+1])]
        if value.startswith(('--search=','--application=')):return result+['--search',search_term(value.split('=',1)[1])]
        if value.startswith(('apt:','appstream:')):return result+['--search',search_term(value)]
    return result


if __name__=='__main__':
    argv=command(sys.argv[1:]);os.execv(argv[0],argv)
