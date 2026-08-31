# 👑 Elite Music API & Bot Ecosystem

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Aiogram 3.x](https://img.shields.io/badge/Aiogram-3.x-2CA5E0.svg)](https://docs.aiogram.dev)
[![PyTgCalls](https://img.shields.io/badge/PyTgCalls-NTgCalls-FF5722.svg)](https://pytgcalls.github.io)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)]()

> **The Premier Ultra-Low-Latency Telegram Voice Chat Audio & Video Streaming Engine.**  
> Powered by 7 Hot-Standby Priority MTProto Userbots, JioSaavn 320kbps Lossless CDN Extraction, Real-Time Live DSP Biquad Filters, Self-Service Bot Cloning, and Automated Cross-Bot Database Telemetry.

---

## 🌟 Core Features

- 🎵 **Lossless 320kbps Audio Pipeline**: Direct uncompressed 48 kHz stereo PCM streaming with zero buffering.
- 🎛️ **Real-Time Live DSP Equalizer**:
  - 🔥 **Bass Boost**: 4-pole biquad low-shelf filter (+6dB to +12dB).
  - 🎧 **8D Spatial Audio**: True binaural rotating acoustic soundfield.
  - ⚡ **Tempo / Speed**: Pitch-compensated audio time-stretching (1.0x, 1.2x, 1.5x).
- 🤖 **Self-Service Bot Clone Engine**: Turn any Bot Token from `@BotFather` into an independent music bot in 3 seconds.
- 🗄️ **Unified Analytics & User Capture**: Automatically indexes every DM user and added supergroup across main and cloned bots.
- 📢 **Mass Broadcasting Engine (`/broadcast` & `/gcast`)**: Global and clone-specific broadcast capabilities with flood control.
- 📥 **Telegram Audio File & Voice Note Playback**: Reply to any uploaded MP3, voice message, or audio document with `/play` to stream directly into Voice Chat.
- 🛡️ **Automated Group Join Request Approval**: Automatically approves assistant userbots when joining restricted supergroups.
- 🧹 **Dynamic Glassmorphic Cards & Zero-Clutter TTL**: High-resolution 1200x630 player cards with automated transient message self-destruction.

---

## 📜 Complete Command Reference

| Command | Scope | Description |
| :--- | :--- | :--- |
| `/start` | DM / Groups | Start bot, view banner, and access main control deck |
| `/play <query/url>` | Groups | Stream audio track or URL in Voice Chat |
| Reply with `/play` | Groups | Stream replied audio, voice message, or document |
| `/pause` | Groups | Pause current Voice Chat playback |
| `/resume` | Groups | Resume paused playback |
| `/skip` | Groups | Skip to the next queued track |
| `/stop` | Groups | Stop playback and release assistant userbot |
| `/queue` | Groups | View upcoming queued songs and playback state |
| `/bass [on\|off\|dB]` | Groups | Toggle Bass Boost (+6dB default) |
| `/8d [on\|off]` | Groups | Toggle 8D Spatial Binaural Audio |
| `/speed [1.0\|1.2\|1.5]` | Groups | Scale playback tempo and speed |
| `/clone` | DM | Create and connect your personal music bot |
| `/help` / `/faq` | DM / Groups | Interactive knowledge hub and troubleshooting guide |
| `/stats` | DM / Groups | System load, active streams, and assistant telemetry |
| `/broadcast <msg>` | DM (Admin) | Broadcast message to all tracked DM users |
| `/gcast <msg>` | DM (Admin) | Broadcast message to all tracked supergroups |

---

## 🏗️ Architecture Overview

```
[ Telegram Groups & DMs ]
          │
          ▼
 [ Aiogram 3.x Bot Daemon & Clones ]
          │
          ▼ (HTTP REST API / Python SDK)
 [ FastAPI Gateway & Room Manager (Port 8000) ]
          │
          ├──> [ JioSaavn / YouTube / Media Extractor ]
          ├──> [ SQLite / PostgreSQL Database & Analytics ]
          ├──> [ Redis Token-Bucket Rate Limiter & DSP State ]
          └──> [ 7-Assistant Hot-Standby Session Pool ]
                        │
                        ▼ (PyTgCalls / NTgCalls WebRTC)
               [ Telegram Voice Chats ]
```

---

## ⚡ Deployment & Service Management

```bash
# Restart API and Bot Daemons
sudo systemctl restart elitemusic-api elitemusic-bot

# Check Status
sudo systemctl status elitemusic-api elitemusic-bot

# Tail Live Journal Logs
journalctl -u elitemusic-bot -f
```

---

⚡ *Powered by* [**Elite Bots**](https://t.me/EliteBotsTelegram)
