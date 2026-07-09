# FunnyStreamTools

**FunnyStreamTools** is a lightweight, modular, and highly customizable streaming utility designed to add an aesthetic edge to your live broadcasts. It bridges your streaming platforms (Twitch, Discord, etc.) directly into a beautiful, terminal-inspired overlay for OBS.

---

## 📸 Preview Gallery

<p align="center">
  <img src="doc/picture1.png" width="30%" alt="Overlay Preview 1" />
  <img src="doc/picture2.png" width="30%" alt="Overlay Preview 2" />
  <img src="doc/picture3.png" width="30%" alt="Overlay Preview 3" />
</p>

---

## 🚀 Features

* **Terminal Aesthetic**: Features a custom Windows-style CMD terminal overlay with real-time feedback, typewriter effects, and retro sounds.
* **Ultimate Emote Integration**: Full, built-in support for rendering custom and global emotes from **Twitch**, **7TV**, **BetterTTV (BTTV)**, and **FrankerFaceZ (FFZ)** inside the console chat overlay.
* **Discord Integration**: Real-time voice activity monitoring via local Discord RPC. No bot tokens required — it hooks directly into your local Discord client.
* **Modular Architecture**: Easily add new data providers (e.g., YouTube, Discord) and UI plugins without touching the core engine.
* **Event-Driven**: Built on an asynchronous event bus, ensuring high performance and low latency for your stream overlays.

## 🛠 Prerequisites

* **Python 3.10+**
* **Discord Desktop App** (Must be running for voice integration)
* **OBS Studio** (To add the browser source overlays)

## 📦 Installation

1. **Clone the repository**:
```bash
git clone https://github.com/777Chara777/FunnyStreamTools.git
cd FunnyStreamTools

```

2. **Install dependencies**:

```bash
uv sync

```

## 🚀 Running the App

Start the core engine from the root directory:

```bash
uv run main.py

```

The server will start at `http://127.0.0.1:8000`.

## 📺 Setting up in OBS

1. Open **OBS Studio**.
2. Add a new **Browser Source**.
3. Set the URL to the plugin endpoint:
* **Chat Terminal**: `http://127.0.0.1:8000/widget/commandchat`
* **Discord Voice**: `http://127.0.0.1:8000/widget/discordvoice`


4. Set the desired width and height (e.g., `600x600` or custom terminal dimensions).
5. Check **"Refresh browser when scene becomes active"** if desired.

## 🧩 How it works

1. **Providers**: Listen to external APIs (Twitch/Discord) and push events to the `EventBus`.
2. **EventBus**: A central hub that dispatches messages to the appropriate plugins.
3. **Plugins**: WebSocket-based interfaces that render incoming events into web-based UI widgets with high-performance text and asset handling.

## 🛡 License

This project is open-source and free to use for your streaming needs.

---

*Happy Streaming!*
