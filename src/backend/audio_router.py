"""
Switchboard Audio Engine & Diagnostics Manager
Provides robust, leak-free, bi-directional 16-bit 8000Hz mono PCM audio routing between
Huawei K4201 (COM6) and Windows Multimedia Audio Devices (waveOut & waveIn).

Features:
1. 20ms frame alignment (320 bytes @ 8000Hz 16-bit Mono) matching Huawei baseband DSP.
2. Full DCB initialization (115200 8N1 raw binary) and 64KB driver buffer sizing.
3. Active assertion of DTR and RTS signals for USB CDC ACM bulk endpoints.
4. Continuous 20ms uplink frame transmission to prevent DSP audio watchdog drops.
5. True 64-bit WAVEHDR structure alignment preventing buffer recycling starvation.
6. Non-blocking Win32 serial multiplexing eliminating usbser.sys driver deadlocks.
"""

import ctypes
import threading
import time
import queue
import collections
import math
from ctypes import wintypes

winmm = ctypes.windll.winmm
k32 = ctypes.windll.kernel32

k32.CreateEventW.restype = wintypes.HANDLE
k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]

k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]

k32.SetCommTimeouts.restype = wintypes.BOOL
k32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

k32.SetupComm.restype = wintypes.BOOL
k32.SetupComm.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]

k32.GetCommState.restype = wintypes.BOOL
k32.GetCommState.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

k32.SetCommState.restype = wintypes.BOOL
k32.SetCommState.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

k32.EscapeCommFunction.restype = wintypes.BOOL
k32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]

k32.ClearCommError.restype = wintypes.BOOL
k32.ClearCommError.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p]

k32.ReadFile.restype = wintypes.BOOL
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]

k32.WriteFile.restype = wintypes.BOOL
k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]

k32.WaitForSingleObject.restype = wintypes.DWORD
k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

k32.CloseHandle.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

def is_valid_handle(h):
    if not h or h == 0:
        return False
    if h == -1 or h == INVALID_HANDLE_VALUE or h == 0xFFFFFFFFFFFFFFFF or h == 0xFFFFFFFF:
        return False
    return True

WAVE_FORMAT_PCM = 1
CALLBACK_EVENT = 0x00050000
CALLBACK_NULL = 0

WHDR_DONE = 0x00000001
WHDR_PREPARED = 0x00000002
WHDR_INQUEUE = 0x00000010

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD)
    ]

class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_char_p),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t)
    ]

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

class DCB(ctypes.Structure):
    _fields_ = [
        ("DCBlength", wintypes.DWORD),
        ("BaudRate", wintypes.DWORD),
        ("fBitFields", wintypes.DWORD),
        ("wReserved", wintypes.WORD),
        ("XonLim", wintypes.WORD),
        ("XoffLim", wintypes.WORD),
        ("ByteSize", wintypes.BYTE),
        ("Parity", wintypes.BYTE),
        ("StopBits", wintypes.BYTE),
        ("XonChar", ctypes.c_char),
        ("XoffChar", ctypes.c_char),
        ("ErrorChar", ctypes.c_char),
        ("EofChar", ctypes.c_char),
        ("EvtChar", ctypes.c_char),
        ("wReserved1", wintypes.WORD)
    ]

