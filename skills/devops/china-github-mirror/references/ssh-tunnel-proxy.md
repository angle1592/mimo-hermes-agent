# Phone-to-Server Proxy: Getting Internet Access on a China Cloud Server

When the cloud server has no VPN/proxy but the user's phone does, there are two approaches. **Approach 1 (direct install) is strongly recommended.**

## Approach 1: Install Proxy Client Directly on Server — Recommended

The most reliable solution: install mihomo (Clash Meta) on the server and use the user's Clash subscription URL.

### Steps

1. **Download mihomo** (GitHub releases are blocked in China, use ghfast.top mirror):
   ```bash
   curl -sL "https://ghfast.top/https://github.com/MetaCubeX/mihomo/releases/download/v1.19.8/mihomo-linux-amd64-v1.19.8.gz" -o /tmp/mihomo.gz
   cd /tmp && gunzip -f mihomo.gz && chmod +x mihomo && mv mihomo /usr/local/bin/
   ```

2. **Fetch subscription config** (needs specific User-Agent — see pitfalls):
   ```bash
   mkdir -p /etc/mihomo
   curl -sL -A "clash-verge/v2.0.0" "SUBSCRIPTION_URL" -o /etc/mihomo/config.yaml
   ```

3. **Verify config has nodes**:
   ```bash
   grep -c "server:" /etc/mihomo/config.yaml  # Should be > 0
   ```

4. **Run mihomo**:
   ```bash
   mihomo -d /etc/mihomo
   ```
   Mixed proxy listens on `[::]:7890` by default (both HTTP and SOCKS5).

5. **Test**:
   ```bash
   curl -x http://localhost:7890 -s https://www.google.com -o /dev/null -w "%{http_code}"
   curl -x http://localhost:7890 -s https://httpbin.org/ip
   ```

6. **Optional: systemd service** for auto-start on boot.

### Why this beats SSH tunnels
- No phone dependency — works 24/7 without phone being online
- Stable — no mobile network drops, sleep issues
- Fast — direct connection from server to proxy nodes
- Simple — no Termux, no sshd config, no tunnel debugging

## Approach 2: SSH Tunnel (Phone → Server) — Unreliable, Last Resort

**⚠️ WARNING: SSH port forwarding with Termux is unreliable.** Extensive testing (2026-05) shows:
- SSH `-R` port forwarding establishes the tunnel (port listens on server) but connections through it result in CLOSE-WAIT state — the phone side closes connections immediately
- Termux's sshd sometimes fails to listen on its port after `sshd` command (no error shown, no port bound)
- Even when tunnel works, it's intermittent — may succeed once then fail on subsequent attempts
- FlClash proxy rejects connections coming through SSH tunnels
- Root cause unclear: likely Termux sshd limitation with reverse port forwarding

**If you must try SSH tunnel:**

```bash
# On phone (Termux):
pkg install openssh
sshd
ssh -R 1080:localhost:7890 root@SERVER_IP

# On server, test:
curl -x http://localhost:1080 -s https://www.google.com
```

## Pitfalls

- **Clash subscription URLs need specific User-Agent** — Generic UA (or none) returns 403 or empty `proxies: []`. Use `-A "clash-verge/v2.0.0"`. Test with `grep -c "server:" config.yaml` to verify nodes are present. `ClashForAndroid/2.5.12` may return empty proxies.
- **GitHub downloads blocked in China** — Use `https://ghfast.top/<original-url>` as proxy prefix. Alternatives: `https://mirror.ghproxy.com/`, `https://gh-proxy.com/`.
- **mihomo config format** — The subscription returns Clash Meta (mihomo) format, not standard Clash. Use mihomo as the client, not original Clash.
- **Mixed port** — mihomo's default `mixed-port: 7890` supports both HTTP and SOCKS5 on the same port.
- **mihomo listens on `[::]:7890`** (all interfaces) by default when `allow-lan: true` in config. Fine for server use but be aware of security implications.
- **Phone proxy app must be active** for SSH tunnel approach — VPN badge should show in status bar.
