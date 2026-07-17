---
id: guides.always-on
layer: operational
type: guide
status: active
owner: shared
updated: 2026-07-17
---

# Keep Your AI Always Running

> [!IMPORTANT]
> **Historical only:** local Nero auto-start is hard-disabled under ADR-0014.
> Do not install or enable any service, scheduled task, login item, Ollama
> process, or project server from this document. Zero-start Codex Host Presence
> requires no local background process.

For your AI to be reachable *at all times*, your PC needs to keep running the
app in the background — ideally starting automatically on boot, and restarting
itself if it ever crashes.

Pick the section for your operating system.

---

## Windows

The simplest reliable approach is **Task Scheduler**.

1. Create a **headless** launcher next to `run.py` called `nero-service.bat`
   with exactly this content:

   ```bat
   @echo off
   cd /d "%~dp0"
   ".venv\Scripts\python.exe" run.py
   ```

   > Use a *separate* file for this — **don't** point the scheduler at the
   > shipped `start.bat`. That one ends with `pause` (great for double-clicking,
   > but under Task Scheduler it would hang forever waiting for a keypress, so
   > the "restart on failure" trigger would never fire). This headless script
   > calls the venv's Python directly, so it also doesn't depend on `python`
   > being on PATH.

2. Open **Task Scheduler** → *Create Task…*
   - **General:** name it `Nero`. Tick *"Run whether user is logged on or not"*.
   - **Triggers:** *New… → Begin the task: At startup*.
   - **Actions:** *New… → Start a program* → browse to your `nero-service.bat`.
   - **Settings:** tick *"If the task fails, restart every 1 minute"*.
3. Save. Nero now starts with Windows and stays up.

> Make sure **Ollama** also starts on boot — its installer sets this up by
> default (check the system tray).

---

## Linux (systemd)

1. Create a service file at `/etc/systemd/system/mbd-ai.service`
   (replace `YOUR_USER` and the paths):

   ```ini
   [Unit]
   Description=mbd-AI personal assistant
   After=network.target

   [Service]
   User=YOUR_USER
   WorkingDirectory=/home/YOUR_USER/mbd-AI
   ExecStart=/home/YOUR_USER/mbd-AI/.venv/bin/python run.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start it:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now mbd-ai
   ```

3. Check it's healthy / view logs:

   ```bash
   systemctl status mbd-ai
   journalctl -u mbd-ai -f
   ```

`Restart=always` means it comes back automatically after a crash or reboot.

---

## macOS (launchd)

1. Create `~/Library/LaunchAgents/com.mbd.ai.plist`:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.mbd.ai</string>
     <key>ProgramArguments</key>
     <array>
       <string>/Users/YOUR_USER/mbd-AI/.venv/bin/python</string>
       <string>/Users/YOUR_USER/mbd-AI/run.py</string>
     </array>
     <key>WorkingDirectory</key><string>/Users/YOUR_USER/mbd-AI</string>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
   </dict>
   </plist>
   ```

2. Load it:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.mbd.ai.plist
   ```

---

## Don't forget

- **Ollama must also be running** for the AI to think. Its installer normally
  configures it to start on boot; verify after a restart.
- If your PC sleeps, it won't be reachable. On a machine acting as an
  always-on server, consider disabling sleep (Windows: *Power & sleep →
  Sleep → Never* while plugged in).
- After a reboot, visit the app once to confirm the status dot is green.
