"""
Switchboard / CellularPC Backend Modem & Audio Bridge
Handles Huawei K4201 AT communication, incoming/outgoing calls, URCs, SMS, USSD,
SQLite persistence, and bi-directional 16-bit 8000Hz PCM voice audio routing via COM6.
"""

import sys
import os
import time
import json
import threading
import queue
import re
import math
import uuid
import ctypes
from ctypes import wintypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import subprocess

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# Local modules
from database import db, normalize_number
from audio_router import audio_router, diagnostics

k32 = ctypes.windll.kernel32
winmm = ctypes.windll.winmm

# 64-bit Windows ctypes function signatures
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]

k32.SetCommTimeouts.restype = wintypes.BOOL
k32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

k32.ClearCommError.restype = wintypes.BOOL
k32.ClearCommError.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p]

k32.ReadFile.restype = wintypes.BOOL
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]

k32.WriteFile.restype = wintypes.BOOL
k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]

k32.CloseHandle.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

def is_valid_handle(h):
    if not h or h == 0:
        return False
    if h == -1 or h == INVALID_HANDLE_VALUE or h == 0xFFFFFFFFFFFFFFFF or h == 0xFFFFFFFF:
        return False
    return True

# Windows SCSI Pass-Through for Huawei dongle mode-switching
class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ('Length', wintypes.USHORT),
        ('ScsiStatus', ctypes.c_ubyte),
        ('PathId', ctypes.c_ubyte),
        ('TargetId', ctypes.c_ubyte),
        ('Lun', ctypes.c_ubyte),
        ('CdbLength', ctypes.c_ubyte),
        ('SenseInfoLength', ctypes.c_ubyte),
        ('DataIn', ctypes.c_ubyte),
        ('DataTransferLength', wintypes.ULONG),
        ('TimeOutValue', wintypes.ULONG),
        ('DataBuffer', ctypes.c_void_p),
        ('SenseInfoOffset', wintypes.ULONG),
        ('Cdb', ctypes.c_ubyte * 16)
    ]

IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808

k32.DeviceIoControl.restype = wintypes.BOOL
k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]

k32.GetVolumeInformationW.restype = wintypes.BOOL
k32.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD]

def send_scsi_cdb(target_dev, cdb_bytes):
    if len(target_dev) == 1:
        target = f"\\\\.\\{target_dev}:"
    elif not target_dev.startswith("\\\\"):
        target = f"\\\\.\\{target_dev}"
    else:
        target = target_dev

    h = k32.CreateFileW(target, 0xC0000000, 3, None, 3, 0, None)
    if not is_valid_handle(h):
        h = k32.CreateFileW(target, 0x80000000, 3, None, 3, 0, None)
    if not is_valid_handle(h):
        return False
    
    spt = SCSI_PASS_THROUGH_DIRECT()
    spt.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    spt.CdbLength = min(len(cdb_bytes), 16)
    spt.DataIn = 0
    spt.DataTransferLength = 0
    spt.TimeOutValue = 3
    for i, b in enumerate(cdb_bytes[:16]):
        spt.Cdb[i] = b
        
    ret = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(
        h, IOCTL_SCSI_PASS_THROUGH_DIRECT,
        ctypes.byref(spt), ctypes.sizeof(spt),
        ctypes.byref(spt), ctypes.sizeof(spt),
        ctypes.byref(ret), None
    )
    err = k32.GetLastError()
    k32.CloseHandle(h)
    return bool(ok or err in (121, 1117))

def find_cdfs_drive():
    # 1. Check direct CdRom device handles
    for cr in [r"\\.\CdRom0", r"\\.\CdRom1"]:
        h = k32.CreateFileW(cr, 0x80000000, 3, None, 3, 0, None)
        if is_valid_handle(h):
            k32.CloseHandle(h)
            return cr, "CdRom Device"

    # 2. Check drive letters
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        dt = k32.GetDriveTypeW(root)
        if dt == 5:  # DRIVE_CDROM
            return letter, "Huawei Virtual CD-ROM"
            
        if os.path.exists(root):
            try:
                vol_buf = ctypes.create_unicode_buffer(261)
                fs_buf = ctypes.create_unicode_buffer(261)
                k32.GetVolumeInformationW(root, vol_buf, 261, None, None, None, fs_buf, 261)
                vol_name = vol_buf.value
                fs_name = fs_buf.value
                if "Vodafone" in vol_name or "CDFS" in fs_name or "Mobile" in vol_name or "HUAWEI" in vol_name.upper():
                    return letter, vol_name or "Huawei CD-ROM"
            except Exception:
                pass
    return None, None

def query_windows_mbn_status():
    try:
        res = subprocess.run(["netsh", "mbn", "show", "interfaces"], capture_output=True, text=True, timeout=2)
        out = res.stdout
        if "Model" in out or "Manufacturer" in out:
            model = "Huawei K4201"
            carrier = "Telecel Ghana"
            signal_pct = 70
            signal_dbm = -69
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Model"):
                    model = line.split(":", 1)[1].strip()
                elif line.startswith("Provider Name"):
                    carrier = line.split(":", 1)[1].strip()
                elif line.startswith("Signal"):
                    sig_str = line.split(":", 1)[1].strip().replace("%", "")
                    try:
                        signal_pct = int(sig_str)
                    except Exception:
                        pass
                elif "RSSI" in line and "(" in line:
                    try:
                        dbm_part = line.split("(")[1].split("dBm")[0].strip()
                        signal_dbm = int(dbm_part)
                    except Exception:
                        pass
            return {
                "present": True,
                "model": model,
                "carrier": carrier,
                "signal_pct": signal_pct,
                "signal_dbm": signal_dbm,
                "state": "Connected (Data Mode)"
            }
    except Exception:
        pass
    return None

WAVE_FORMAT_PCM = 1

class COMSTAT(ctypes.Structure):
    _fields_ = [
        ("fBitFields", wintypes.DWORD),
        ("cbInQue", wintypes.DWORD),
        ("cbOutQue", wintypes.DWORD)
    ]

class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", wintypes.DWORD),
        ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
        ("ReadTotalTimeoutConstant", wintypes.DWORD),
        ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
        ("WriteTotalTimeoutConstant", wintypes.DWORD)
    ]

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def decode_ussd_text(raw_text):
    if not raw_text:
        return ""
    cleaned = raw_text.strip()
    # Check if 16-bit hex UCS2 (e.g. 00480065006C006C006F)
    if len(cleaned) >= 4 and len(cleaned) % 4 == 0 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        try:
            return bytes.fromhex(cleaned).decode("utf-16-be")
        except Exception:
            pass
    return raw_text.replace("\\r", "").replace("\\n", "\n").strip()

