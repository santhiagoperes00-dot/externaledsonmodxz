# Python / app.py / Windows x64 Python 3.12 / BlueStacks Nougat32 Free Fire 1.132.1
import ctypes
from ctypes import wintypes as W
import colorsys
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
import sys
import traceback
from tkinter import ttk, colorchooser, filedialog
from reader import Memory, project
from discovery import discover

U = ctypes.WinDLL('user32', use_last_error=True)
CB = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
U.GetForegroundWindow.restype = W.HWND
U.GetParent.argtypes = [W.HWND]; U.GetParent.restype = W.HWND
U.GetWindowLongW.argtypes = [W.HWND, ctypes.c_int]
U.SetWindowLongW.argtypes = [W.HWND, ctypes.c_int, ctypes.c_long]
U.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
U.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
U.ClientToScreen.argtypes = [W.HWND, ctypes.POINTER(W.POINT)]
U.IsWindowVisible.argtypes = [W.HWND]
U.IsIconic.argtypes = [W.HWND]
U.EnumChildWindows.argtypes = [W.HWND, CB, W.LPARAM]
U.GetAsyncKeyState.argtypes = [ctypes.c_int]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class INPUTUNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('padding', ctypes.c_byte * (32 if ctypes.sizeof(ctypes.c_void_p)==8 else 24))]
class INPUT(ctypes.Structure):
    _fields_ = [('type', W.DWORD), ('data', INPUTUNION)]
