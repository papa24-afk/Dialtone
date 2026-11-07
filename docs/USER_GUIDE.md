# Dialtone User Guide

This guide walks you through connecting your hardware, configuring your audio devices, and making calls, sending SMS messages, and executing USSD queries with Dialtone.

---

## Table of Contents
1. [Overview of the Interface](#1-overview-of-the-interface)
2. [Connecting Your USB Modem](#2-connecting-your-usb-modem)
3. [Making & Receiving Calls](#3-making--receiving-calls)
4. [Sending & Receiving SMS](#4-sending--receiving-sms)
5. [USSD Services & Balance Queries](#5-ussd-services--balance-queries)
6. [Managing Contacts](#6-managing-contacts)
7. [Configuring Audio Devices](#7-configuring-audio-devices)

---

## 1. Overview of the Interface

Dialtone features a dark-themed, desktop interface designed for cellular management:

- **Top Status Bar:** Displays the connected modem model, active cellular carrier, network technology (e.g., 3G HSPA+), signal strength percentage, and the active Windows audio output device.
- **Left Navigation Bar:** Seamless switching between **Home**, **Calls**, **Messages**, **USSD**, **Contacts**, **Devices**, **Audio**, and **Settings**.
- **Home Dashboard:** Quick dials, recent call and message activity, and carrier service shortcuts (*124#, *110#, etc.).

---

## 2. Connecting Your USB Modem

1. Insert your active SIM card into your USB cellular modem.
2. Plug the USB modem into an available USB port on your Windows PC.
3. Launch Dialtone.
4. Dialtone will automatically scan available COM ports:
   - When detected, the top status badge turns from amber (`Searching for Modem...`) to green with your carrier name (e.g., `Telecel`, `Vodafone`, `MTN`).
   - If the modem is plugged in as a virtual CD drive or storage device, Dialtone will trigger the hardware mode-switch to expose the serial and voice interfaces.

---

## 3. Making & Receiving Calls

### Outgoing Calls
1. Navigate to the **Calls** tab from the left sidebar.
2. Use the on-screen keypad or your computer's keyboard to enter the target phone number.
3. Click the green **Call** button.
4. The call card will appear showing:
   - Call state: `DIALING` -> `RINGING` -> `CONNECTED`.
   - Live call duration timer.
   - Contact name (if saved in Contacts).
5. During an active call, you can:
   - **Mute / Unmute** your microphone.
   - **Put Call on Hold** / **Resume**.
   - Send in-call **DTMF tones** (touch tones for automated phone systems).
   - Click **End Call** to terminate the connection.

### Incoming Calls
1. When an incoming cellular call arrives, Dialtone rings and displays the caller ID popup with the caller's phone number or contact name.
2. Click **Answer** to connect the call and start the PC audio stream, or **Decline** to send a busy/hangup command.

---

## 4. Sending & Receiving SMS

1. Navigate to the **Messages** tab.
2. Select an existing conversation thread from the list or click **New Message**.
3. Type the recipient's phone number and message body.
4. Click **Send** (or press Enter).
5. Inbound SMS messages are automatically received, alerted in the application, and grouped into chronological conversation threads.

---

## 5. USSD Services & Balance Queries

USSD is crucial for checking airtime balances, buying data bundles, and accessing mobile banking in many countries:

1. Navigate to the **USSD** tab.
2. Enter the carrier USSD code (e.g., `*124#` for airtime balance or `*110#` for mobile money).
3. Click **Send**.
4. The carrier's response will render in the terminal window:
   - **Single-response inquiries:** Displays the network reply text.
   - **Interactive multi-step menus:** If the carrier presents a numbered menu, an interactive reply input will appear. Type your selection (e.g., `1`) and submit.
5. Click **Cancel Session** if you wish to exit the USSD session early.

---

## 6. Managing Contacts

1. Navigate to the **Contacts** tab.
2. View your saved phonebook, complete with search and category tags.
3. Click **Add Contact** to save a new name, phone number, category, and notes.
4. Click on any contact card to initiate a direct call or open their SMS conversation.

---

## 7. Configuring Audio Devices

1. Navigate to the **Audio** tab.
2. Select your preferred **Speaker / Headphone device** from the drop-down.
3. Select your preferred **Microphone input device**.
4. Adjust speaker and microphone volume sliders.
5. Check real-time **Audio Engine Diagnostics**:
   - Sample rate: 8000 Hz 16-bit Mono PCM.
   - Buffer depth, RX/TX byte counters, and frame transmission health.