def decode_sms_text(raw_text):
    if not raw_text:
        return ""
    cleaned = raw_text.strip()
    if len(cleaned) >= 4 and len(cleaned) % 4 == 0 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        try:
            return bytes.fromhex(cleaned).decode("utf-16-be")
        except Exception:
            pass
    return raw_text.strip()

def scan_cellular_modem_ports():
    """
    Dynamically scans Windows serial ports to identify:
    1. AT Command Port (used for calls, SMS, USSD, network status)
    2. Audio PCM Port (used for 16-bit 8000Hz PCM voice streaming)
    """
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        ports = []

    at_port = None
    audio_port = None

    if ports:
        # Step 1: Detect Huawei hardware IDs (12D1) or descriptions
        huawei_ports = []
        for p in ports:
            ident = f"{p.description} {p.hwid} {p.device}".lower()
            if "12d1" in ident or "huawei" in ident:
                huawei_ports.append(p)

        if huawei_ports:
            for p in huawei_ports:
                desc = p.description.lower()
                if "modem" in desc and not at_port:
                    at_port = p.device
                elif ("pc ui" in desc or "application" in desc or "audio" in desc) and not audio_port:
                    audio_port = p.device
            for p in huawei_ports:
                if not at_port and p.device != audio_port:
                    at_port = p.device
                elif not audio_port and p.device != at_port:
                    audio_port = p.device

        # Step 2: Probe available COM ports if Huawei not specifically matched by name
        if not at_port:
            for p in ports:
                try:
                    h = k32.CreateFileW(f"\\\\.\\{p.device}", 0xC0000000, 0, None, 3, 0, None)
                    if is_valid_handle(h):
                        to = COMMTIMEOUTS(100, 0, 100, 0, 100)
                        k32.SetCommTimeouts(h, ctypes.byref(to))
                        written = wintypes.DWORD(0)
                        k32.WriteFile(h, b"AT\r\n", 4, ctypes.byref(written), None)
                        time.sleep(0.12)
                        buf = ctypes.create_string_buffer(128)
                        rb = wintypes.DWORD(0)
                        k32.ReadFile(h, buf, 127, ctypes.byref(rb), None)
                        k32.CloseHandle(h)
                        if b"OK" in buf.value or b"0" in buf.value:
                            at_port = p.device
                            break
                except Exception:
                    continue

    # Fallback probe for COM7 / COM6
    if not at_port:
        h = k32.CreateFileW("\\\\.\\COM7", 0xC0000000, 0, None, 3, 0, None)
        if is_valid_handle(h):
            k32.CloseHandle(h)
            at_port = "COM7"
            audio_port = "COM6"

    return at_port, audio_port