class AudioDiagnostics:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            now = time.time()
            self.start_time = now
            self.bytes_rx = 0
            self.bytes_tx = 0
            self.frames_played = 0
            self.frames_captured = 0
            self.rx_overruns = 0
            self.tx_underruns = 0
            self.serial_errors = 0
            self.buffer_depth_bytes = 0
            self.last_downlink_time = None
            self.last_uplink_time = None
            self.last_downlink_bytes = 0
            self.last_uplink_bytes = 0
            self.com6_connected = False
            self.wave_out_active = False
            self.wave_in_active = False
            self.recent_logs = collections.deque(maxlen=150)
            self.last_rx_rate = 0.0
            self.last_tx_rate = 0.0
            self.prev_rx_check = (now, 0)
            self.prev_tx_check = (now, 0)

    def log(self, category, message):
        t_str = time.strftime("%H:%M:%S")
        entry = f"[{t_str}] [{category}] {message}"
        with self.lock:
            self.recent_logs.append(entry)
        print(f"[AudioDiag] {entry}")

    def record_downlink(self, num_bytes):
        with self.lock:
            self.bytes_rx += num_bytes
            self.last_downlink_time = time.time()
            self.last_downlink_bytes = num_bytes

    def record_uplink(self, num_bytes):
        with self.lock:
            self.bytes_tx += num_bytes
            self.last_uplink_time = time.time()
            self.last_uplink_bytes = num_bytes

    def update_throughput(self):
        with self.lock:
            now = time.time()
            rx_dt = now - self.prev_rx_check[0]
            if rx_dt >= 1.0:
                self.last_rx_rate = (self.bytes_rx - self.prev_rx_check[1]) / rx_dt
                self.prev_rx_check = (now, self.bytes_rx)

            tx_dt = now - self.prev_tx_check[0]
            if tx_dt >= 1.0:
                self.last_tx_rate = (self.bytes_tx - self.prev_tx_check[1]) / tx_dt
                self.prev_tx_check = (now, self.bytes_tx)

    def snapshot(self, thread_statuses=None, call_state="CONNECTED"):
        self.update_throughput()
        with self.lock:
            now = time.time()
            dur = int(now - self.start_time) if self.com6_connected else 0

            sec_since_downlink = round(now - self.last_downlink_time, 2) if self.last_downlink_time else None
            sec_since_uplink = round(now - self.last_uplink_time, 2) if self.last_uplink_time else None

            dl_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_downlink_time)) if self.last_downlink_time else "None"
            ul_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_uplink_time)) if self.last_uplink_time else "None"

            return {
                "active_duration_sec": dur,
                "com6_connected": self.com6_connected,
                "call_state": call_state,
                "bytes_rx": self.bytes_rx,
                "bytes_tx": self.bytes_tx,
                "rx_rate_bps": round(self.last_rx_rate, 1),
                "tx_rate_bps": round(self.last_tx_rate, 1),
                "last_downlink_timestamp": dl_iso,
                "last_uplink_timestamp": ul_iso,
                "sec_since_last_downlink": sec_since_downlink,
                "sec_since_last_uplink": sec_since_uplink,
                "downlink_flowing": (sec_since_downlink is not None and sec_since_downlink < 2.0),
                "uplink_flowing": (sec_since_uplink is not None and sec_since_uplink < 2.0),
                "frames_played": self.frames_played,
                "frames_captured": self.frames_captured,
                "rx_overruns": self.rx_overruns,
                "tx_underruns": self.tx_underruns,
                "serial_errors": self.serial_errors,
                "buffer_depth_bytes": self.buffer_depth_bytes,
                "buffer_latency_ms": int((self.buffer_depth_bytes / 16000.0) * 1000),
                "wave_out_active": self.wave_out_active,
                "wave_in_active": self.wave_in_active,
                "threads": thread_statuses or {},
                "recent_logs": list(self.recent_logs)[-35:]
            }

diagnostics = AudioDiagnostics()

