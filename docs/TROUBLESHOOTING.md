# Dialtone Troubleshooting Guide

This guide helps diagnose and resolve common issues encountered when connecting cellular USB modems and running Dialtone.

---

## Table of Contents
1. [Modem Shows "Searching for Modem..." or Offline](#1-modem-shows-searching-for-modem-or-offline)
2. [Modem Stuck in "Mobile Broadband" / Data Mode](#2-modem-stuck-in-mobile-broadband--data-mode)
3. [COM Port Access Denied or Port Locked](#3-com-port-access-denied-or-port-locked)
4. [Audio Issues (No Sound or Static During Calls)](#4-audio-issues-no-sound-or-static-during-calls)
5. [USSD Returns Error or Times Out](#5-ussd-returns-error-or-times-out)
6. [SMS Fails to Send (+CMS ERROR)](#6-sms-fails-to-send-cms-error)

---

## 1. Modem Shows "Searching for Modem..." or Offline

### Symptoms:
The top status bar remains stuck on amber `Searching for Modem...` and no carrier is shown.

### Causes & Fixes:
1. **Modem is in Mass Storage / CD-ROM mode:**
   - On first insertion, many modems present a virtual CD-ROM drive containing legacy carrier software.
   - **Fix:** Open File Explorer (`This PC`). If you see a CD drive like `Vodafone Mobile Broadband`, right-click it and select **Eject**. Dialtone's built-in CDFS switcher will detect the eject event and switch the modem into serial mode.
2. **Backend engine is not active:**
   - Verify the backend server is listening on port 8765:
     ```powershell
     netstat -ano | findstr 8765
     ```
   - If not responding, launch the backend manually from terminal:
     ```powershell
     python src/backend/modem_bridge.py
     ```
3. **Hardware USB connection loose:**
   - Re-insert the modem into a primary USB port directly on the laptop (avoid unpowered USB hubs).

---

## 2. Modem Stuck in "Mobile Broadband" / Data Mode

### Symptoms:
Dialtone reports: `Huawei K4201 in Broadband Data Mode. Reconnect for Voice`. The Windows network flyout shows `Cellular (Voda GH / Telecel) Getting ready...`.

### Cause:
Windows 10/11 includes a native Mobile Broadband Class Driver (`wmbclass.sys` / MBIM) that automatically binds to composite cellular dongles on initial connection, locking the baseband to IP data and suppressing the virtual serial COM ports needed for telephony.

### Solution:
1. In Windows Settings or the Quick Settings network panel, **turn off the Cellular toggle**.
2. Open **Device Manager** (`Win + X` -> `Device Manager`).
3. Locate the modem under **Network Adapters** or **Universal Serial Bus controllers**.
4. Right-click the device -> **Update driver** -> **Browse my computer for drivers** -> **Let me pick from a list of available drivers on my computer**.
5. Select **USB Mass Storage Device** or **USB Composite Device** and click Next.
6. Unplug the USB dongle, wait 3 seconds, and plug it back in.
7. Windows will re-enumerate the device as a standard USB Composite Device, loading `usbser.sys` for `COM7` (AT commands) and `COM6` (Audio).

---

## 3. COM Port Access Denied or Port Locked

### Symptoms:
Console logs show `WinError 5: Access is denied` or `Cannot open \\.\COM7`.

### Causes & Fixes:
- Another application is holding an exclusive handle to the COM port.
- Common culprits:
  - Legacy modem software (e.g., Vodafone Mobile Broadband, Huawei Mobile Partner, generic connection managers).
  - Terminal emulators (PuTTY, Tera Term, RealTerm).
  - Background serial monitors.
- **Fix:** Terminate any open serial software or conflicting cellular managers in Task Manager.

---

## 4. Audio Issues (No Sound or Static During Calls)

### Symptoms:
Calls connect and timers run, but no ringback tone or voice is heard through speakers, or microphone is not transmitted.

### Causes & Fixes:
1. **Secondary COM port (Audio PCM) unassigned:**
   - Check the **Audio** or **Devices** tab in Dialtone. Verify the secondary port is detected (e.g., `COM6`).
2. **Audio device selection:**
   - Go to the **Audio** tab and confirm your computer's active speakers and microphone are selected.
3. **Modem DSP volume muted:**
   - Dialtone automatically submits `AT+CLVL=5` (speaker volume) and `AT^CVOICE=0` during call initiation. If audio is quiet, verify the system volume mixer in Windows.

---

## 5. USSD Returns Error or Times Out

### Symptoms:
Submitting `*124#` or `*110#` fails with `+CUSD: 2` or `Network request timed out`.

### Causes & Fixes:
1. **Carrier DCS encoding variation:**
   - Certain cellular networks require raw GSM 7-bit encoding rather than explicit DCS flags. Dialtone submits standard `AT+CUSD=1,"<code>"`.
2. **Ongoing call or high baseband load:**
   - Ensure you are not currently in a voice call when querying USSD.
3. **Weak signal:**
   - Check signal percentage on the status bar. USSD transactions may fail when signal is below 20% (-95 dBm).

---

## 6. SMS Fails to Send (+CMS ERROR)

### Symptoms:
Sending SMS fails with a `+CMS ERROR: 304` or `+CMS ERROR: 500`.

### Causes & Fixes:
1. **SMS Center (SMSC) number missing on SIM:**
   - Verify SMSC number with `AT+CSCA?`. If empty, set the carrier SMS center address.
2. **Airtime balance exhausted:**
   - Use the **USSD** tab to check if the SIM card has sufficient airtime credit to send SMS messages.
3. **Number formatting:**
   - Always ensure numbers include the appropriate international country code (e.g., `+233...`) or standard local formatting.
