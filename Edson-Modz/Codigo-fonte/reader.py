# Python / reader.py / Python 3.12 Windows / Free Fire 1.132.1 ARM32
import base64
import math
import queue
import re
import struct
import subprocess
import threading
import time
import socket
import secrets
import pathlib
import sys

CREATE_NO_WINDOW = 0x08000000


class Memory:
    def __init__(self, adb, serial):
        self.adb, self.serial = adb, serial
        self.proc = None
        self.pages = {}
        self.names = {}
        self.sock = None
        self.port = None
        self.remote = None

    def command(self, *args):
        p = subprocess.run([self.adb, '-s', self.serial, *args], capture_output=True,
                           timeout=12, creationflags=CREATE_NO_WINDOW)
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout).decode(errors='replace').strip())
        return p.stdout.decode(errors='replace').strip()

    def connect(self):
        if not re.fullmatch(r'[\w.:-]+', self.serial):
            raise ValueError('Endereço ADB inválido')
        subprocess.run([self.adb, 'connect', self.serial], capture_output=True,
                       timeout=10, creationflags=CREATE_NO_WINDOW)
        uid = self.command('shell', 'su -c id')
        if 'uid=0(' not in uid:
            raise RuntimeError('O comando su não concedeu root')
        pid = self.command('shell', 'su -c "pidof com.dts.freefireth"').split()
        if not pid or not pid[0].isdigit():
            raise RuntimeError('Abra o Free Fire e entre no treinamento')
        self.pid = int(pid[0])
        maps = self.command('shell', f'su -c "cat /proc/{self.pid}/maps"')
        self.ranges = []
        self.base = None
        for line in maps.splitlines():
            parts = line.split()
            lo, hi = [int(v, 16) for v in parts[0].split('-')]
            if parts[1].startswith('r'):
                self.ranges.append((lo, hi))
            if 'libil2cpp.so' in line and int(parts[2], 16) == 0:
                self.base = lo
                library_path = parts[-1]
        if self.base is None:
            raise RuntimeError('libil2cpp.so ainda não está carregada')
        if not re.fullmatch(r'/[\w./-]+', library_path):
            raise RuntimeError('Caminho de biblioteca inesperado')
        digest = self.command('shell', f'su -c "sha256sum {library_path}"').split()[0]
        if digest != '11fbddd1d4c65646522fe092b391ed416b0830a16017e89b2c6e190f9df83651':
            raise RuntimeError('Biblioteca diferente da versão validada; conexão interrompida')
        identity = 'edson_' + secrets.token_hex(12)
        token = secrets.token_hex(32)
        binary = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).parent)) / 'edson-reader'
        self.remote = '/data/local/tmp/' + identity
        self.command('push', str(binary), self.remote)
        self.command('shell', f'chmod 700 {self.remote}')
        self.proc = subprocess.Popen([self.adb, '-s', self.serial, 'shell',
                                     f'su -c "{self.remote} {self.pid} {identity} {token}"'],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            self.port = reserve.getsockname()[1]
        self.command('forward', f'tcp:{self.port}', f'localabstract:{identity}')
        for attempt in range(30):
            try:
                self.sock = socket.create_connection(('127.0.0.1', self.port), timeout=2)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.sock.sendall(token.encode())
                if self.receive(4) != b'EDM1':
                    raise RuntimeError('Identificação do leitor inválida')
                break
            except (OSError, RuntimeError):
                if self.sock:
                    self.sock.close()
                    self.sock = None
                if attempt == 29:
                    raise RuntimeError('Leitor temporário não iniciou; confira root e ABI x86')
                time.sleep(0.1)
        self.command('shell', f'rm {self.remote}')
        self.remote = None
        if self.raw(self.base, 4) != b'\x7fELF':
            raise RuntimeError('Falha na leitura real da memória ELF')

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.port:
            try:
                self.command('forward', '--remove', f'tcp:{self.port}')
            except Exception:
                pass
            self.port = None
        if self.remote:
            try:
                self.command('shell', f'rm {self.remote}')
            except Exception:
                pass
            self.remote = None

    def receive(self, n):
        data = bytearray()
        while len(data) < n:
            part = self.sock.recv(n-len(data))
            if not part:
                raise RuntimeError('Leitor de memória desconectado')
            data.extend(part)
        return bytes(data)

    def raw(self, address, size):
        if size < 1 or size > 262144 or not any(a <= address and address + size <= b for a, b in self.ranges):
            raise ValueError(f'Endereço fora das regiões legíveis: {address:#x}')
        self.sock.sendall(struct.pack('<II', address, size))
        got = struct.unpack('<i', self.receive(4))[0]
        if got < 0:
            raise RuntimeError(f'Leitura negada em {address:#x}, errno {-got}')
        data = self.receive(got)
        if got != size:
            raise RuntimeError(f'Leitura incompleta em {address:#x}: {got}/{size}')
        return data

    def read(self, a, n):
        page = a & ~4095
        if a + n <= page + 4096 and any(lo <= page and page + 4096 <= hi for lo, hi in self.ranges):
            if page not in self.pages:
                self.pages[page] = self.raw(page, 4096)
            return self.pages[page][a-page:a-page+n]
        return self.raw(a, n)

    def u32(self, a):
        return struct.unpack('<I', self.read(a, 4))[0]

    def prefetch(self, addresses):
        pages = sorted({a & ~4095 for a in addresses if a})
        pages = [p for p in pages if p not in self.pages and any(lo <= p and p+4096 <= hi for lo,hi in self.ranges)]
        if not pages:
            return
        self.sock.sendall(b''.join(struct.pack('<II',p,4096) for p in pages))
        for p in pages:
            n=struct.unpack('<i',self.receive(4))[0]
            data=self.receive(n) if n>0 else b''
            if n==4096:self.pages[p]=data

    def prepare_players(self, players):
        self.prefetch([p+o for p in players for o in (0,0x50,0x49c,0x4b0,0x504)])
        bones=[]
        for p in players:
            try: bones.extend([self.u32(p+0x49c),self.u32(p+0x4b0)])
            except (ValueError,RuntimeError):pass
        for offset in (8,8):
            self.prefetch([b+offset for b in bones if b])
            next_bones=[]
            for b in bones:
                try:next_bones.append(self.u32(b+offset))
                except (ValueError,RuntimeError):pass
            bones=next_bones
        self.prefetch([b+0x20 for b in bones if b])
        datasets=[]
        for b in bones:
            try:datasets.append(self.u32(b+0x20))
            except (ValueError,RuntimeError):pass
        self.prefetch([d+0x18 for d in datasets if d])
        pages=[]
        for d in set(datasets):
            try:
                count=self.u32(d+0x10)
                arr,parents=struct.unpack('<II',self.read(d+0x18,8))
                if 0<count<512:
                    pages.extend(range(arr&~4095,(arr+count*48+4095)&~4095,4096))
                    pages.extend(range(parents&~4095,(parents+count*4+4095)&~4095,4096))
            except (ValueError,RuntimeError):pass
        self.prefetch(pages)

    def classname(self, obj):
        cls = self.u32(obj)
        if cls not in self.names:
            p = self.u32(cls + 8)
            self.names[cls] = self.read(p, 96).split(b'\0')[0].decode(errors='replace')
        return self.names[cls]

    def position(self, managed, bone=False):
        if bone:
            managed = self.u32(managed + 8)
        native = self.u32(managed + 8)
        data, index = struct.unpack('<II', self.read(native + 0x20, 8))
        if index > 4096:
            raise ValueError('Índice de transformação inválido')
        array, parents = struct.unpack('<II', self.read(data + 0x18, 8))
        row = struct.unpack('<12f', self.read(array + index * 48, 48))
        pos = row[:3]
        visited = set()
        while True:
            parent = struct.unpack('<i', self.read(parents + index * 4, 4))[0]
            if parent == -1:
                break
            if parent < 0 or parent > 4096 or parent in visited or len(visited) > 100:
                raise ValueError('Hierarquia de transformação inválida')
            visited.add(parent)
            row = struct.unpack('<12f', self.read(array + parent * 48, 48))
            v = tuple(pos[i] * row[8+i] for i in range(3))
            qx, qy, qz, qw = row[4:8]
            tx, ty, tz = (2*(qy*v[2]-qz*v[1]), 2*(qz*v[0]-qx*v[2]), 2*(qx*v[1]-qy*v[0]))
            pos = (v[0]+qw*tx+qy*tz-qz*ty+row[0],
                   v[1]+qw*ty+qz*tx-qx*tz+row[1],
                   v[2]+qw*tz+qx*ty-qy*tx+row[2])
            index = parent
        if not all(math.isfinite(x) and abs(x) < 100000 for x in pos):
            raise ValueError('Posição não finita')
        return pos

    def snapshot(self):
        self.pages.clear()
        start = time.monotonic()
        slot = self.u32(self.base + 0xA342EFC)
        klass = self.u32(slot)
        statics = self.u32(klass + 0x5c)
        facade = self.u32(statics)
        match = self.u32(facade + 0x50)
        local = self.u32(match + 0x94)
        if self.classname(local) != 'PlayerNetwork':
            raise ValueError('Jogador local não validado; entre no treinamento')
        cam = self.u32(self.u32(local + 0x494) + 0x18)
        camera_native = self.u32(cam + 8)
        matrix = struct.unpack('<16f', self.read(camera_native + 0xe8, 64))
        if not all(math.isfinite(v) for v in matrix) or sum(abs(v) for v in matrix[:12]) < 0.1:
            raise ValueError('Matriz de câmera inválida')
        origin = self.position(self.u32(local + 0x28c))
        entities = []
        seen = set()
        # 0xC8 and the 40-byte entries were observed in the running training match.
        for dict_offset in (0x68, 0xc8):
            dictionary = self.u32(match + dict_offset)
            if self.classname(dictionary) != 'Dictionary`2':
                continue
            count = self.u32(dictionary + 0x10)
            if count == 0:
                continue
            if count > 256:
                raise ValueError('Quantidade inesperada de entidades')
            entries = self.u32(dictionary + 0xc)
            capacity = self.u32(entries + 0xc)
            if count > capacity or capacity > 4096:
                raise ValueError('Capacidade de entidades inválida')
            data = self.read(entries + 16, count * 40)
            candidates=[]
            for i in range(count):
                h=struct.unpack_from('<i',data,i*40)[0]
                p=struct.unpack_from('<I',data,i*40+32)[0]
                if h>=0 and p and p!=local:candidates.append(p)
            self.prepare_players(candidates)
            for i in range(count):
                h = struct.unpack_from('<i', data, i*40)[0]
                player = struct.unpack_from('<I', data, i*40+32)[0]
                if h < 0 or not player or player == local or player in seen:
                    continue
                seen.add(player)
                try:
                    kind = self.classname(player)
                    if 'Player' not in kind:
                        continue
                    if self.read(player + 0x50, 1)[0]:
                        continue
                    head = self.position(self.u32(player + 0x49c), bone=True)
                    foot = self.position(self.u32(player + 0x4b0), bone=True)
                    distance = math.dist(origin, head)
                    if not 0.1 < distance < 2000:
                        continue
                    # Fail closed for aim when team/visibility cannot be read.
                    teammate, visible = True, False
                    try:
                        avatar = self.u32(self.u32(player + 0x504) + 0xa8)
                        visible = bool(self.read(avatar + 0x95, 1)[0])
                        teammate = bool(self.read(self.u32(avatar + 0x14) + 0x59, 1)[0])
                    except (ValueError, RuntimeError):
                        pass
                    entities.append(dict(address=hex(player), head=head, foot=foot,
                                         distance=distance, visible=visible, teammate=teammate))
                except (ValueError, RuntimeError, struct.error):
                    continue
        return dict(entities=entities, matrix=matrix, origin=origin, local=hex(local),
                    elapsed=time.monotonic()-start, timestamp=time.monotonic())


def project(pos, matrix, width, height):
    x, y, z = pos
    w = x*matrix[3] + y*matrix[7] + z*matrix[11] + matrix[15]
    if not math.isfinite(w) or w <= 0.05:
        return None
    sx = (x*matrix[0]+y*matrix[4]+z*matrix[8]+matrix[12])/w
    sy = (x*matrix[1]+y*matrix[5]+z*matrix[9]+matrix[13])/w
    return ((sx+1)*width/2, (1-sy)*height/2)
