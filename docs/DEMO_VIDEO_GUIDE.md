# Dialtone — YouTube Demonstration Video Guide & Production Script

This document provides a comprehensive, production-ready blueprint for creating a professional YouTube product demonstration for **Dialtone**.

> **Cardinal Rule for This Demonstration:**  
> Use **genuine application footage and physical hardware only**. Never simulate phone calls, fabricate network responses, or claim unsupported features. Technical precision and transparency build long-term trust with the developer and telecom community.

---

## 1. YouTube Video Metadata

### Suggested Video Titles (Choose One)
- **Option 1 (Direct & Search-Optimized):**  
  `How to Make Calls, Send SMS & Query USSD with a USB Modem on Windows 11 (Dialtone Demo)`
- **Option 2 (Alternative-Focused):**  
  `Replacing Huawei Mobile Partner in 2026: Voice Calls & USSD on Windows 11 with Dialtone`
- **Option 3 (Product Showcase):**  
  `Dialtone: Open-Source Desktop Cellular Suite for USB Modems (Complete Walkthrough)`

### Suggested Video Description
```text
Turn your USB cellular modem into a full-featured desktop phone and messaging station on Windows 10 & 11!

In this video, we demonstrate Dialtone — an open-source desktop application that unlocks cellular voice calling, threaded SMS messaging, and interactive USSD services (*124#, *110#) using standard USB modems.

Tested hardware in this video:
• Modem: Huawei K4201 (Vodafone K4201-I) HSPA+ USB Stick
• Carrier: Telecel Ghana (3G HSPA+)
• Host PC: HP EliteBook x360 1040 G7 (Windows 11 Pro 64-bit)

Timestamps:
0:00 - The Problem: Why Windows Only Uses Modems for Data
0:45 - The Hardware: Huawei K4201 USB Modem & SIM
1:35 - Connecting to PC & Mode Switching
2:40 - Device Manager & COM Port Verification
3:30 - Dialtone Interface & Live Cellular Telemetry
4:45 - Live Hardware Demo: Real-Time USSD Balance Check (*124#)
6:10 - Live Hardware Demo: SMS Messaging & Inbox
7:15 - Live Hardware Demo: Voice Telephony & 16-Bit PCM Audio Engine
8:50 - Standalone Installation & Zero-Setup Portability
10:00 - Open Source Project, Roadmap & How to Contribute

Links & Resources:
 GitHub Repository: https://github.com/papa24-afk/Dialtone
 Releases & Downloads: https://github.com/papa24-afk/Dialtone/releases
 Documentation & Supported Modems: https://github.com/papa24-afk/Dialtone/blob/main/docs/SUPPORTED_MODEMS.md

#USBModem #HuaweiModem #Windows11 #Cellular #USSD #OpenSource #Telephony #Dialtone
```

### Video Tags
`dialtone, usb modem voice call, huawei usb modem, huawei mobile partner alternative, windows 11 usb modem, ussd reader pc, send sms from pc usb modem, huawei k4201, voice over usb, pcm audio com port, telecel ghana, cellular desktop, electron cellular, at commands modem`

---

## 2. Pre-Recording Checklist

### Hardware Preparation
- [ ] **Laptop:** HP EliteBook x360 1040 G7 plugged into AC power (to prevent power-saving throttling).
- [ ] **Modem:** Huawei K4201 with an active, unlocked SIM card inserted (PIN code disabled).
- [ ] **Audio Headset:** Use a USB or 3.5mm headset with microphone connected to the laptop (prevents acoustic feedback during call testing).
- [ ] **Secondary Phone:** A mobile phone ready to test incoming/outgoing calls or SMS.

### Screen Recording Setup (OBS Studio recommended)
- [ ] **Canvas Resolution:** 1920x1080 @ 60 FPS (1080p) or 2560x1440 (1440p).
- [ ] **Display Scale:** Windows Display Scaling set to 100% or 125% for crisp UI readability.
- [ ] **Audio Capture:**
  - Track 1: Microphone (Voiceover narration).
  - Track 2: Desktop Audio (System sounds and Dialtone audio).
- [ ] **Camera / B-Roll (Optional but recommended):** Smartphone or camera positioned to record physical insertion of the USB modem into the laptop.

### Privacy & Redaction Prep
- [ ] **Phone Numbers:** Ensure any personal contact numbers you do not want publicly visible on YouTube are blurred in post-production or replaced with test/carrier service numbers (e.g., `100`, `*124#`, `*110#`).
- [ ] **Desktop Cleanup:** Hide unnecessary desktop icons, close browser personal tabs, and turn on Windows Do Not Disturb / Focus Assist.

---

## 3. Scene-by-Scene Storyboard & Script

