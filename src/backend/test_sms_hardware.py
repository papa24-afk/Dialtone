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

def write_raw(data_bytes):
    w = wintypes.DWORD(0)
    k32.WriteFile(h, data_bytes, len(data_bytes), ctypes.byref(w), None)

def write_cmd(cmd):
    print(f"[TX] >>> {cmd}", flush=True)
    write_raw((cmd + '\r\n').encode())

def read_until(pattern=None, timeout_sec=8.0):
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
                text = buf.decode(errors='replace')
                if pattern and pattern in text:
                    break
        time.sleep(0.05)
    return buf.decode(errors='replace')

# 1. Init
write_cmd('ATE0')
time.sleep(0.2)
read_until()

write_cmd('AT+CMGF=1')
time.sleep(0.2)
read_until()

# 2. Send SMS
phone_num = os.environ.get("TEST_PHONE_NUM", "0000000000")
test_msg = f"Hardware regression test {time.strftime('%H:%M:%S')}"
print(f"\n--- Testing SMS Submission to {phone_num} ---", flush=True)

write_cmd(f'AT+CMGS="{phone_num}"')
prompt = read_until('>', 4.0)
print(f"[PROMPT RESULT]: {repr(prompt)}", flush=True)

if '>' in prompt:
    print(f"[+] Prompt '>' received. Writing body: {test_msg}", flush=True)
    body_data = test_msg.encode('utf-8') + b'\x1a'
    write_raw(body_data)
    result = read_until('OK', 12.0)
    print(f"[SUBMISSION RESULT]:\n{result}", flush=True)
else:
    print("[-] Prompt not received. Sending ESC.", flush=True)
    write_raw(b'\x1b')

# 3. Check SIM stored messages (+CMGL="ALL")
print("\n--- Reading Stored SMS on SIM ---", flush=True)
write_cmd('AT+CPMS="SM","SM","SM"')
time.sleep(0.2)
read_until('OK', 2.0)

write_cmd('AT+CMGL="ALL"')
msgs = read_until('OK', 4.0)
print(f"[STORED MESSAGES RESULT]:\n{msgs}", flush=True)

k32.CloseHandle(h)
print("[+] SMS test completed cleanly.", flush=True)
