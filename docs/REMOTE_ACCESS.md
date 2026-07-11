# Reach Your AI From Anywhere (Securely)

You want to talk to your AI **on any network, anytime** — but *without* exposing
it to the public internet or sending your data through anyone else's servers.

The clean way to do this is **Tailscale**: it builds a small private, encrypted
network between *your own devices*. Your PC keeps hosting the AI locally; your
phone and laptop connect to it directly, as if you were sitting at home — even
over cellular or a coffee-shop Wi-Fi.

Your data never leaves your devices. There are no ports to open and nothing is
exposed publicly.

---

## One-time setup (about 10 minutes)

### 1. Install Tailscale on your PC (the one running the AI)

1. Download from **https://tailscale.com/download**.
2. Sign in (Google/Microsoft/GitHub account works).
3. After it connects, find your PC's Tailscale address:

   ```bash
   tailscale ip -4
   ```

   You'll get something like `100.101.102.103`. That address is stable and only
   works for your own logged-in devices.

### 2. Install Tailscale on your phone / laptop

- **Phone:** install the Tailscale app (App Store / Play Store), sign in with the
  **same account**.
- **Laptop:** same installer as above, same account.

That's it — all your devices are now on the same private network.

### 3. Make sure the AI is listening on the network

In `config.yaml`, keep:

```yaml
host: "0.0.0.0"
port: 8080
```

`0.0.0.0` means "accept connections from my Tailscale network" (not just this
one computer). Restart `python run.py` if you changed it.

### 4. Connect from anywhere

With Tailscale running on both devices, open this on your phone or laptop:

```
http://100.101.102.103:8080
```

(using **your** PC's Tailscale IP from step 1). You're now talking to your
home AI from anywhere. 🎉

> **Tip — a friendlier address.** Turn on *MagicDNS* in the Tailscale admin
> console and you can use your PC's name instead of the IP, e.g.
> `http://my-pc:8080`.

---

## Add it to your phone's home screen (feels like a real app)

- **iPhone (Safari):** open the address → Share → *Add to Home Screen*.
- **Android (Chrome):** open the address → ⋮ menu → *Add to Home screen*.

Now it launches full-screen with its own icon, like any other app.

---

## Security notes

- Only devices signed into **your** Tailscale account can reach the AI.
- Traffic between your devices is end-to-end encrypted by Tailscale.
- Nothing is exposed to the public internet; there are no open firewall ports.
- The model and all your data stay on your PC.

For this to work when you're away, your PC needs to be **on and running the app**
— see **[ALWAYS_ON.md](ALWAYS_ON.md)** to keep it running automatically.
