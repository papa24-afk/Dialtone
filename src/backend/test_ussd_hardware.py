import ctypes, time
from ctypes import wintypes
k32 = ctypes.windll.kernel32

class COMSTAT(ctypes.Structure):
    _fields_ = [('fBitFields', wintypes.DWORD), ('cbInQue', wintypes.DWORD), ('cbOutQue', wintypes.DWORD)]

class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [('a', wintypes.DWORD), ('b', wintypes.DWORD), ('c', wintypes.DWORD), ('d', wintypes.DWORD), ('e', wintypes.DWORD)]

h = k32.CreateFileW('\\\\.\\COM7', 0xC0000000, 0, None, 3, 0, None)
if h in (-1, 0):
    print(f'[-] Failed to open COM7: Error {k32.GetLastError()}', flush=True)
    exit(1)

to = COMMTIMEOUTS(0xFFFFFFFF, 0, 0, 0, 1000)
k32.SetCommTimeouts(h, ctypes.byref(to))

def write_cmd(cmd):
    w = wintypes.DWORD(0)
    data = (cmd + '\r\n').encode()
    print(f"[TX] >>> {cmd}", flush=True)
    k32.WriteFile(h, data, len(data), ctypes.byref(w), None)

def read_available(timeout_sec=5.0):
    start = time.time()
    buf = bytearray()
    cs = COMSTAT()
    errs = wintypes.DWORD(0)
    while (time.time() - start) < timeout_sec:
        k32.ClearCommError(h, ctypes.byref(errs), ctypes.byref(cs))
        if cs.cbInQue > 0:
            chunk = ctypes.create_string_buffer(cs.cbInQue)
            r = wintypes.DWORD(0)
            ok = k32.ReadFile(h, chunk, cs.cbInQue, ctypes.byref(r), None)
            if ok and r.value > 0:
                data = chunk.raw[:r.value]
                buf.extend(data)
                print(f"[RX CHUNK] {repr(data.decode(errors='replace'))}", flush=True)
                if b"+CUSD:" in buf and (buf.count(b'"') >= 2 or b"+CUSD: 2" in buf):
                    break
        time.sleep(0.05)
    return buf.decode(errors='replace')

# 1. Init
write_cmd('ATE0')
time.sleep(0.2)
read_available(0.5)

write_cmd('AT+CUSD=1')
time.sleep(0.2)
read_available(0.5)

# 2. Send USSD *124# (Balance check)
print("\n--- Testing USSD *124# ---", flush=True)
write_cmd('AT+CUSD=1,"*124#",15')
resp = read_available(8.0)
print(f"[FULL RESULT *124#]:\n{resp}\n", flush=True)

# 3. Send USSD *110# (Telecel Cash menu)
print("\n--- Testing USSD *110# ---", flush=True)
write_cmd('AT+CUSD=1,"*110#",15')
resp2 = read_available(8.0)
print(f"[FULL RESULT *110#]:\n{resp2}\n", flush=True)

# 4. If session active, reply with 1
if "+CUSD: 1" in resp2:
    print("\n--- Session active! Replying with option 1 ---", flush=True)
    write_cmd('AT+CUSD=1,"1",15')
    resp3 = read_available(8.0)
    print(f"[FULL RESULT REPLY 1]:\n{resp3}\n", flush=True)

# 5. Cancel session
write_cmd('AT+CUSD=2')
read_available(1.0)

k32.CloseHandle(h)
print("[+] Test completed cleanly.", flush=True)