class ModemVoiceBridge:
    def __init__(self, at_port="COM7", audio_port="COM6"):
        self.at_port = at_port
        self.audio_port = audio_port
        self.h_at = None
        self.running = False
        self.modem_connected = False
        self.serial_lock = threading.RLock()
        self.audio_lock = threading.Lock()
        
        # Call State
        self.call_state = "IDLE"  # IDLE, DIALING, RINGING, CONNECTED, INCOMING, HELD
        self.current_call_id = None
        self.active_number = ""
        self.caller_id = ""
        self.active_contact_name = None
        self.call_connected_time = None
        self.call_start_time = None
        
        # Audio Router
        self.audio_router = audio_router
        self.is_muted = False
        self.speaker_enabled = True
        
        # Cellular Status
        self.signal_csq = 0
        self.signal_percent = 0
        self.signal_dbm = 0
        self.carrier_name = "Searching for Modem..."
        self.network_type = "Offline"
        self.network_registered = False
        self.model = "Searching for Modem..."
        self.imei = "N/A"
        self.firmware = "N/A"
        
        # Subscribers for SSE
        self.subscribers = []
        self.subscribers_lock = threading.Lock()
        
        # USSD State
        self.latest_ussd = None
        self.ussd_session_active = False
        self.at_busy = False
        
        # SMS Sending Synchronization
        self.sms_prompt_event = threading.Event()
        self.sms_result_event = threading.Event()
        self.sms_result_text = ""

    def open(self, at_port=None, audio_port=None):
        if at_port:
            self.at_port = at_port
        if audio_port:
            self.audio_port = audio_port
            self.audio_router.audio_port = audio_port

        print(f"[*] Opening AT command port {self.at_port} (Audio: {self.audio_port})...")
        with self.serial_lock:
            if is_valid_handle(self.h_at):
                try:
                    k32.CloseHandle(self.h_at)
                except Exception:
                    pass
                self.h_at = None

            self.h_at = k32.CreateFileW(f"\\\\.\\{self.at_port}", 0xC0000000, 0, None, 3, 0, None)
            if not is_valid_handle(self.h_at):
                print(f"[-] Failed to open {self.at_port} (Error {k32.GetLastError()})")
                self.h_at = None
                self.modem_connected = False
                return False
                
            to = COMMTIMEOUTS(0xFFFFFFFF, 0, 0, 0, 1000)
            k32.SetCommTimeouts(self.h_at, ctypes.byref(to))
            
            self.running = True
            self.modem_connected = True
        
        # Background serial reader thread
        if not hasattr(self, 'reader_thread') or not self.reader_thread or not self.reader_thread.is_alive():
            self.reader_thread = threading.Thread(target=self._at_read_loop, name="AT-Reader", daemon=True)
            self.reader_thread.start()
        
        # Background poller (signal & network registration & USB keepalive)
        if not hasattr(self, 'poller_thread') or not self.poller_thread or not self.poller_thread.is_alive():
            self.poller_thread = threading.Thread(target=self._poll_loop, name="AT-Poller", daemon=True)
            self.poller_thread.start()
        
        time.sleep(0.3)
        self._init_modem()
        return True

    def close(self):
        print(f"[*] Disconnecting modem {self.at_port}...")
        self.running = False
        with self.serial_lock:
            if is_valid_handle(self.h_at):
                try:
                    k32.CloseHandle(self.h_at)
                except Exception:
                    pass
                self.h_at = None
        self.stop_voice_audio()
        self.modem_connected = False
        self.network_registered = False
        self.carrier_name = "Searching for Modem..."
        self.model = "Searching for Modem..."
        self.signal_dbm = 0
        self.signal_percent = 0
        self.network_type = "Offline"
        self.call_state = "IDLE"

    def start_hardware_watchdog(self):
        t_watchdog = threading.Thread(target=self._hardware_watchdog_loop, name="Modem-Watchdog", daemon=True)
        t_watchdog.start()
        t_cdfs = threading.Thread(target=self._cdfs_switcher_loop, name="CDFS-Switcher", daemon=True)
        t_cdfs.start()

    def _cdfs_switcher_loop(self):
        print("[*] Huawei CDFS auto-switcher armed. Monitoring USB insertion...")
        last_switch = 0
        while True:
            try:
                if not self.modem_connected:
                    letter, name = find_cdfs_drive()
                    now = time.time()
                    if letter and (now - last_switch > 12):
                        print(f"[+] Detected Huawei/Vodafone CDFS drive on {letter}: ({name})")
                        last_switch = now
                        # 1. Modem Mode CDB
                        send_scsi_cdb(letter, bytes.fromhex("11062000000100000000000000000000"))
                        time.sleep(0.3)
                        # 2. HuaweiNewMode CDB
                        send_scsi_cdb(letter, bytes.fromhex("11060000000000000000000000000000"))
                        time.sleep(0.3)
                        # 3. SCSI Eject CDB
                        send_scsi_cdb(letter, bytes.fromhex("1b000000020000000000000000000000"))
                        print("[+] Huawei mode switch commands dispatched! Dongle rebooting into Serial Mode (PID 14FB)...")
            except Exception:
                pass
            time.sleep(0.25)

    def _hardware_watchdog_loop(self):
        consecutive_errors = 0
        while True:
            try:
                if not self.modem_connected:
                    at_p, aud_p = scan_cellular_modem_ports()
                    if at_p:
                        print(f"[+] Cellular modem detected on {at_p} (Audio: {aud_p or 'N/A'})")
                        if self.open(at_p, aud_p):
                            print(f"[+] Successfully connected to modem on {self.at_port}!")
                            self.mbim_mode = False
                            consecutive_errors = 0
                            self.broadcast_event("modem_connected", {"connected": True, "model": self.model})
                            self.broadcast_event("status_update", self.get_status())
                    else:
                        mbn = query_windows_mbn_status()
                        if mbn:
                            if not getattr(self, "mbim_mode", False):
                                self.mbim_mode = True
                                self.carrier_name = mbn["carrier"]
                                self.model = f"Huawei {mbn['model']}" if not mbn["model"].startswith("Huawei") else mbn["model"]
                                self.signal_percent = mbn["signal_pct"]
                                self.signal_dbm = mbn["signal_dbm"]
                                self.network_type = "Data Mode (MBIM)"
                                self.broadcast_event("status_update", self.get_status())
                        else:
                            if getattr(self, "mbim_mode", False):
                                self.mbim_mode = False
                                self.carrier_name = "Searching for Modem..."
                                self.model = "Searching for Modem..."
                                self.network_type = "Offline"
                                self.broadcast_event("status_update", self.get_status())
                else:
                    if not is_valid_handle(self.h_at):
                        consecutive_errors += 1
                    else:
                        cs = COMSTAT()
                        errs = wintypes.DWORD(0)
                        ok = k32.ClearCommError(self.h_at, ctypes.byref(errs), ctypes.byref(cs))
                        if not ok:
                            consecutive_errors += 1
                        else:
                            consecutive_errors = 0

                    if consecutive_errors >= 2:
                        print("[-] Cellular modem disconnected / unplugged!")
                        self.close()
                        consecutive_errors = 0
                        self.broadcast_event("modem_disconnected", {"connected": False})
                        self.broadcast_event("status_update", self.get_status())
            except Exception:
                pass
            time.sleep(1.5)

    def _write_at_raw(self, cmd_bytes):
        with self.serial_lock:
            if not is_valid_handle(self.h_at):
                return False
            written = wintypes.DWORD(0)
            return k32.WriteFile(self.h_at, cmd_bytes, len(cmd_bytes), ctypes.byref(written), None)

    def send_at(self, cmd, wait_time=0.15):
        full_cmd = (cmd + "\r\n").encode("utf-8")
        self._write_at_raw(full_cmd)
        if wait_time > 0:
            time.sleep(wait_time)

    def _init_modem(self):
        print("[*] Configuring modem for Voice, SMS & USSD...")
        self.model = "Huawei K4201"
        self.network_type = "3G (HSPA+)"
        self.network_registered = True
        self.send_at("ATE0")               # Echo off
        self.send_at("AT+CMEE=2")          # Verbose errors
        self.send_at('AT^SETPORT="A1,A2;1,2,3"') # Lock into Serial Voice Mode permanently in NVRAM
        self.send_at('AT^SETPORT="FF;1,2,3"')    # Fallback permanent NVRAM configuration
        self.send_at("AT+CLIP=1")          # Enable Caller ID
        self.send_at("AT+CRC=1")           # Extended cellular ring reporting
        self.send_at("AT+CMGF=1")          # SMS Text Mode
        self.send_at('AT+CSCS="GSM"')      # GSM charset
        self.send_at('AT+CPMS="SM","SM","SM"') # Set SMS storage to SIM
        self.send_at("AT+CNMI=2,1,0,0,0")  # Enable new SMS URC indications (+CMTI)
        self.send_at("AT+CUSD=1")          # Enable USSD unsolicited notifications (+CUSD)
        self.send_at("AT+CREG=1")          # Enable network registration URCs
        self.send_at("AT^CVOICE=0,8000,16,20") # Enable Voice audio capability
        self.send_at("AT^DDSETEX=2")       # Arm DSP audio routing to secondary interface (COM6)
        self.send_at("AT+CLVL=5")          # Maximum speaker output level
        self.send_at("AT+CSQ")             # Initial signal strength
        self.send_at("AT+COPS?")           # Operator query
        
        # Sync any unread SMS stored on SIM card on startup
        threading.Thread(target=self._sync_sim_messages, daemon=True).start()

    def _sync_sim_messages(self):
        time.sleep(1.5)
        self.send_at('AT+CMGL="ALL"')

    def broadcast_event(self, event_type, data):
        payload = json.dumps({"event": event_type, "data": data})
        message = f"event: {event_type}\ndata: {payload}\n\n"
        with self.subscribers_lock:
            for q in list(self.subscribers):
                try:
                    q.put_nowait(message)
                except Exception:
                    self.subscribers.remove(q)

    def _at_read_loop(self):
        """
        Non-blocking Win32 reader loop for COM7 with multi-line quote awareness
        for USSD menus (+CUSD) and SMS retrieval (+CMGR, +CMGL).
        """
        raw_buf = bytearray()
        cs = COMSTAT()
        errs = wintypes.DWORD(0)
        
        while self.running:
            if not is_valid_handle(self.h_at):
                time.sleep(0.05)
                continue
                
            k32.ClearCommError(self.h_at, ctypes.byref(errs), ctypes.byref(cs))
            if cs.cbInQue > 0:
                chunk = ctypes.create_string_buffer(cs.cbInQue)
                read_bytes = wintypes.DWORD(0)
                ok = k32.ReadFile(self.h_at, chunk, cs.cbInQue, ctypes.byref(read_bytes), None)
                if ok and read_bytes.value > 0:
                    raw_buf.extend(chunk.raw[:read_bytes.value])
                    
                    # 0. Check for SMS prompt '>' when sending an SMS
                    if self.at_busy and b">" in raw_buf:
                        p_pos = raw_buf.find(b">")
                        raw_buf = raw_buf[p_pos+1:]
                        self.sms_prompt_event.set()
                        continue

                    # 1. Check for multiline +CUSD: response in buffer
                    text_view = raw_buf.decode("utf-8", errors="replace")
                    
                    # 0b. Check for SMS submission confirmation or error
                    if self.at_busy and ("+CMGS:" in text_view or "+CMS ERROR" in text_view):
                        cmgs_m = re.search(r'(\+CMGS:\s*\d+.*?\r?\n\s*OK|\+CMS ERROR:.*?\r?\n)', text_view, re.DOTALL)
                        if cmgs_m:
                            self.sms_result_text = cmgs_m.group(0)
                            self.sms_result_event.set()
                            consumed_len = len(text_view[:cmgs_m.end()].encode("utf-8", errors="replace"))
                            raw_buf = raw_buf[consumed_len:]
                            continue

                    if getattr(self, "ussd_pending", False) and time.time() - getattr(self, "ussd_sent_time", 0) > 15.0:
                        self.ussd_pending = False
                        self.ussd_session_active = False
                        self.latest_ussd = {
                            "type": 2,
                            "text": "Network request timed out. Please try again.",
                            "active": False,
                            "time": time.strftime("%H:%M:%S")
                        }
                        print("[USSD Request Timeout]")
                        self.broadcast_event("ussd_response", self.latest_ussd)

                    if "+CUSD:" in text_view:
                        cusd_idx = text_view.find("+CUSD:")
                        cusd_tail = text_view[cusd_idx:]
                        
                        # Check if quote-less network termination e.g. +CUSD: 2
                        cusd_term_m = re.match(r'\+CUSD:\s*(\d+)\s*(?:\r?\n|$)', cusd_tail)
                        if cusd_term_m and int(cusd_term_m.group(1)) == 2:
                            self.ussd_pending = False
                            self.ussd_session_active = False
                            self.latest_ussd = {
                                "type": 2,
                                "text": "Session terminated by network.",
                                "active": False,
                                "time": time.strftime("%H:%M:%S")
                            }
                            print("[USSD Terminated (Type 2)]")
                            self.broadcast_event("ussd_response", self.latest_ussd)
                            consumed_len = len(text_view[:cusd_idx + cusd_term_m.end()].encode("utf-8", errors="replace"))
                            raw_buf = raw_buf[consumed_len:]
                            continue

                        # Check if opening quote exists but closing quote hasn't arrived yet
                        first_q = cusd_tail.find('"')
                        if first_q != -1 and cusd_tail.find('"', first_q + 1) == -1:
                            # Incomplete USSD string still streaming from network; wait for more bytes
                            time.sleep(0.04)
                            continue

                        # Match complete +CUSD: <type>, "<text>" [, <dcs>]
                        cusd_m = re.search(r'\+CUSD:\s*(\d+)\s*,\s*"(.*?)"(?:\s*,\s*(\d+))?', text_view, re.DOTALL)
                        if cusd_m:
                            self.ussd_pending = False
                            m_type = int(cusd_m.group(1))
                            decoded_text = decode_ussd_text(cusd_m.group(2))
                            self.ussd_session_active = (m_type == 1)
                            self.latest_ussd = {
                                "type": m_type,
                                "text": decoded_text,
                                "active": self.ussd_session_active,
                                "time": time.strftime("%H:%M:%S")
                            }
                            print(f"[USSD Response (Type {m_type})]:\n{decoded_text}")
                            self.broadcast_event("ussd_response", self.latest_ussd)
                            consumed_len = len(text_view[:cusd_m.end()].encode("utf-8", errors="replace"))
                            raw_buf = raw_buf[consumed_len:]
                            continue

                    if getattr(self, "ussd_pending", False) and ("+CME ERROR:" in text_view or "\r\nERROR" in text_view):
                        err_m = re.search(r'(\+CME ERROR:\s*\d+|ERROR)', text_view)
                        if err_m:
                            self.ussd_pending = False
                            err_txt = err_m.group(0).strip()
                            self.latest_ussd = {
                                "type": 2,
                                "text": f"USSD Request Failed ({err_txt})",
                                "active": False,
                                "time": time.strftime("%H:%M:%S")
                            }
                            print(f"[USSD Failed]: {err_txt}")
                            self.broadcast_event("ussd_response", self.latest_ussd)
                            consumed_len = len(text_view[:err_m.end()].encode("utf-8", errors="replace"))
                            raw_buf = raw_buf[consumed_len:]
                            continue

                    # 2. Check for +CMGR: (Read single SMS response)
                    if "+CMGR:" in text_view:
                        cmgr_m = re.search(r'\+CMGR:\s*"([^"]+)",\s*"([^"]+)"(?:,[^,\r\n]*)*?,\s*"([^"]+)"[^\r\n]*\r?\n(.*?)\r?\n(?:\r?\nOK|\r?\n\+CME ERROR|\r?\n\r?\n|OK)', text_view, re.DOTALL)
                        if cmgr_m:
                            stat = cmgr_m.group(1)
                            sender = cmgr_m.group(2)
                            ts_raw = cmgr_m.group(3)
                            body = decode_sms_text(cmgr_m.group(4))
                            
                            # Normalize timestamp e.g. "26/11/04,20:45:00+00" -> "2026-11-04 20:45:00"
                            ts_formatted = time.strftime("%Y-%m-%d %H:%M:%S")
                            if "/" in ts_raw and "," in ts_raw:
                                try:
                                    dp, tp = ts_raw.split(",")[0], ts_raw.split(",")[1].split("+")[0].split("-")[0]
                                    y, m, d = dp.split("/")
                                    year = f"20{y}" if len(y) == 2 else y
                                    ts_formatted = f"{year}-{m}-{d} {tp}"
                                except Exception:
                                    pass

                            print(f"[SMS Received] From: {sender} | Text: {body}")
                            msg = db.save_message(sender, "inbound", body, "received", timestamp=ts_formatted)
                            self.broadcast_event("sms_received", msg)
                            
                            consumed_len = len(text_view[:cmgr_m.end()].encode("utf-8", errors="replace"))
                            raw_buf = raw_buf[consumed_len:]
                            
                            if hasattr(self, '_last_fetched_idx') and self._last_fetched_idx:
                                self.send_at(f"AT+CMGD={self._last_fetched_idx}", wait_time=0.05)
                                self._last_fetched_idx = None
                            continue

                    # 3. Check for +CMGL: (List SMS responses)
                    if "+CMGL:" in text_view and "OK" in text_view:
                        cmgl_items = list(re.finditer(r'\+CMGL:\s*(\d+),"([^"]+)","([^"]+)"(?:,[^,\r\n]*)*,"([^"]+)"\r?\n(.*?)\r?\n(?=\+CMGL:|OK|\r?\n\r?\n)', text_view, re.DOTALL))
                        if cmgl_items:
                            for item in cmgl_items:
                                idx = int(item.group(1))
                                stat = item.group(2)
                                sender = item.group(3)
                                ts_raw = item.group(4)
                                body = decode_sms_text(item.group(5))
                                direction = "outbound" if "SENT" in stat.upper() else "inbound"
                                msg = db.save_message(sender, direction, body, "received")
                                # Clean up from SIM
                                self.send_at(f"AT+CMGD={idx}", wait_time=0.05)
                            
                            end_pos = cmgl_items[-1].end()
                            raw_buf = raw_buf[len(text_view[:end_pos].encode("utf-8", errors="replace")):]
                            continue

                    # 4. Process line-by-line standard single-line URCs
                    while b"\n" in raw_buf:
                        pos = raw_buf.index(b"\n")
                        line = raw_buf[:pos].decode("utf-8", errors="replace").strip()
                        raw_buf = raw_buf[pos+1:]
                        if line:
                            self._handle_urc(line)
            else:
                time.sleep(0.02)

    def _handle_urc(self, line):
        if line.startswith("^DSFLOWRPT"):
            return

        # 1. Incoming Call Detection (RING, +CRING, +CLIP)
        if line.startswith("RING") or line.startswith("+CRING: VOICE"):
            if self.call_state != "INCOMING":
                self.call_state = "INCOMING"
                if not self.current_call_id:
                    self.current_call_id = str(uuid.uuid4())
                number = self.caller_id or "Unknown Caller"
                contact = db.find_contact_by_number(number)
                self.active_contact_name = contact["name"] if contact else None
                db.start_call_record(self.current_call_id, number, direction="incoming", contact_name=self.active_contact_name)
                print(f"[!] INCOMING CALL! Caller: {number} ({self.active_contact_name or 'Unknown'})")
                self.broadcast_event("incoming_call", {
                    "call_id": self.current_call_id,
                    "number": number,
                    "contact_name": self.active_contact_name,
                    "carrier": self.carrier_name,
                    "timestamp": time.strftime("%H:%M:%S")
                })
        elif line.startswith("+CLIP:"):
            match = re.search(r'\+CLIP:\s*"([^"]+)"', line)
            if match:
                self.caller_id = match.group(1)
                self.active_number = self.caller_id
                self.call_state = "INCOMING"
                if not self.current_call_id:
                    self.current_call_id = str(uuid.uuid4())
                contact = db.find_contact_by_number(self.caller_id)
                self.active_contact_name = contact["name"] if contact else None
                db.start_call_record(self.current_call_id, self.caller_id, direction="incoming", contact_name=self.active_contact_name)
                print(f"[+] CALLER ID: {self.caller_id} ({self.active_contact_name or 'Unknown'})")
                self.broadcast_event("incoming_call", {
                    "call_id": self.current_call_id,
                    "number": self.caller_id,
                    "contact_name": self.active_contact_name,
                    "carrier": self.carrier_name,
                    "timestamp": time.strftime("%H:%M:%S")
                })

        # 2. Outgoing Call Progression (^ORIG, ^CONF, ^CONN, ^CEND)
        elif line.startswith("^ORIG:"):
            self.call_state = "DIALING"
            self.broadcast_event("call_state", {
                "state": "DIALING",
                "number": self.active_number,
                "contact_name": self.active_contact_name
            })
        elif line.startswith("^CONF:"):
            self.call_state = "RINGING"
            self.broadcast_event("call_state", {
                "state": "RINGING",
                "number": self.active_number,
                "contact_name": self.active_contact_name
            })
        elif line.startswith("^CONN:") or line.startswith("+COLP:") or line.startswith("VOICE"):
            self.call_state = "CONNECTED"
            if not self.call_connected_time:
                self.call_connected_time = time.time()
            if self.current_call_id:
                db.update_call_connected(self.current_call_id)
            print("[+] CALL CONNECTED! Starting bidirectional PCM voice routing...")
            self.broadcast_event("call_state", {
                "state": "CONNECTED",
                "number": self.active_number or self.caller_id,
                "contact_name": self.active_contact_name
            })
            self.start_voice_audio()

        elif line.startswith("+CLCC:"):
            # Universal 3GPP call list: +CLCC: <id>, <dir>, <stat>, <mode>, <mpty>, ...
            m = re.search(r'\+CLCC:\s*\d+,\d+,(\d+)', line)
            if m:
                clcc_stat = int(m.group(1))
                if clcc_stat == 0 and self.call_state != "CONNECTED":
                    print("[+] +CLCC confirmed Active call state! Transitioning to CONNECTED.")
                    self.call_state = "CONNECTED"
                    if not self.call_connected_time:
                        self.call_connected_time = time.time()
                    if self.current_call_id:
                        db.update_call_connected(self.current_call_id)
                    self.broadcast_event("call_state", {
                        "state": "CONNECTED",
                        "number": self.active_number or self.caller_id,
                        "contact_name": self.active_contact_name
                    })
                    self.start_voice_audio()

        elif line.startswith("^CEND:") or line.startswith("NO CARRIER") or line.startswith("BUSY"):
            print("[*] CALL TERMINATED / DISCONNECTED.")
            duration = 0
            if self.call_connected_time:
                duration = int(time.time() - self.call_connected_time)
            
            if self.call_state == "INCOMING" and duration == 0:
                final_status = "missed"
            elif line.startswith("BUSY"):
                final_status = "busy"
            elif duration > 0:
                final_status = "completed"
            else:
                final_status = "failed"

            if self.current_call_id:
                db.finish_call_record(self.current_call_id, final_status, duration)

            self.stop_voice_audio()
            self.call_state = "IDLE"
            self.active_number = ""
            self.caller_id = ""
            self.active_contact_name = None
            self.call_connected_time = None
            self.current_call_id = None
            self.broadcast_event("call_state", {"state": "IDLE"})

        # 3. New SMS Indication (+CMTI: "SM", <index> or +CMTI: "ME", <index>)
        elif line.startswith("+CMTI:"):
            match = re.search(r'\+CMTI:\s*"([^"]+)"\s*,\s*(\d+)', line)
            if match:
                mem = match.group(1)
                idx = int(match.group(2))
                print(f"[SMS] New message arrived in {mem} at storage index {idx}")
                self._last_fetched_idx = idx
                threading.Thread(target=self._fetch_single_sms, args=(idx, mem), daemon=True).start()

        # 4. Signal & Network Updates
        elif line.startswith("^RSSI:") or line.startswith("+CSQ:"):
            match = re.search(r'(?:\^RSSI:|\+CSQ:)\s*(\d+)', line)
            if match:
                csq = int(match.group(1))
                self.signal_csq = csq
                self.signal_percent = min(100, int((csq / 31.0) * 100))
                self.signal_dbm = -113 + (csq * 2) if csq <= 31 else -51
                self.broadcast_event("status_update", self.get_status())
        elif line.startswith("+COPS:"):
            match = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"', line)
            if match:
                raw_op = match.group(1)
                op_map = {
                    "62002": "Telecel Ghana",
                    "62001": "MTN Ghana",
                    "62003": "AT (AirtelTigo)",
                    "62006": "Glo Ghana"
                }
                self.carrier_name = op_map.get(raw_op, raw_op)
                self.network_registered = True
                self.broadcast_event("status_update", self.get_status())
        elif line.startswith("^MODE:"):
            if "5" in line:
                self.network_type = "3G (HSPA+)"
            elif "3" in line:
                self.network_type = "2G (EDGE)"
            self.network_registered = True
            self.broadcast_event("status_update", self.get_status())

    def _poll_loop(self):
        """
        Polls signal and keeps COM7 active during calls to prevent Windows USB Selective Suspend.
        """
        while self.running:
            time.sleep(3)
            if not self.modem_connected:
                continue
            if self.at_busy:
                continue
            if self.call_state == "IDLE":
                self.send_at("AT+CSQ", wait_time=0.1)
                self.send_at("AT+CREG?", wait_time=0.1)
            elif self.call_state in ("DIALING", "RINGING", "CONNECTED"):
                self.send_at("AT+CLCC", wait_time=0.05)
                self.send_at("AT+CPAS", wait_time=0.05)

    # -------------------------------------------------------------
    # CALL ACTIONS
    # -------------------------------------------------------------
    def dial(self, number):
        if not self.modem_connected or not self.h_at:
            return {"status": "error", "error": "Modem not connected"}

        clean_num = number.strip().replace(" ", "")
        self.active_number = clean_num
        self.current_call_id = str(uuid.uuid4())
        
        contact = db.find_contact_by_number(clean_num)
        self.active_contact_name = contact["name"] if contact else None
        
        db.start_call_record(self.current_call_id, clean_num, direction="outgoing", contact_name=self.active_contact_name)
        
        self.call_state = "DIALING"
        self.call_connected_time = None
        self.call_start_time = time.time()
        
        self.broadcast_event("call_state", {
            "state": "DIALING",
            "number": clean_num,
            "contact_name": self.active_contact_name
        })
        
        # 1. Arm modem voice capability and set volume
        self.send_at("AT^CVOICE=0", wait_time=0.1)
        self.send_at("AT^DDSETEX=2", wait_time=0.1)
        self.send_at("AT+CLVL=5", wait_time=0.1)
        
        # 2. Start PC voice audio immediately so ringback tone, network prompts, and voice are heard!
        self.start_voice_audio()
        
        # 3. Submit cellular dial command
        self.send_at(f"ATD{clean_num};", wait_time=0.2)
        return {"status": "dialing", "number": clean_num, "call_id": self.current_call_id}

    def hangup(self):
        self.send_at("ATH", wait_time=0.1)
        self.send_at("AT+CHUP", wait_time=0.1)
        
        duration = 0
        if self.call_connected_time:
            duration = int(time.time() - self.call_connected_time)
        elif getattr(self, "call_start_time", None):
            duration = int(time.time() - self.call_start_time)

        if self.current_call_id:
            status = "completed" if duration > 3 else "cancelled"
            db.finish_call_record(self.current_call_id, status, duration)

        self.stop_voice_audio()
        self.call_state = "IDLE"
        self.active_number = ""
        self.caller_id = ""
        self.active_contact_name = None
        self.call_connected_time = None
        self.call_start_time = None
        self.current_call_id = None
        self.broadcast_event("call_state", {"state": "IDLE"})
        return {"status": "idle"}

    def answer(self):
        print("[*] Answering incoming call...")
        self.send_at("ATA", wait_time=0.3)
        self.call_state = "CONNECTED"
        self.call_connected_time = time.time()
        if self.current_call_id:
            db.update_call_connected(self.current_call_id)
        self.broadcast_event("call_state", {
            "state": "CONNECTED",
            "number": self.caller_id or self.active_number,
            "contact_name": self.active_contact_name
        })
        self.start_voice_audio()
        return {"status": "connected"}

    def hold_call(self):
        self.send_at("AT+CHLD=2")
        self.call_state = "HELD"
        self.broadcast_event("call_state", {"state": "HELD", "number": self.active_number})
        return {"status": "held"}

    def resume_call(self):
        self.send_at("AT+CHLD=1")
        self.call_state = "CONNECTED"
        self.broadcast_event("call_state", {"state": "CONNECTED", "number": self.active_number})
        return {"status": "connected"}

    def send_dtmf(self, digit):
        self.send_at(f"AT+VTS={digit}")
        return {"status": "dtmf_sent", "digit": digit}

    # -------------------------------------------------------------
    # BI-DIRECTIONAL AUDIO ROUTING (COM6 PCM 8000Hz 16-BIT)
    # -------------------------------------------------------------
    def start_voice_audio(self):
        with self.audio_lock:
            try:
                if self.audio_router.running:
                    return True
                print("[*] Engaging voice audio routing (COM6)...")
                self.send_at("AT^DDSETEX=2", wait_time=0.2)
                self.send_at("AT+CLVL=5", wait_time=0.1)
                success = self.audio_router.start()
                diagnostics.log("STATUS", f"start_voice_audio executed. Success: {success}")
                return success
            except Exception as e:
                print(f"[-] Error starting voice audio routing: {e}")
                diagnostics.log("ERROR", f"start_voice_audio exception: {e}")
                return False

    def stop_voice_audio(self):
        with self.audio_lock:
            self.audio_router.stop()
            diagnostics.log("STATUS", "stop_voice_audio executed.")

    # -------------------------------------------------------------
    # USSD & SMS
    # -------------------------------------------------------------
    def send_ussd(self, code):
        clean_code = code.strip()
        print(f"[*] Sending USSD: {clean_code}")
        if not self.modem_connected or not is_valid_handle(self.h_at):
            msg = {"type": 2, "text": "Cellular AT port not active (Modem in Broadband Data Mode).", "active": False, "time": time.strftime("%H:%M:%S")}
            self.latest_ussd = msg
            self.broadcast_event("ussd_response", msg)
            return {"status": "error", "message": "Modem not in AT command mode"}
        self.ussd_pending = True
        self.ussd_sent_time = time.time()
        self.send_at(f'AT+CUSD=1,"{clean_code}"')
        return {"status": "sent", "code": clean_code}

    def cancel_ussd(self):
        print("[*] Cancelling active USSD session...")
        self.send_at("AT+CUSD=2")
        self.ussd_session_active = False
        self.latest_ussd = {"type": 2, "text": "USSD session cancelled.", "active": False, "time": time.strftime("%H:%M:%S")}
        self.broadcast_event("ussd_response", self.latest_ussd)
        return {"status": "cancelled"}

    def send_sms(self, to_number, text):
        clean_num = to_number.strip().replace(" ", "")
        print(f"[*] Submitting SMS to modem: {clean_num} -> {text}")
        
        with self.serial_lock:
            self.at_busy = True
            self.sms_prompt_event.clear()
            self.sms_result_event.clear()
            self.sms_result_text = ""
            try:
                # 1. Text mode
                self.send_at("AT+CMGF=1", wait_time=0.1)
                
                # 2. Send AT+CMGS
                cmd_init = f'AT+CMGS="{clean_num}"\r\n'.encode()
                self._write_at_raw(cmd_init)
                
                # 3. Wait for prompt event from _at_read_loop
                prompt_ok = self.sms_prompt_event.wait(timeout=5.0)
                if not prompt_ok:
                    print("[-] Prompt '>' not received from modem! Cancelling with ESC...")
                    self._write_at_raw(b"\x1b")
                    msg = db.save_message(clean_num, "outbound", text, "failed")
                    self.broadcast_event("sms_failed", msg)
                    return {"status": "failed", "error": "Prompt not received", "message": msg}
                
                # 4. Send SMS body + Ctrl+Z (\x1a)
                body = text.encode("utf-8") + b"\x1a"
                self._write_at_raw(body)
                
                # 5. Wait for network submission confirmation from _at_read_loop
                result_ok = self.sms_result_event.wait(timeout=15.0)
                if result_ok and "+CMGS:" in self.sms_result_text:
                    print(f"[+] SMS successfully transmitted to cellular network: {self.sms_result_text.strip()}")
                    msg = db.save_message(clean_num, "outbound", text, "sent")
                    self.broadcast_event("sms_sent", msg)
                    return {"status": "sent", "message": msg}
                else:
                    err_text = self.sms_result_text.strip() or "Network submission timeout"
                    print(f"[-] SMS network submission failed: {err_text}")
                    self._write_at_raw(b"\x1b")
                    msg = db.save_message(clean_num, "outbound", text, "failed")
                    self.broadcast_event("sms_failed", msg)
                    return {"status": "failed", "error": err_text, "message": msg}
            finally:
                self.at_busy = False

    def _fetch_single_sms(self, idx, mem=None):
        """Reads message at index idx using AT+CMGR directly on COM7."""
        time.sleep(0.3)
        if mem:
            self.send_at(f'AT+CPMS="{mem}","{mem}","{mem}"', wait_time=0.1)
        self.send_at(f"AT+CMGR={idx}", wait_time=0.4)
        # Message is parsed by _at_read_loop and saved to SQLite

    def get_status(self):
        duration = 0
        if self.call_connected_time:
            duration = int(time.time() - self.call_connected_time)
        elif self.call_state in ("DIALING", "RINGING") and getattr(self, "call_start_time", None):
            duration = int(time.time() - self.call_start_time)
            
        mbim = getattr(self, "mbim_mode", False) and not self.modem_connected
        return {
            "modem_connected": self.modem_connected,
            "mbim_mode": mbim,
            "port": self.at_port if self.modem_connected else ("Mobile Broadband" if mbim else "Disconnected"),
            "audio_port": self.audio_port if self.modem_connected else "Disconnected",
            "model": self.model if (self.modem_connected or mbim) else "Searching for Modem...",
            "imei": self.imei if self.modem_connected else "N/A",
            "firmware": self.firmware if self.modem_connected else "N/A",
            "carrier": self.carrier_name if (self.modem_connected or mbim) else "No Cellular Modem",
            "network_type": self.network_type if (self.modem_connected or mbim) else "Offline",
            "network_registered": self.network_registered if self.modem_connected else mbim,
            "signal_csq": self.signal_csq if self.modem_connected else (int(self.signal_percent * 31 / 100) if mbim else 0),
            "signal_percent": self.signal_percent,
            "signal_dbm": self.signal_dbm,
            "call_state": self.call_state,
            "active_number": self.active_number or self.caller_id,
            "caller_id": self.caller_id,
            "contact_name": self.active_contact_name,
            "call_duration": duration,
            "audio_active": self.audio_router.running,
            "is_muted": self.audio_router.is_muted,
            "speaker_enabled": self.audio_router.speaker_enabled,
            "ussd_session_active": self.ussd_session_active,
            "latest_ussd": self.latest_ussd
        }