class RobustAudioRouter:
    """
    WinMM 8000Hz 16-bit Mono Audio Engine with 20ms Frame Alignment and COM6 PCM Streaming.
    """
    FRAME_SIZE = 320    # 20ms frame at 8000Hz 16-bit mono (160 samples * 2 bytes)
    NUM_BUFFERS = 24    # 24 ring buffers for waveOut (480ms capacity)
    NUM_IN_BUFFERS = 8  # 8 ring buffers for waveIn (160ms capacity)

    def __init__(self, audio_port="COM6"):
        self.audio_port = audio_port
        self.h_audio = None
        self.running = False
        self.is_muted = False
        self.speaker_enabled = True

        # WinMM Playback
        self.h_wave_out = wintypes.HANDLE()
        self.h_event_out = None
        self.out_buffers = []
        self.free_out_indices = queue.Queue()

        # Decoupled Playback Queue (Modem COM6 -> Speakers)
        self.playback_queue = collections.deque(maxlen=16000 * 3) # 3 seconds max
        self.queue_lock = threading.Lock()

        # WinMM Capture (Microphone -> Modem COM6)
        self.h_wave_in = wintypes.HANDLE()
        self.h_event_in = None
        self.in_buffers = []

        # Outgoing Uplink Queue (Mic Frames -> COM6)
        self.uplink_queue = queue.Queue(maxsize=30)

        # Worker Threads
        self.io_thread = None
        self.playback_thread = None
        self.capture_thread = None
        self.lifecycle_lock = threading.RLock()

    def start(self):
        with self.lifecycle_lock:
            if self.running:
                return True
            diagnostics.reset()
            diagnostics.log("START", f"Opening audio pipeline on {self.audio_port} (8000Hz 16-bit PCM 20ms)...")

            # 1. Open COM6 with non-blocking timeouts
            self.h_audio = k32.CreateFileW(f"\\\\.\\{self.audio_port}", 0xC0000000, 0, None, 3, 0, None)
            if not is_valid_handle(self.h_audio):
                err = k32.GetLastError()
                diagnostics.log("ERROR", f"Failed to open {self.audio_port} (Win32 Error {err})")
                return False

            self.running = True
            to = COMMTIMEOUTS(0xFFFFFFFF, 0, 0, 0, 500)
            k32.SetCommTimeouts(self.h_audio, ctypes.byref(to))
            
            # Setup 64KB driver FIFO buffers
            k32.SetupComm(self.h_audio, 65536, 65536)

            # Configure DCB for 115200 8N1 raw binary
            dcb = DCB()
            dcb.DCBlength = ctypes.sizeof(DCB)
            if k32.GetCommState(self.h_audio, ctypes.byref(dcb)):
                dcb.BaudRate = 115200
                dcb.ByteSize = 8
                dcb.Parity = 0  # NOPARITY
                dcb.StopBits = 0 # ONESTOPBIT
                # fBinary=1, fDtrControl=DTR_CONTROL_ENABLE (0x01 << 4), fRtsControl=RTS_CONTROL_ENABLE (0x01 << 12)
                dcb.fBitFields = 1 | (1 << 4) | (1 << 12)
                k32.SetCommState(self.h_audio, ctypes.byref(dcb))

            # Assert DTR and RTS to enable bulk transfer on USB CDC serial interface
            k32.EscapeCommFunction(self.h_audio, 5) # SETDTR
            k32.EscapeCommFunction(self.h_audio, 3) # SETRTS
            self.speaker_enabled = True

            diagnostics.com6_connected = True
            diagnostics.log("COM6", f"COM6 handle successfully opened (115200 8N1, DTR/RTS asserted, 64KB FIFO).")

            # 2. Initialize Playback Engine (waveOut with CALLBACK_EVENT)
            if not self._init_wave_out():
                diagnostics.log("ERROR", "Failed to initialize WinMM waveOut device.")
                self.running = False
                self.stop()
                return False

            # 3. Initialize Capture Engine (waveIn with CALLBACK_EVENT)
            self._init_wave_in()

            # Request 1ms timer resolution on Windows
            try:
                winmm.timeBeginPeriod(1)
            except Exception:
                pass

            # 4. Launch Threads
            self.io_thread = threading.Thread(target=self._com6_io_loop, name="COM6-MuxIO", daemon=True)
            self.playback_thread = threading.Thread(target=self._playback_feeder_loop, name="WaveOut-Feeder", daemon=True)
            self.capture_thread = threading.Thread(target=self._capture_worker_loop, name="WaveIn-Worker", daemon=True)

            self.io_thread.start()
            self.playback_thread.start()
            if diagnostics.wave_in_active:
                self.capture_thread.start()

            diagnostics.log("PIPELINE", "All audio threads started successfully.")
            return True

    def _init_wave_out(self):
        wfx = WAVEFORMATEX()
        wfx.wFormatTag = WAVE_FORMAT_PCM
        wfx.nChannels = 1
        wfx.nSamplesPerSec = 8000
        wfx.nAvgBytesPerSec = 16000
        wfx.nBlockAlign = 2
        wfx.wBitsPerSample = 16
        wfx.cbSize = 0

        self.h_wave_out = wintypes.HANDLE()
        self.h_event_out = k32.CreateEventW(None, False, False, None)

        res = winmm.waveOutOpen(
            ctypes.byref(self.h_wave_out),
            -1,  # WAVE_MAPPER
            ctypes.byref(wfx),
            self.h_event_out,
            0,
            CALLBACK_EVENT
        )
        if res != 0:
            diagnostics.log("ERROR", f"waveOutOpen failed: {res}")
            return False

        self.out_buffers.clear()
        while not self.free_out_indices.empty():
            try:
                self.free_out_indices.get_nowait()
            except queue.Empty:
                break

        for i in range(self.NUM_BUFFERS):
            buf = ctypes.create_string_buffer(self.FRAME_SIZE)
            hdr = WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_char_p)
            hdr.dwBufferLength = self.FRAME_SIZE
            hdr.dwFlags = 0
            hdr.dwUser = i
            prep_res = winmm.waveOutPrepareHeader(self.h_wave_out, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            if prep_res != 0:
                diagnostics.log("ERROR", f"waveOutPrepareHeader failed for buf {i}: {prep_res}")
                return False
            self.out_buffers.append((hdr, buf))
            self.free_out_indices.put(i)

        diagnostics.wave_out_active = True
        diagnostics.log("WAVEOUT", f"Pre-allocated {self.NUM_BUFFERS} ring buffers of {self.FRAME_SIZE}B (CALLBACK_EVENT).")
        return True

    def _init_wave_in(self):
        wfx = WAVEFORMATEX()
        wfx.wFormatTag = WAVE_FORMAT_PCM
        wfx.nChannels = 1
        wfx.nSamplesPerSec = 8000
        wfx.nAvgBytesPerSec = 16000
        wfx.nBlockAlign = 2
        wfx.wBitsPerSample = 16
        wfx.cbSize = 0

        self.h_wave_in = wintypes.HANDLE()
        self.h_event_in = k32.CreateEventW(None, False, False, None)

        res = winmm.waveInOpen(
            ctypes.byref(self.h_wave_in),
            -1,  # WAVE_MAPPER
            ctypes.byref(wfx),
            self.h_event_in,
            0,
            CALLBACK_EVENT
        )
        if res != 0:
            diagnostics.log("WARN", f"waveInOpen returned {res}. Microphone capture inactive.")
            diagnostics.wave_in_active = False
            return False

        self.in_buffers.clear()
        for i in range(self.NUM_IN_BUFFERS):
            buf = ctypes.create_string_buffer(self.FRAME_SIZE)
            hdr = WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_char_p)
            hdr.dwBufferLength = self.FRAME_SIZE
            hdr.dwFlags = 0
            hdr.dwUser = i
            winmm.waveInPrepareHeader(self.h_wave_in, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            winmm.waveInAddBuffer(self.h_wave_in, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            self.in_buffers.append((hdr, buf))

        if winmm.waveInStart(self.h_wave_in) == 0:
            diagnostics.wave_in_active = True
            diagnostics.log("WAVEIN", f"Microphone capture active ({self.NUM_IN_BUFFERS} buffers of {self.FRAME_SIZE}B).")
            return True
        else:
            diagnostics.wave_in_active = False
            return False

    def _com6_io_loop(self):
        """
        Unified COM6 I/O thread.
        Multiplexes Downlink Read and Uplink Write safely on usbser.sys.
        """
        cs = COMSTAT()
        errs = wintypes.DWORD(0)
        written = wintypes.DWORD(0)
        silence_chunk = b"\x00" * self.FRAME_SIZE # 20ms silence frame
        last_tx_time = time.time()
        read_buf = ctypes.create_string_buffer(4096)

        while self.running:
            if not is_valid_handle(self.h_audio):
                break

            # 1. Clear serial errors
            k32.ClearCommError(self.h_audio, ctypes.byref(errs), ctypes.byref(cs))

            # 2. DOWNLINK: Read available PCM from modem COM6
            read_bytes = wintypes.DWORD(0)
            ok = k32.ReadFile(self.h_audio, read_buf, 4096, ctypes.byref(read_bytes), None)
            if ok and read_bytes.value > 0:
                raw_data = read_buf.raw[:read_bytes.value]
                diagnostics.record_downlink(len(raw_data))
                with self.queue_lock:
                    self.playback_queue.extend(raw_data)
                    diagnostics.buffer_depth_bytes = len(self.playback_queue)

            # 3. UPLINK: Transmit 320-byte microphone frames to COM6
            data_to_write = None
            try:
                data_to_write = self.uplink_queue.get_nowait()
            except queue.Empty:
                # Keepalive: send comfort silence every 20ms to keep Huawei DSP voice pipeline alive
                if (time.time() - last_tx_time) >= 0.020:
                    data_to_write = silence_chunk

            if data_to_write:
                ok = k32.WriteFile(self.h_audio, data_to_write, len(data_to_write), ctypes.byref(written), None)
                if ok and written.value > 0:
                    diagnostics.record_uplink(written.value)
                    last_tx_time = time.time()

            # Small yield for CPU efficiency and ultra-low latency (<3ms)
            time.sleep(0.003)

    def _playback_feeder_loop(self):
        """
        Feeds audio frames from playback_queue into pre-allocated waveOut ring buffers.
        Only dispatches when a complete 320-byte frame (20ms) is ready.
        """
        silence_frame = b"\x00" * self.FRAME_SIZE

        while self.running:
            # 1. Reclaim completed buffers
            for i, (hdr, buf) in enumerate(self.out_buffers):
                if hdr.dwFlags & WHDR_DONE:
                    hdr.dwFlags &= ~WHDR_DONE
                    self.free_out_indices.put(i)

            # 2. Check if we have at least FRAME_SIZE bytes in playback_queue
            with self.queue_lock:
                q_len = len(self.playback_queue)
                diagnostics.buffer_depth_bytes = q_len
                if q_len < self.FRAME_SIZE:
                    time.sleep(0.005)
                    continue

                # Pull exactly FRAME_SIZE (320 bytes)
                frame_bytes = bytearray()
                for _ in range(self.FRAME_SIZE):
                    frame_bytes.append(self.playback_queue.popleft())

            # 3. Acquire a free buffer (wait if necessary)
            try:
                buf_idx = self.free_out_indices.get(timeout=0.03)
            except queue.Empty:
                if self.h_event_out:
                    k32.WaitForSingleObject(self.h_event_out, 15)
                continue

            if not self.speaker_enabled:
                frame_bytes = bytearray(silence_frame)

            # 4. Copy and dispatch to WinMM waveOut
            hdr, buf = self.out_buffers[buf_idx]
            ctypes.memmove(buf, bytes(frame_bytes), self.FRAME_SIZE)
            hdr.dwFlags &= ~WHDR_DONE
            hdr.dwBufferLength = self.FRAME_SIZE

            res = winmm.waveOutWrite(self.h_wave_out, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            if res == 0:
                diagnostics.frames_played += 1
            else:
                diagnostics.log("ERROR", f"waveOutWrite error {res} on buf {buf_idx}")
                self.free_out_indices.put(buf_idx)
                time.sleep(0.005)

    def _capture_worker_loop(self):
        """
        Microphone capture loop (waveIn -> uplink_queue).
        Pushes recorded 320-byte frames (20ms) into uplink_queue for COM6 transmission.
        """
        silence_frame = b"\x00" * self.FRAME_SIZE

        while self.running and diagnostics.wave_in_active:
            if not self.h_event_in:
                break

            k32.WaitForSingleObject(self.h_event_in, 30)

            for hdr, buf in self.in_buffers:
                if hdr.dwFlags & WHDR_DONE:
                    rec_len = hdr.dwBytesRecorded
                    if rec_len > 0:
                        if self.is_muted:
                            data = silence_frame[:rec_len]
                        else:
                            data = buf.raw[:rec_len]

                        # Slice into 320-byte chunks if needed
                        for offset in range(0, len(data), self.FRAME_SIZE):
                            chunk = data[offset:offset + self.FRAME_SIZE]
                            if len(chunk) == self.FRAME_SIZE:
                                try:
                                    self.uplink_queue.put_nowait(chunk)
                                    diagnostics.frames_captured += 1
                                except queue.Full:
                                    try:
                                        self.uplink_queue.get_nowait()
                                        self.uplink_queue.put_nowait(chunk)
                                    except Exception:
                                        pass

                    hdr.dwFlags &= ~WHDR_DONE
                    hdr.dwBytesRecorded = 0
                    winmm.waveInAddBuffer(self.h_wave_in, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))

    def set_mute(self, muted):
        self.is_muted = muted
        diagnostics.log("CONTROL", f"Microphone muted: {muted}")

    def set_speaker(self, enabled):
        self.speaker_enabled = enabled
        diagnostics.log("CONTROL", f"Speaker enabled: {enabled}")

    def get_thread_health(self):
        return {
            "io_thread_alive": bool(self.io_thread and self.io_thread.is_alive()),
            "playback_thread_alive": bool(self.playback_thread and self.playback_thread.is_alive()),
            "capture_thread_alive": bool(self.capture_thread and self.capture_thread.is_alive())
        }

    def stop(self):
        with self.lifecycle_lock:
            if not self.running and not diagnostics.com6_connected:
                return
            diagnostics.log("STOP", "Stopping audio engine...")
            self.running = False

        try:
            winmm.timeEndPeriod(1)
        except Exception:
            pass

        if self.h_wave_in:
            diagnostics.wave_in_active = False
            winmm.waveInStop(self.h_wave_in)
            winmm.waveInReset(self.h_wave_in)
            for hdr, buf in self.in_buffers:
                winmm.waveInUnprepareHeader(self.h_wave_in, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            winmm.waveInClose(self.h_wave_in)
            self.h_wave_in = None
        if self.h_event_in:
            k32.CloseHandle(self.h_event_in)
            self.h_event_in = None

        if self.h_wave_out:
            diagnostics.wave_out_active = False
            winmm.waveOutReset(self.h_wave_out)
            for hdr, buf in self.out_buffers:
                winmm.waveOutUnprepareHeader(self.h_wave_out, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            winmm.waveOutClose(self.h_wave_out)
            self.h_wave_out = None
        if self.h_event_out:
            k32.CloseHandle(self.h_event_out)
            self.h_event_out = None

        if is_valid_handle(self.h_audio):
            k32.CloseHandle(self.h_audio)
            self.h_audio = None
        diagnostics.com6_connected = False
        diagnostics.log("STOP", "Audio engine completely stopped.")

# Export singleton instance for modem bridge
audio_router = RobustAudioRouter("COM6")
