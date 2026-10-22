# Python / discovery.py / Windows 64-bit / local BlueStacks ADB discovery
import os
from pathlib import Path
import re
import subprocess
import winreg


def profiles_from_text(text):
    values=dict(re.findall(r'^([^=\r\n]+)="([^"\r\n]*)"',text,re.M))
    result={}
    for key,value in values.items():
        m=re.fullmatch(r'bst\.instance\.([^.]+)\.adb_port',key)
        if m and value.isdigit() and 1<=int(value)<=65535:
            name=m.group(1)
            result[f'127.0.0.1:{int(value)}']=values.get(f'bst.instance.{name}.display_name','BlueStacks App Player')
    return result


def find_installation(preferred=''):
    bins=[];configs=[]
    if preferred:bins.append(Path(preferred))
    for env in ('ProgramFiles','ProgramFiles(x86)'):
        base=Path(os.environ.get(env,'C:/Program Files'))
        for folder in ('BlueStacks_nxt','BlueStacks','BlueStacks_msi5'):
            bins.append(base/folder/'HD-Adb.exe')
    for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
        for name in ('BlueStacks_nxt','BlueStacks','BlueStacks_msi5'):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,'SOFTWARE\\'+name,0,winreg.KEY_READ|view) as key:
                    for field in ('InstallDir','DataDir','UserDefinedDir'):
                        try:
                            value=Path(winreg.QueryValueEx(key,field)[0])
                            if field=='InstallDir':bins.append(value/'HD-Adb.exe')
                            else:configs.append(value/'bluestacks.conf')
                        except (OSError,TypeError):pass
            except OSError:pass
    for name in ('BlueStacks_nxt','BlueStacks','BlueStacks_msi5'):
        configs.append(Path(os.environ.get('ProgramData','C:/ProgramData'))/name/'bluestacks.conf')
    adb=next((str(p) for p in bins if p.is_file()),None)
    if not adb:raise RuntimeError('HD-Adb.exe não encontrado. Use Escolher HD-Adb.exe.')
    profiles={}
    for p in configs:
        try:profiles.update(profiles_from_text(p.read_text(encoding='utf-8')))
        except (OSError,UnicodeError):pass
    if not profiles:profiles['127.0.0.1:5555']='BlueStacks App Player'
    return adb,profiles


def discover(preferred='',saved_serial=''):
    adb,profiles=find_installation(preferred)
    active=[]
    for serial,title in profiles.items():
        try:
            subprocess.run([adb,'connect',serial],capture_output=True,timeout=3,creationflags=0x08000000)
            r=subprocess.run([adb,'-s',serial,'shell','pm path com.dts.freefireth'],
                             capture_output=True,timeout=3,creationflags=0x08000000)
            if r.returncode==0 and b'package:' in r.stdout:active.append((serial,title))
        except subprocess.TimeoutExpired:pass
    if not active:raise RuntimeError('Abra a instância com Free Fire e ADB ativado; clique DETECTAR NOVAMENTE.')
    if len(active)>1:
        selected=next((x for x in active if x[0]==saved_serial),None)
        if selected:return adb,*selected
        raise RuntimeError('Mais de uma instância ativa. Informe a porta desejada e clique CONECTAR.')
    return adb,*active[0]
