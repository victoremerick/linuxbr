#!/usr/bin/env python3
"""Check Brazilian ABNT2 symbols and composition through the desktop XKB library."""
import argparse
import ctypes as C
import json
from pathlib import Path
import shlex

parser=argparse.ArgumentParser()
parser.add_argument('--model')
parser.add_argument('--output',type=Path)
args=parser.parse_args()
values={}
for line in Path('/etc/default/keyboard').read_text().splitlines():
    key,separator,value=line.partition('=')
    if separator and key in ('XKBMODEL','XKBLAYOUT','XKBVARIANT','XKBOPTIONS'):
        values[key]=shlex.split(value)[0] if shlex.split(value) else ''
model=args.model or values['XKBMODEL']
assert values['XKBLAYOUT']=='br',values
registry=Path('/usr/share/X11/xkb/rules/base.lst').read_text()
assert any(line.split() and line.split()[0]==model for line in registry.splitlines()),'Modelo ausente no registro XKB: '+model


class Names(C.Structure):
    _fields_=[(key,C.c_char_p) for key in ('rules','model','layout','variant','options')]


lib=C.CDLL('libxkbcommon.so.0')
def bind(name,restype,*argtypes):
    function=getattr(lib,name);function.restype=restype;function.argtypes=list(argtypes);return function

context_new=bind('xkb_context_new',C.c_void_p,C.c_int)
keymap_new=bind('xkb_keymap_new_from_names',C.c_void_p,C.c_void_p,C.POINTER(Names),C.c_int)
key_by_name=bind('xkb_keymap_key_by_name',C.c_uint32,C.c_void_p,C.c_char_p)
symbols=bind('xkb_keymap_key_get_syms_by_level',C.c_int,C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.POINTER(C.c_uint32)))
symbol_name=bind('xkb_keysym_get_name',C.c_int,C.c_uint32,C.c_char_p,C.c_size_t)
symbol_from_name=bind('xkb_keysym_from_name',C.c_uint32,C.c_char_p,C.c_int)
compose_table_new=bind('xkb_compose_table_new_from_locale',C.c_void_p,C.c_void_p,C.c_char_p,C.c_int)
compose_new=bind('xkb_compose_state_new',C.c_void_p,C.c_void_p,C.c_int)
compose_reset=bind('xkb_compose_state_reset',None,C.c_void_p)
compose_feed=bind('xkb_compose_state_feed',C.c_int,C.c_void_p,C.c_uint32)
compose_utf8=bind('xkb_compose_state_get_utf8',C.c_int,C.c_void_p,C.c_char_p,C.c_size_t)
context=context_new(0);assert context
names=Names(b'evdev',model.encode(),b'br',b'',b'')
keymap=keymap_new(context,C.byref(names),0);assert keymap
table=compose_table_new(context,b'pt_BR.UTF-8',0);assert table
state=compose_new(table,0);assert state
checks={}
try:
    for key,level,expected in [('AC10',0,'ccedilla'),('AC10',1,'Ccedilla'),
                               ('AD11',0,'dead_acute'),('AC11',0,'dead_tilde'),
                               ('AB11',0,'slash'),('AB11',1,'question'),
                               ('LSGT',0,'backslash'),('LSGT',1,'bar')]:
        output=C.POINTER(C.c_uint32)()
        count=symbols(keymap,key_by_name(keymap,key.encode()),0,level,C.byref(output));assert count==1
        buffer=C.create_string_buffer(80);symbol_name(output[0],buffer,len(buffer))
        actual=buffer.value.decode();assert actual==expected,(key,level,actual,expected)
        checks[key+':'+str(level)]=actual
    for dead,letter,expected in [('dead_acute','a','á'),('dead_tilde','a','ã'),('dead_circumflex','e','ê')]:
        compose_reset(state)
        for name in (dead,letter):compose_feed(state,symbol_from_name(name.encode(),0))
        buffer=C.create_string_buffer(80);compose_utf8(state,buffer,len(buffer))
        actual=buffer.value.decode();assert actual==expected,(dead,actual,expected)
        checks[dead+'+'+letter]=actual
    result={'status':'PASS','model':model,'layout':'br','abnt2_symbols':checks,'physical_keyboard_tested':False}
    if args.output:args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
finally:
    for name,pointer in [('xkb_compose_state_unref',state),('xkb_compose_table_unref',table),
                         ('xkb_keymap_unref',keymap),('xkb_context_unref',context)]:
        bind(name,None,C.c_void_p)(pointer)