U.SendInput.argtypes = [W.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

def window_target(window_title='BlueStacks App Player'):
    found = []
    def top(h, _):
        title = ctypes.create_unicode_buffer(256)
        U.GetWindowTextW(h, title, 256)
        if window_title in title.value and U.IsWindowVisible(h):
            found.append(h)
        return True
    U.EnumWindows(CB(top), 0)
    matches=[]
    for parent in found:
        children = []
        def child(h, _):
            title = ctypes.create_unicode_buffer(256)
            U.GetWindowTextW(h, title, 256)
            if title.value == 'HD-Player':
                r=W.RECT();U.GetClientRect(h,ctypes.byref(r))
                children.append((r.right*r.bottom,h))
            return True
        U.EnumChildWindows(parent, CB(child), 0)
        if children:
            h=max(children)[1]
            r=W.RECT();p=W.POINT(0,0)
            U.GetClientRect(h,ctypes.byref(r));U.ClientToScreen(h,ctypes.byref(p))
            matches.append((parent,(p.x,p.y,r.right,r.bottom)))
    return matches[0] if len(matches)==1 else (None,None)


class App:
    def __init__(self,auto_connect=True):
        try: U.SetProcessDPIAware()
        except Exception: pass
        self.root=tk.Tk();self.root.title('Edson Modz • Free Fire')
        self.root.geometry('960x750');self.root.minsize(920,720)
        self.bg='#0b101b';self.panel='#131c2c';self.accent='#6e8cff';self.color='#54e4cb'
        self.root.configure(bg=self.bg)
        self.events=queue.Queue();self.stop=threading.Event();self.worker=None
        self.snapshot=None;self.last_frame=0;self.last_geometry=None;self.phase=0
        self.closing=False;self.window_title='BlueStacks App Player';self.detecting=False
        self.path=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'EdsonModz'
        self.path.mkdir(parents=True,exist_ok=True)
        try:self.settings=json.loads((self.path/'settings.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):self.settings={}
        self.root.report_callback_exception=lambda *exc:self.note('Erro de interface: '+''.join(traceback.format_exception(*exc)))
        self.vars={}
        style=ttk.Style();style.theme_use('clam')
        style.configure('TNotebook',background=self.bg,borderwidth=0)
        style.configure('TNotebook.Tab',background=self.panel,foreground='#b6c3dc',padding=(20,12))
        style.map('TNotebook.Tab',background=[('selected','#263858')],foreground=[('selected','white')])
        self.build()
        self.overlay=tk.Toplevel(self.root);self.overlay.withdraw();self.overlay.overrideredirect(True)
        self.overlay.configure(bg='#010203');self.overlay.attributes('-transparentcolor','#010203')
        self.overlay.attributes('-topmost',True)
        self.canvas=tk.Canvas(self.overlay,bg='#010203',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.overlay.update_idletasks()
        hwnd=U.GetParent(self.overlay.winfo_id()) or self.overlay.winfo_id()
        U.SetWindowLongW(hwnd,-20,U.GetWindowLongW(hwnd,-20)|0x20|0x80000|0x08000000)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.after(33,self.tick)
        if auto_connect:self.root.after(450,self.auto_connect)

    def label(self,parent,text,size=11,color='#c4cee1',**pack):
        w=tk.Label(parent,text=text,font=('Segoe UI',size),bg=parent['bg'],fg=color,anchor='w')
        w.pack(**pack);return w

    def build(self):
        header=tk.Frame(self.root,bg=self.bg);header.pack(fill='x',padx=28,pady=(24,12))
        self.label(header,'EDSON  MODZ',25,'#ffffff',side='left')
        self.badge=self.label(header,'ARM32  /  1.132.1',11,self.color,side='right')
        self.line=tk.Canvas(self.root,height=3,bg='#1d2940',highlightthickness=0);self.line.pack(fill='x',padx=28)
        body=tk.Frame(self.root,bg=self.bg);body.pack(fill='both',expand=True,padx=28,pady=20)
        left=tk.Frame(body,bg=self.panel,width=254);left.pack(side='left',fill='y',padx=(0,20));left.pack_propagate(False)
        self.label(left,'CONEXÃO',11,self.color,padx=18,pady=(20,10),fill='x')
        self.label(left,'ADB do BlueStacks',10,padx=18,fill='x')
        self.adb=tk.StringVar(value=self.settings.get('adb',''))
        tk.Entry(left,textvariable=self.adb,bg='#0b101b',fg='white',insertbackground='white',relief='flat').pack(fill='x',padx=18,pady=8)
        tk.Button(left,text='Escolher HD-Adb.exe',command=self.browse,bg='#263858',fg='white',relief='flat').pack(fill='x',padx=18)
        self.serial=tk.StringVar(value=self.settings.get('serial','127.0.0.1:5555'))
        self.label(left,'Endereço da instância',10,padx=18,pady=(18,0),fill='x')
        tk.Entry(left,textvariable=self.serial,bg='#0b101b',fg='white',insertbackground='white',relief='flat').pack(fill='x',padx=18,pady=8)
        self.connect_button=tk.Button(left,text='CONECTAR',command=self.connect,bg=self.accent,fg='white',relief='flat',font=('Segoe UI',11,'bold'),pady=10)
        self.connect_button.pack(fill='x',padx=18,pady=12)
        tk.Button(left,text='Desconectar',command=self.disconnect,bg='#263858',fg='white',relief='flat').pack(fill='x',padx=18)
        tk.Button(left,text='DETECTAR NOVAMENTE',command=self.auto_connect,bg='#263858',fg='white',relief='flat').pack(fill='x',padx=18,pady=8)
        self.stats=self.label(left,'Sem leitura ativa',11,padx=18,pady=20,fill='x')
        self.label(left,'Mira: segure o botão direito\nPausa geral: F8\n\nFoque a janela do jogo para\nmostrar o overlay e usar a mira.',10,padx=18,pady=10,fill='x')
        book=ttk.Notebook(body);book.pack(side='left',fill='both',expand=True)
        esp=tk.Frame(book,bg=self.bg);aim=tk.Frame(book,bg=self.bg);info=tk.Frame(book,bg=self.bg)
        book.add(esp,text='ESP');book.add(aim,text='MIRA');book.add(info,text='STATUS')
        self.check(esp,'esp','Ativar ESP',False)
        self.check(esp,'boxes','Caixas',True);self.check(esp,'lines','Linhas até os alvos',False)
        self.check(esp,'distance','Exibir distância',True);self.check(esp,'friends','Mostrar aliados',False)
        self.check(esp,'rainbow','Cores animadas',False)
        tk.Button(esp,text='Selecionar cor',command=self.pick_color,bg='#263858',fg='white',relief='flat').pack(anchor='w',padx=18,pady=10)
        self.slider(esp,'range','Distância máxima (m)',10,500,200)
        self.check(aim,'aim','Ativar aimbot por movimento do mouse',False)
        self.check(aim,'fovcircle','Mostrar círculo de FOV',True)
        self.check(aim,'visible','Exigir flag de visibilidade',True)
        self.slider(aim,'fov','Raio de FOV (pixels)',20,500,130)
        self.slider(aim,'smooth','Suavização',2,30,12)
        self.label(aim,'Mira experimental: depende do modo de captura\ndo mouse do BlueStacks. Não dispara automaticamente.\nA flag de visibilidade ainda não foi validada.',10,padx=18,pady=18,fill='x')
        self.log=tk.Text(info,bg=self.panel,fg='#bdcce5',font=('Consolas',10),relief='flat',wrap='word',state='disabled')
        self.log.pack(fill='both',expand=True,padx=10,pady=16)
        self.status=tk.StringVar(value='Detectando BlueStacks • ESP e mira começam desligados')
        tk.Label(self.root,textvariable=self.status,bg=self.panel,fg='#bdcce5',font=('Segoe UI',10),anchor='w',padx=28,pady=12).pack(fill='x',side='bottom')

    def check(self,frame,key,text,default):
        v=tk.BooleanVar(value=default);self.vars[key]=v
        tk.Checkbutton(frame,text=text,variable=v,bg=self.bg,fg='#dae3f5',selectcolor='#263858',activebackground=self.bg,activeforeground='white',font=('Segoe UI',11),anchor='w').pack(fill='x',padx=16,pady=(12,0))

    def slider(self,frame,key,title,lo,hi,default):
        self.label(frame,title,10,padx=18,pady=(14,0),fill='x')
        v=tk.DoubleVar(value=default);self.vars[key]=v
        tk.Scale(frame,variable=v,from_=lo,to=hi,orient='horizontal',bg=self.bg,fg='#c4cee1',troughcolor=self.panel,highlightthickness=0,activebackground=self.accent,length=360).pack(fill='x',padx=18)

    def browse(self):
        path=filedialog.askopenfilename(filetypes=[('ADB executable','*.exe')])
        if path:self.adb.set(path)

    def pick_color(self):
        color=colorchooser.askcolor(self.color,parent=self.root)[1]
        if color:self.color=color

    def note(self,text):
        self.log.configure(state='normal');self.log.insert('end',time.strftime('%H:%M:%S')+'  '+text+'\n');self.log.see('end');self.log.configure(state='disabled')
        with (self.path/'session.log').open('a',encoding='utf-8') as f:f.write(text+'\n')

    def auto_connect(self):
        if self.closing or self.detecting or (self.worker and self.worker.is_alive()):return
        self.detecting=True;self.connect_button.configure(state='disabled')
        self.status.set('Procurando uma instância do BlueStacks com Free Fire…')
        preferred,saved=self.adb.get(),self.settings.get('serial','')
        def search():
            try:self.events.put(('discovered',discover(preferred,saved)))
            except Exception as e:self.events.put(('discovery_error',str(e)))
        threading.Thread(target=search,daemon=True).start()

    def connect(self):
        if self.closing or self.detecting or (self.worker and self.worker.is_alive()):return
        if not Path(self.adb.get()).is_file():self.auto_connect();return
        self.stop.clear();self.connect_button.configure(state='disabled');self.status.set('Conectando e validando a memória…')
        adb,serial=self.adb.get(),self.serial.get()
        self.settings.update(adb=adb,serial=serial)
        (self.path/'settings.json').write_text(json.dumps(self.settings),encoding='utf-8')
        def work():
            memory=None;last_error='';failures=0
            try:
                while not self.stop.is_set():
                    try:
                        if memory is None:
                            memory=Memory(adb,serial);memory.connect()
                            self.events.put(('log',f'PID {memory.pid} • leitura ELF confirmada'))
                        snap=memory.snapshot();self.events.put(('frame',snap))
                        failures=0;last_error='';self.stop.wait(0.02)
                    except Exception as e:
                        message=str(e)
                        if message!=last_error:self.events.put(('error',message));last_error=message
                        failures+=1
                        if failures>=3 or not memory or not memory.sock:
                            if memory:memory.close()
                            memory=None;failures=0
                        if 'Biblioteca diferente' in message or 'não concedeu root' in message:break
                        self.stop.wait(3)
            finally:
                if memory:memory.close()
                self.events.put(('done',None))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()

    def disconnect(self):
        self.stop.set();self.vars['aim'].set(False);self.snapshot=None;self.overlay.withdraw()

    def tick(self):
        if self.closing:return
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='discovered':
                    self.detecting=False
                    adb,serial,title=value;self.adb.set(adb);self.serial.set(serial);self.window_title=title
                    self.note('Instância detectada: '+serial+' • '+title);self.connect()
                elif kind=='discovery_error':
                    self.detecting=False;self.connect_button.configure(state='normal');self.status.set(value);self.note(value)
                elif kind=='frame':
                    self.snapshot=value
                    self.stats.configure(text=f"{len(value['entities'])} entidades\n{value['elapsed']*1000:.0f} ms por leitura")
                    self.status.set('Conectado • foque o jogo para mostrar o overlay • F8 pausa')
                elif kind=='log':self.note(value)
                elif kind=='error':self.note(value);self.status.set(value);self.snapshot=None;self.vars['aim'].set(False)
                elif kind=='done':self.connect_button.configure(state='normal')
        except queue.Empty:pass
        self.phase=(self.phase+0.008)%1
        self.line.delete('all');width=max(self.line.winfo_width(),1)
        x=self.phase*(width+150)-150;self.line.create_line(x,1,x+150,1,fill=self.accent,width=3)
        if U.GetAsyncKeyState(0x77)&1:
            self.vars['esp'].set(False);self.vars['aim'].set(False);self.note('F8: ESP e mira desativados')
        self.draw()
        self.root.after(33,self.tick)

    def draw(self):
        s=self.snapshot;parent,rect=window_target(self.window_title)
        if self.stop.is_set() or not s or not parent or U.IsIconic(parent) or U.GetForegroundWindow()!=parent or time.monotonic()-s['timestamp']>0.5:
            self.overlay.withdraw();return
        x,y,w,h=rect
        if w<100 or h<100:return
        if rect!=self.last_geometry:
            self.overlay.geometry(f'{w}x{h}{x:+d}{y:+d}');self.last_geometry=rect
        self.overlay.deiconify();self.canvas.delete('all')
        color=self.color
        if self.vars['rainbow'].get():color='#%02x%02x%02x'%tuple(int(v*255) for v in colorsys.hsv_to_rgb(self.phase,0.65,1))
        fov=self.vars['fov'].get();cx,cy=w/2,h/2
        if self.vars['aim'].get() and self.vars['fovcircle'].get():self.canvas.create_oval(cx-fov,cy-fov,cx+fov,cy+fov,outline=color)
        targets=[];drawn=0
        for e in s['entities']:
            if e['distance']>self.vars['range'].get() or (e['teammate'] and not self.vars['friends'].get()):continue
            head=project(e['head'],s['matrix'],w,h);foot=project(e['foot'],s['matrix'],w,h)
            if not head or not foot:continue
            hx,hy=head;fx,fy=foot
            if not (0<=hx<=w and 0<=hy<=h):continue
            height=abs(fy-hy)
            if not 2<height<h*2:continue
            drawn+=1
            if self.vars['esp'].get():
                bw=height*0.44
                if self.vars['boxes'].get():self.canvas.create_rectangle(hx-bw/2,hy-5,hx+bw/2,fy+3,outline=color,width=2)
                if self.vars['lines'].get():self.canvas.create_line(cx,h,hx,fy,fill=color)
                if self.vars['distance'].get():self.canvas.create_text(hx,hy-16,text=f"{e['distance']:.0f} m",fill=color,font=('Segoe UI',10,'bold'))
            delta=math.hypot(hx-cx,hy-cy)
            if not e['teammate'] and delta<fov and (e['visible'] or not self.vars['visible'].get()):targets.append((delta,hx-cx,hy-cy))
        self.stats.configure(text=f"{len(s['entities'])} entidades\n{drawn} na tela\n{s['elapsed']*1000:.0f} ms por leitura")
        self.status.set('Conectado • F8 pausa • mira somente com botão direito pressionado')
        if self.vars['aim'].get() and targets and U.GetAsyncKeyState(0x02)&0x8000 and s['timestamp']!=self.last_frame:
            _,dx,dy=min(targets);smooth=self.vars['smooth'].get()
            dx=int(max(-35,min(35,dx/smooth)));dy=int(max(-35,min(35,dy/smooth)))
            packet=INPUT(type=0,data=INPUTUNION(mi=MOUSEINPUT(dx,dy,0,1,0,0)))
            if not U.SendInput(1,ctypes.byref(packet),ctypes.sizeof(packet)):
                self.vars['aim'].set(False);self.note('Windows recusou SendInput; mira desativada')
            self.last_frame=s['timestamp']

    def close(self):
        if self.closing:return
        self.closing=True
        self.disconnect()
        def wait():
            if self.worker and self.worker.is_alive():self.root.after(100,wait)
            else:self.root.destroy()
        wait()

if __name__=='__main__':
    application=App()
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        destination=Path(sys.argv[2])
        def finish_test():
            s=application.snapshot
            result={'window_created':True,'memory_connected':bool(s),
                    'entities':len(s['entities']) if s else 0,
                    'elapsed_ms':round(s['elapsed']*1000,2) if s else None,
                    'aim_enabled':application.vars['aim'].get()}
            destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
            application.close()
        application.root.after(16000,finish_test)
    application.root.mainloop()
