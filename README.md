# FunnyStreamTools

**FunnyStreamTools** is a lightweight, modular, and highly customizable streaming utility designed aesthetic to your live broadcasts. It bridges your streaming platforms (Twitch, Discord, etc.) directly into a beautiful, terminal-inspired overlay for OBS.

## 🚀 Features

* **Modular Architecture**: Easily add new data providers (e.g., YouTube, Discord) and UI plugins without touching the core engine.
* **Terminal Aesthetic**: Features a custom Windows-style CMD terminal overlay with real-time feedback, typewriter effects, and retro sounds.
* **Discord Integration**: Real-time voice activity monitoring via local Discord RPC. No bot tokens required — it hooks directly into your local Discord client.
* **Event-Driven**: Built on an asynchronous event bus, ensuring high performance and low latency for your stream overlays.

## 🛠 Prerequisites

* **Python 3.10+**
* **Discord Desktop App** (Must be running for voice integration)
* **OBS Studio** (To add the browser source overlays)

## 📦 Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/funnystreamtool.git
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

The server will start at `[http://127.0.0.1:8000](http://127.0.0.1:8000)`.

## 📺 Setting up in OBS

1. Open **OBS Studio**.
2. Add a new **Browser Source**.
3. Set the URL to the plugin endpoint:
* **Chat Terminal**: `[http://127.0.0.1:8000/widget/commandchat](http://127.0.0.1:8000/widget/commandchat)`
* **Discord Voice**: `[http://127.0.0.1:8000/widget/discordvoice](http://127.0.0.1:8000/widget/discordvoice)`


4. Set the width and height (e.g., 600x600).
5. Check "Refresh browser when scene becomes active" if desired.

## 🧩 How it works

1. **Providers**: Listen to external APIs (Twitch/Discord) and push events to the `EventBus`.
2. **EventBus**: A central hub that dispatches messages to the appropriate plugins.
3. **Plugins**: WebSocket-based interfaces that render incoming events into web-based UI widgets.

## 🛡 License

This project is open-source and free to use for your streaming needs.

---

*Happy Streaming!*