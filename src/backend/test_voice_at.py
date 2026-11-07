import ctypes, time
from ctypes import wintypes
k32 = ctypes.windll.kernel32

class COMSTAT(ctypes.Structure):
    _fields_ = [('fBitFields', wintypes.DWORD), ('cbInQue', wintypes.DWORD), ('cbOutQue', wintypes.DWORD)]

class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [('a', wintypes.DWORD), ('b', wintypes.DWORD), ('c', wintypes.DWORD), ('d', wintypes.DWORD), ('e', wintypes.DWORD)]

h = k32.CreateFileW('\\\\.\\COM7', 0xC0000000, 0, None, 3, 0, None)
if h in (-1, 0):
    print('Failed open COM7:', k32.GetLastError(), flush=True)
    exit()

to = COMMTIMEOUTS(0xFFFFFFFF, 0, 0, 0, 1000)
k32.SetCommTimeouts(h, ctypes.byref(to))

def query(cmd):
    w = wintypes.DWORD(0)
    data = (cmd + '\r\n').encode()
    k32.WriteFile(h, data, len(data), ctypes.byref(w), None)
    time.sleep(0.2)
    cs = COMSTAT()
    errs = wintypes.DWORD(0)
    k32.ClearCommError(h, ctypes.byref(errs), ctypes.byref(cs))
    if cs.cbInQue > 0:
        buf = ctypes.create_string_buffer(cs.cbInQue)
        r = wintypes.DWORD(0)
        k32.ReadFile(h, buf, cs.cbInQue, ctypes.byref(r), None)
        res = buf.raw[:r.value].decode(errors='replace').strip()
        print(f"[{cmd}] -> {repr(res)}", flush=True)
    else:
        print(f"[{cmd}] -> NO DATA", flush=True)

query('ATE0')
query('AT^CVOICE=?')
query('AT^CVOICE?')
query('AT^DDSETEX=?')
query('AT^DDSETEX?')
query('AT^DDSETEX=2')
query('AT+CLVL=?')
query('AT+CLVL?')
query('AT+CMUT=?')
query('AT^CPCM=?')
query('AT^CPCM?')
k32.CloseHandle(h)