bridge = ModemVoiceBridge("COM7", "COM6")

class APIHandler(BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        path_clean = self.path.split("?")[0]
        query_str = self.path.split("?")[1] if "?" in self.path else ""
        query_params = dict(qp.split("=") for qp in query_str.split("&") if "=" in qp)

        if path_clean == "/api/status":
            self._respond_json(bridge.get_status())

        elif path_clean == "/api/calls":
            f_type = query_params.get("filter", "all")
            search = query_params.get("search", "")
            calls = db.get_call_history(filter_type=f_type, search=search)
            self._respond_json(calls)

        elif path_clean == "/api/conversations":
            search = query_params.get("search", "")
            convs = db.get_conversations(search=search)
            self._respond_json(convs)

        elif path_clean == "/api/messages":
            num = query_params.get("number", "")
            msgs = db.get_messages(num)
            self._respond_json(msgs)

        elif path_clean == "/api/contacts":
            search = query_params.get("search", "")
            contacts = db.get_contacts(search=search)
            self._respond_json(contacts)

        elif path_clean == "/api/ussd":
            self._respond_json({
                "latest": bridge.latest_ussd,
                "session_active": bridge.ussd_session_active
            })

        elif path_clean == "/api/audio/diagnostics":
            thread_health = bridge.audio_router.get_thread_health()
            snap = diagnostics.snapshot(thread_statuses=thread_health, call_state=bridge.call_state)
            self._respond_json(snap)

        elif path_clean == "/api/events":
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            q = queue.Queue()
            with bridge.subscribers_lock:
                bridge.subscribers.append(q)

            init_payload = json.dumps({"event": "status_update", "data": bridge.get_status()})
            self.wfile.write(f"event: status_update\ndata: {init_payload}\n\n".encode())
            self.wfile.flush()

            try:
                while bridge.running:
                    try:
                        msg = q.get(timeout=15.0)
                        self.wfile.write(msg.encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with bridge.subscribers_lock:
                    if q in bridge.subscribers:
                        bridge.subscribers.remove(q)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if self.path == "/api/dial":
            number = data.get("number", "").strip()
            res = bridge.dial(number)
            self._respond_json(res)

        elif self.path == "/api/hangup":
            res = bridge.hangup()
            self._respond_json(res)

        elif self.path == "/api/answer":
            res = bridge.answer()
            self._respond_json(res)

        elif self.path == "/api/hold":
            res = bridge.hold_call()
            self._respond_json(res)

        elif self.path == "/api/resume":
            res = bridge.resume_call()
            self._respond_json(res)

        elif self.path == "/api/dtmf":
            digit = data.get("digit", "1")
            res = bridge.send_dtmf(digit)
            self._respond_json(res)

        elif self.path == "/api/ussd":
            code = data.get("code", "").strip()
            res = bridge.send_ussd(code)
            self._respond_json(res)

        elif self.path == "/api/ussd/cancel":
            res = bridge.cancel_ussd()
            self._respond_json(res)

        elif self.path == "/api/sms/send":
            to = data.get("to", "").strip()
            text = data.get("text", "").strip()
            res = bridge.send_sms(to, text)
            self._respond_json(res)

        elif self.path == "/api/messages/read":
            number = data.get("number", "").strip()
            db.mark_conversation_read(number)
            self._respond_json({"status": "marked_read", "number": number})

        elif self.path == "/api/conversations/delete":
            number = data.get("number", "").strip()
            db.delete_conversation(number)
            self._respond_json({"status": "deleted", "number": number})

        elif self.path == "/api/contacts/delete":
            cid = data.get("id")
            db.delete_contact(cid)
            self._respond_json({"status": "deleted", "id": cid})

        elif self.path == "/api/calls/clear":
            db.clear_call_history()
            self._respond_json({"status": "cleared"})

        elif self.path == "/api/contacts/save":
            name = data.get("name", "").strip()
            number = data.get("phone_number", "").strip()
            category = data.get("category", "Personal")
            notes = data.get("notes", "")
            avatar_color = data.get("avatar_color", "#8b5cf6")
            contact = db.save_contact(name, number, avatar_color=avatar_color, category=category, notes=notes)
            self._respond_json(contact)

        elif self.path == "/api/audio/mute":
            muted = bool(data.get("muted", False))
            bridge.audio_router.set_mute(muted)
            self._respond_json({"status": "updated", "muted": muted})

        elif self.path == "/api/audio/speaker":
            enabled = bool(data.get("enabled", True))
            bridge.audio_router.set_speaker(enabled)
            self._respond_json({"status": "updated", "speaker_enabled": enabled})

        elif self.path == "/api/audio/start":
            res = bridge.start_voice_audio()
            self._respond_json({"status": "started" if res else "failed"})

        elif self.path == "/api/audio/stop":
            bridge.stop_voice_audio()
            self._respond_json({"status": "stopped"})

        elif self.path == "/api/audio/test":
            def chime():
                wfx = WAVEFORMATEX(WAVE_FORMAT_PCM, 1, 8000, 16000, 2, 16, 0)
                h_out = wintypes.HANDLE()
                if winmm.waveOutOpen(ctypes.byref(h_out), -1, ctypes.byref(wfx), 0, 0, 0) == 0:
                    pcm = bytearray()
                    for i in range(3200): # 0.4s D5 (587Hz)
                        s = int(32767 * 0.25 * math.sin(2 * math.pi * 587 * i / 8000))
                        pcm.extend(s.to_bytes(2, "little", signed=True))
                    for i in range(4800): # 0.6s A5 (880Hz)
                        s = int(32767 * 0.25 * math.sin(2 * math.pi * 880 * i / 8000))
                        pcm.extend(s.to_bytes(2, "little", signed=True))
                    buf = ctypes.create_string_buffer(bytes(pcm))
                    hdr = WAVEHDR(ctypes.cast(buf, ctypes.c_char_p), len(pcm), 0, 0, 0, 0, None, 0)
                    winmm.waveOutPrepareHeader(h_out, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                    winmm.waveOutWrite(h_out, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                    time.sleep(1.1)
                    winmm.waveOutReset(h_out)
                    winmm.waveOutClose(h_out)
            threading.Thread(target=chime, daemon=True).start()
            self._respond_json({"status": "testing_audio"})

        elif self.path == "/api/at":
            cmd = data.get("command", "").strip()
            bridge.send_at(cmd)
            self._respond_json({"status": "executed", "command": cmd})
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        path_clean = self.path.split("?")[0]
        query_str = self.path.split("?")[1] if "?" in self.path else ""
        query_params = dict(qp.split("=") for qp in query_str.split("&") if "=" in qp)

        if path_clean == "/api/calls":
            call_id = query_params.get("id")
            if call_id:
                db.delete_call_record(call_id)
            else:
                db.clear_call_history()
            self._respond_json({"status": "deleted"})

        elif path_clean == "/api/conversations":
            number = query_params.get("number")
            if number:
                db.delete_conversation(number)
            self._respond_json({"status": "deleted"})

        elif path_clean == "/api/messages":
            msg_id = query_params.get("id")
            if msg_id:
                db.delete_message(int(msg_id))
            self._respond_json({"status": "deleted"})

        elif path_clean == "/api/contacts":
            c_id = query_params.get("id")
            if c_id:
                db.delete_contact(int(c_id))
            self._respond_json({"status": "deleted"})
        else:
            self.send_response(404)
            self.end_headers()

    def _respond_json(self, data):
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def run_server(port=8765):
    at_p, aud_p = scan_cellular_modem_ports()
    if at_p:
        bridge.open(at_p, aud_p)
    else:
        print("[*] No cellular modem detected on startup. Hardware watchdog scanner armed...")
    
    bridge.start_hardware_watchdog()

    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, APIHandler)
    print(f"[+] Dialtone Backend listening on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        bridge.close()
        httpd.server_close()

if __name__ == "__main__":
    run_server()