### Scene 1: Introduction & The Problem (0:00 – 0:45)
- **Visual:** Host talking to camera or screen showing a plugged-in USB modem with Windows Cellular showing "Getting ready..." or standard data connection.
- **On-Screen Text Callout:** *The Problem: Windows treats USB modems as data-only cards.*
- **Spoken Script:**
  > *"Have you ever plugged a cellular USB modem into your Windows laptop and wondered why you can only browse the internet? Even though your SIM card has call credit, SMS bundles, and mobile money services, Windows treats the modem strictly as a data adapter. Voice calling, USSD balance queries, and SMS are completely locked out.*  
  > *In the past, people used software like Huawei Mobile Partner, but that was discontinued years ago and doesn't run reliably on modern 64-bit Windows 11.*  
  > *Today, I'm introducing **Dialtone** — a modern, open-source desktop application that turns standard USB cellular modems into a full-fledged telephony, SMS, and USSD workstation on Windows 10 and 11."*

---

### Scene 2: The Hardware Showcase (0:45 – 1:35)
- **Visual:** Close-up camera shot (or clear high-res photos) of the **Huawei K4201** (Vodafone K4201-I) USB modem. Show opening the cover, showing the SIM card slot, and sliding in the active SIM card.
- **On-Screen Text Callout:** *Hardware Profile: Huawei K4201 HSPA+ USB Stick (Balong V3R2 / Qualcomm baseband).*
- **Spoken Script:**
  > *"Here is our test hardware: this is the Huawei K4201, branded as the Vodafone K4201-I. It's a standard 3G HSPA+ USB dongle. Inside, we have an active SIM card from Telecel Ghana with active voice, SMS, and airtime balance.*  
  > *What makes this dongle interesting is that its internal baseband chip has hardware support for 16-bit 8000Hz PCM voice audio streams over a secondary serial port. Dialtone leverages this baseband capability directly."*

---

### Scene 3: Connecting & Windows Enumeration (1:35 – 2:40)
- **Visual:** Footage of inserting the USB modem into the HP EliteBook x360. Screen recording showing Windows detecting the device.
- **On-Screen Text Callout:** *Automated Mode Switching: Storage (CDFS) → Composite Serial Mode (`PID 14FB`).*
- **Spoken Script:**
  > *"When you insert a cellular dongle into Windows, it typically powers up in mass storage or virtual CD-ROM mode. Dialtone includes an automated SCSI pass-through switcher that detects the storage drive and sends the vendor eject sequence, switching the modem into composite serial mode.*  
  > *Furthermore, Dialtone can permanently program the modem's onboard NVRAM using `AT^SETPORT="A1,A2;1,2,3"`. Once programmed, the dongle powers up directly into Voice and Serial mode on any PC you plug it into."*

---

### Scene 4: Device Manager & Port Verification (2:40 – 3:30)
- **Visual:** Open Windows Device Manager (`Win + X` -> Device Manager). Expand **Ports (COM & LPT)**. Highlight `USB Serial Device (COM7)` and `USB Serial Device (COM6)`.
- **On-Screen Text Callout:**  
  - *COM7: 3G Modem & AT Command Port (Commands, SMS, USSD)*  
  - *COM6: PC UI & 16-bit 8000Hz PCM Voice Streaming*
- **Spoken Script:**
  > *"Let's verify this in Windows Device Manager. Under Ports, we can see two active serial devices powered by Microsoft's built-in `usbser.sys` driver: COM7, which handles AT commands for network queries, SMS, and dialing; and COM6, which carries raw bi-directional PCM audio frames directly to and from the modem's baseband DSP."*

---

### Scene 5: Dialtone Interface & Live Telemetry (3:30 – 4:45)
- **Visual:** Launch `CellularPC.exe`. The dark-themed Dialtone UI opens instantly. Show the top status bar transitioning from amber to green.
- **On-Screen Text Callout:** *Real-time SSE Telemetry: CSQ 22 (~71% Signal) • 3G HSPA+ • Telecel Ghana.*
- **Spoken Script:**
  > *"Now let's launch Dialtone. Notice how quickly the application loads. Immediately, Dialtone's background engine connects to the modem. Look at the status bar at the top:*  
  > *It identifies our hardware — Huawei K4201 — connected to the Telecel network in 3G HSPA+ mode, with a live signal strength of around 71% (-69 dBm).*  
  > *On the left, we have clean navigation: Home, Calls, Messages, USSD, Contacts, Devices, Audio Diagnostics, and Settings."*

---

### Scene 6: Live Demonstrations of Supported Features (4:45 – 7:45)

