# SSH Reverse Tunnel: Phone Proxy → Server

When the server (in China, no VPN) needs to access blocked sites, and the user's phone has a working proxy/VPN, use an SSH reverse tunnel to forward the phone's proxy port to the server.

## Setup

**User runs on phone (Termux):**

ssh -R <server_port>:localhost:<phone_proxy_port> root@<server_ip>

**Example (Clash HTTP proxy on port 7890):**

ssh -R 1080:localhost:7890 root@YOUR_SERVER_IP

This makes `localhost:1080` on the server forward to `localhost:7890` on the phone.

## Usage on Server

```bash
# HTTP proxy (works)
curl -x http://localhost:1080 http://httpbin.org/ip

# HTTPS via CONNECT (does NOT work with HTTP proxy tunnel — see pitfalls)
curl -x http://localhost:1080 https://blocked-site.com   # TIMEOUT

# SOCKS5 proxy (if phone proxy is SOCKS5 — preferred for HTTPS)
curl -x socks5://localhost:1080 https://blocked-site.com

# With Python requests
export HTTP_PROXY=http://localhost:1080
export HTTPS_PROXY=http://localhost:1080
python3 -c "import requests; print(requests.get('https://httpbin.org/ip').text)"
```

## Verification

```bash
# 1. Check tunnel port is listening
ss -tlnp | grep 1080
# Should show sshd listening on 127.0.0.1:1080

# 2. Test HTTP (should work, ~30-60s latency)
curl -x http://localhost:1080 -s --connect-timeout 60 http://httpbin.org/ip

# 3. Confirm traffic exits through phone's VPN (IP should differ from server's)
# Expected: origin IP != YOUR_SERVER_IP
```

### FlClash (Android Clash Client) — SSH Tunnel Does NOT Work

**FlClash rejects connections coming through SSH -R tunnels.** Even with "Allow LAN" (允许局域网连接) enabled and the tunnel port listening on the server, FlClash accepts then immediately closes connections (CLOSE-WAIT state). Both HTTP proxy and SOCKS5 protocols fail. This was confirmed with FlClash's default mixed port 7890.

**Root cause**: FlClash appears to filter incoming connections by source, and SSH tunnel forwarded connections (arriving from localhost on the phone) are rejected despite appearing local.

**Workaround**: Use Chisel or similar dedicated tunnel tool (see "Alternative: Chisel" below). Direct SSH tunnel to FlClash is fundamentally broken.

### Termux sshd Approach (Also Unreliable)

Installing `openssh` in Termux and using `ssh -R 1080:localhost:8022` to forward Termux's SSH server also fails. Symptoms:
- Termux sshd sometimes starts but doesn't bind to port 8022 (verify with `netstat -tlnp | grep sshd`)
- Even when sshd is listening, SSH banner exchange times out through the tunnel
- Connections show CLOSE-WAIT state (phone closes connection immediately)
- Debug: `sshd -D -e` runs sshd in foreground with debug output

**Diagnosis steps in Termux:**
```bash
# Check if sshd is actually listening
netstat -tlnp | grep sshd   # if empty, sshd didn't bind
# Kill and restart with debug
pkill sshd && sshhd -D -e   # should show "Server listening on :: port 8022"
```

## Alternative: Chisel (Recommended)

Chisel is a dedicated TCP/UDP tunnel tool that creates a SOCKS5 proxy on the server, routing traffic through the phone. More reliable than SSH tunnels for this use case.

**Setup:**
```bash
# Termux on phone
pkg install golang
go install github.com/jpillora/chisel@latest

# Server
chisel server -p 8080 --socks5

# Phone (connects to server, creates reverse SOCKS proxy)
chisel client SERVER_IP:8080 R:socks
```

Server then uses `localhost:1080` as SOCKS5 proxy. Traffic exits through phone's VPN.

**Note:** Chisel was identified as the recommended approach but not fully tested in the session that documented this.

**FlClash reference info:**
- Default mixed port: 7890 (HTTP + SOCKS5 on same port)
- Global mode (全局) vs Rule mode (规则): switching may drop the tunnel, require reconnect
- "Allow LAN" setting: found in network settings, but does NOT fix the SSH tunnel rejection issue
- RESTful API port: 9090

## Common Phone Proxy Ports

| App | Default Port | Type |
|-----|-------------|------|
| Clash | 7890 | HTTP |
| Clash for Android | 7890 | HTTP |
| V2RayNG | 10808 | SOCKS5 |
| Shadowsocks | 1080 | SOCKS5 |
| Surge | 6152 | HTTP |

## Pitfalls

### HTTPS CONNECT Does NOT Work Through HTTP Proxy Tunnel

Clash (and similar) in HTTP proxy mode does NOT support the CONNECT method from external connections. Plain HTTP requests work, but HTTPS requests (which use CONNECT to tunnel) will time out after ~2 minutes. Since most sites are HTTPS, this severely limits usefulness.

**Workaround**: Configure the proxy app to also expose a SOCKS5 port, then forward that instead — SOCKS5 handles HTTPS CONNECT natively. Check Clash settings for a separate SOCKS port (often 7891 or configurable).

### Very High Latency

Expect 30-60 seconds per request through the tunnel (phone mobile network → proxy → target). Not suitable for high-frequency scraping or interactive use.

### `ssh -D` Does NOT Create a Server-Side SOCKS Proxy

Common mistake: `ssh -D 1080 root@server` creates a SOCKS proxy on the CLIENT (phone) side, not the server. The server can't use it. Always use `ssh -R` to forward the phone's proxy port to the server.

### Tunnel Drops on Sleep

Android may kill Termux when screen off. User should:
1. Install termux-api: `pkg install termux-api`
2. Enable wakelock: `termux-wake-lock`
3. Or keep screen on while tunnel is needed

### SSH Keepalive

Add keepalive flags to prevent idle disconnection:

ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 1080:localhost:7890 root@SERVER_IP

### Proxy Type Mismatch

If phone proxy is HTTP but curl uses `socks5://`, it won't work. Always match the type to the phone's proxy protocol.

### Clash Exclude Domains List

Proxy apps like Clash have "exclude domains" (排除域名) lists that bypass the proxy for matching domains. Private IP ranges (10.*, 172.16-31.*, 192.168.*) are typically excluded by default but don't affect the tunnel since the server uses a public IP.

## Full Command Template

ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R <server_port>:localhost:<phone_proxy_port> root@<server_ip>
