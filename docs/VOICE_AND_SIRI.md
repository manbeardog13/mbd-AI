# Talking To Your AI (Voice & "Hey Siri")

You want to reach your AI *like Siri* — instantly, by voice, no fuss. There are
two layers to that, and you can use either or both.

| Layer | What it gives you | Where it works |
|-------|-------------------|----------------|
| **In-app voice** | Tap 🎤 to talk; it reads replies aloud | Desktop & Android (mic needs HTTPS — see below). Speaking-aloud works everywhere, including iPhone. |
| **Siri Shortcut** | *"Hey Siri, ask Niro…"* — fully hands-free | iPhone / iPad / Apple Watch |

---

## Layer 1 — In-app voice

In the web app's left panel, under **Voice**, you'll find:

- **Speak replies aloud** — your AI reads its answers to you. Works on every
  device, including iPhone, over plain HTTP.
- **Hands-free (auto-listen after each reply)** — after it finishes speaking,
  the mic re-opens automatically so you can just keep talking. A real
  back-and-forth conversation.

And in the message bar, the **🎤 mic button** lets you talk instead of type.

### Enabling the mic over Tailscale (one-time)

Browsers only allow microphone access on a **secure (HTTPS)** page. On your own
PC `http://localhost:8080` counts as secure, so the mic works there right away.
But over Tailscale you're using an `http://100.x.x.x` address, which browsers
treat as insecure — so the mic stays hidden until you turn on HTTPS.

Good news: **Tailscale gives you free HTTPS** with one command. On the PC
running the AI:

```bash
# Puts your local app behind a real HTTPS address on your tailnet
tailscale serve --bg 8080
```

Now visit the HTTPS address Tailscale prints — something like:

```
https://your-pc.your-tailnet.ts.net
```

On *that* address the 🎤 mic works from your phone and laptop anywhere. (The
"speak replies aloud" feature works with or without this.)

> To see the address any time: `tailscale serve status`.
> To turn it off: `tailscale serve --https=443 off`.

---

## Layer 2 — The Siri Shortcut ("Hey Siri, ask Niro…")

This is the closest thing to real Siri. You say a phrase, dictate your question
using the iPhone's own voice recognition, your AI answers, and your phone speaks
it back — without opening anything.

### Build it once (about 5 minutes)

1. Open the **Shortcuts** app on your iPhone → tap **+** to create a new shortcut.
2. Add these actions in order:

   **① Dictate Text**
   - Search actions for *"Dictate Text"* and add it. (This captures your voice.)

   **② Get Contents of URL**
   - Search for *"Get Contents of URL"* and add it.
   - **URL:** your AI's address, ending in `/api/chat`. For example:
     `https://your-pc.your-tailnet.ts.net/api/chat`
     (Use your Tailscale HTTPS address from Layer 1, or your `http://100.x.x.x:8080`
     address — both work for Shortcuts.)
   - Tap **Show More** and set:
     - **Method:** `POST`
     - **Headers:** add one → key `Content-Type`, value `application/json`
     - **Request Body:** `JSON`
       - Add a field → key `message`, type **Text**, value = the **Dictated Text**
         variable (tap the field, pick the magic variable from step ①).

   **③ Speak Text**
   - Search for *"Speak Text"* and add it.
   - Set its input to the **Contents of URL** variable (the reply from step ②).

3. Tap the shortcut's name at the top and rename it to something Siri-friendly,
   like **"Ask Niro"** (use your AI's actual name).
4. Done. Now say: **"Hey Siri, Ask Niro"** → speak your question → hear the answer.

> **Tip:** Add the shortcut to your Home Screen or Lock Screen for a one-tap
> button too (share icon → *Add to Home Screen*).

### Requirements

- Tailscale must be connected on your iPhone (so it can reach your PC).
- Your PC must be on and running the app (see **ALWAYS_ON.md**).
- Using an `https://…ts.net` URL is smoother than `http://` inside Shortcuts —
  set that up via Layer 1.

---

## Which should I use?

- **On your iPhone, day to day:** the **Siri Shortcut** — it's the real
  hands-free "assistant" experience.
- **At your desk or on Android:** the **in-app mic + speak-aloud**, ideally with
  **hands-free** mode on for a flowing conversation.

Both talk to the exact same AI with the same memory, so it doesn't matter which
one you use — it's always the same companion.