#### Demo Part A: Live USSD Balance Query (4:45 – 6:10)
- **Visual:** Click on the **USSD** tab. Type `*124#` into the input bar. Click **Send**. Show the live response popping up in under 3 seconds.
- **On-Screen Text Callout:** *Live 3GPP USSD Session: Instant Airtime & CUG Quota Response.*
- **Spoken Script:**
  > *"Let's test one of the most critical features for prepaid mobile users: USSD. In many countries, USSD is essential for checking airtime and accessing mobile money.*  
  > *I'll type `*124#`, the standard balance inquiry code for Telecel Ghana, and hit Send.*  
  > *In less than 3 seconds, the network responds directly in Dialtone's terminal: we can see our live airtime balance, account validity, and CUG call minutes.*  
  > *Dialtone also handles multi-step interactive USSD menus, allowing you to reply with numbers to navigate carrier menus like mobile cash."*

#### Demo Part B: SMS Messaging & Inbox (6:10 – 7:15)
- **Visual:** Click on the **Messages** tab. Show conversation threads. Open a thread or click **New Message**. Type a test message and send it, or show receiving an SMS notification.
- **On-Screen Text Callout:** *3GPP AT Text Mode (`AT+CMGF=1`) with SIM Card Synchronization.*
- **Spoken Script:**
  > *"Next is SMS messaging. Dialtone operates in standard 3GPP text mode. On startup, it automatically syncs any messages stored on the SIM card and groups them into clean conversation threads.*  
  > *You can compose messages, view timestamps, and receive inbound SMS notifications in real-time without leaving your desktop."*

#### Demo Part C: Voice Telephony & PCM Audio Pipeline (7:15 – 8:50)
- **Visual:** Click on the **Calls** tab. Show the full numeric dialpad. Show dialing customer support (`100`) or a test number. Click Call.
- **Visual Overlay:** Show the **Audio** tab with live diagnostic meters (TX/RX byte counters, 8000Hz 16-bit Mono, buffer latency).
- **On-Screen Text Callout:** *Direct Win32 Multimedia Integration (`waveOut`/`waveIn`) via COM6 PCM.*
- **Spoken Script:**
  > *"Now for voice calling. On the Calls screen, we have a complete dialpad with contact matching. When I initiate a call, Dialtone submits the AT dial command, commands the baseband to activate voice routing with `AT^DDSETEX=2`, and opens a 16-bit 8000Hz mono PCM audio pipeline through Windows Multimedia `waveOut` and `waveIn`.*  
  > *Over in the Audio settings tab, you can see real-time diagnostics: transmission counters, buffer latency, and hardware levels.*  
  > *Please note: because this is direct PCM audio streaming over serial, we strongly recommend using headphones during calls to prevent acoustic microphone feedback while software echo cancellation is in development."*

---

### Scene 7: Zero-Setup Portability (8:50 – 10:00)
- **Visual:** Show the `Dialtone-Portable.zip` on the Windows Desktop. Extract the folder. Open the folder and double-click `CellularPC.exe`. It launches instantly.
- **On-Screen Text Callout:** *Self-Contained: Zero Python installation, zero terminal commands, 100% offline.*
- **Spoken Script:**
  > *"One of the biggest strengths of Dialtone is its portability. You don't need to install Python, configure virtual environments, or run terminal commands.*  
  > *We've compiled the entire backend modem bridge into a native 64-bit Windows executable bundled directly inside the release package. You simply download the zip, extract it to any folder on your laptop, and double-click `CellularPC.exe`. It runs completely offline with zero external cloud dependencies."*

---

### Scene 8: Open Source, Roadmap & Outro (10:00 – 10:45)
- **Visual:** Open browser showing the GitHub repository: `https://github.com/papa24-afk/Dialtone`. Scroll through the README, documentation links, and Releases page.
- **On-Screen Text Callout:** *Open Source (MIT) • Contributions Welcome • Link in Description.*
- **Spoken Script:**
  > *"Dialtone is 100% free and open-source under the MIT license. You can find the complete source code, installation guides, and hardware documentation on GitHub at `github.com/papa24-afk/Dialtone`.*  
  > *We have detailed guides for supported chipsets, troubleshooting driver modes, and a community issue template where you can submit compatibility reports for your own USB modems.*  
  > *If you found this project helpful, please star the repository on GitHub, leave a like on this video, and drop a comment with the modem models you'd like to see tested next.*  
  > *Thank you for watching, and enjoy using Dialtone!"*

---

## 4. Post-Recording Editing Tips

1. **Audio Normalization:**  
   Apply a compressor/limiter to your voiceover track to keep audio clear between -3dB and -1dB.
2. **Zoom & Pan on Key Areas:**  
   When showing USSD terminal text and Device Manager COM port numbers, use a smooth 130% zoom in your video editor so mobile viewers can read the small text easily.
3. **Privacy Blur Check:**  
   Double-check that no private phone numbers, SIM IMSI numbers, or personal contacts were accidentally shown during the live demo.
4. **Thumbnail Concept:**  
   - Left side: High-contrast photo of the Huawei USB modem plugged into the laptop edge.
   - Right side: Crop of the sleek dark-mode Dialtone dialpad with a glowing green "Call" button and a badge saying *"USSD + Voice Calls on Windows 11"*.
