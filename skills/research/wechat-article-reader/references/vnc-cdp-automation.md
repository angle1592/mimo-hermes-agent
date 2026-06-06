# VNC + CDP Browser Automation Pattern

The server has a persistent Chromium instance accessible via VNC and CDP. Use this for tasks requiring persistent login sessions (Bilibili, etc.) where Browserbase sessions expire too quickly.

## Architecture
```
Xvnc :99 (display :99)
  └── Chromium (CDP on :9222)
        └── websockify :6080 → noVNC (visual monitoring)
```

## Access Points
- **noVNC (visual)**: http://YOUR_SERVER_IP:6080/vnc.html
- **CDP (programmatic)**: http://localhost:9222
- **VNC direct**: port 5900

## CDP Workflow (Python + websockets)

### List tabs
```bash
curl -s http://localhost:9222/json/list
```

### Open new tab
```bash
curl -s -X PUT "http://localhost:9222/json/new?https://example.com"
```

### Interact via websocket
```python
import asyncio, json, websockets

async def interact(tab_id):
    ws_url = f"ws://localhost:9222/devtools/page/{tab_id}"
    async with websockets.connect(ws_url) as ws:
        # Execute JS
        await ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": "document.title"}
        }))
        r = json.loads(await ws.recv())
        
        # Screenshot
        await ws.send(json.dumps({
            "id": 2,
            "method": "Page.captureScreenshot",
            "params": {"format": "png"}
        }))
        r = json.loads(await ws.recv())
        # r["result"]["data"] is base64 PNG
```

### React-controlled inputs
Standard `.value =` doesn't work on React pages. Use:
```js
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(input, 'new value');
input.dispatchEvent(new Event('input', { bubbles: true }));
input.dispatchEvent(new Event('change', { bubbles: true }));
```

## Troubleshooting

### noVNC shows ERR_EMPTY_RESPONSE
websockify crashed. Restart:
```bash
# Kill old process
pkill -f "websockify.*6080"
# Restart
/usr/bin/python3 /usr/bin/websockify --web /opt/noVNC 6080 localhost:5900 &
```

### Chromium CDP not responding
```bash
# Check if Chromium is running
ps aux | grep chromium
# Check if CDP port is open
ss -tlnp | grep 9222
```

### Session expires too quickly (Browserbase)
Use this VNC/CDP setup instead — Chromium maintains persistent sessions across tool calls.

## Bilibili Login + Cookie Extraction

When yt-dlp fails with `412 Precondition Failed` on Bilibili, you need browser cookies. Use the VNC Chromium to log in, then export cookies.

### Step 1: Open login page via CDP
```bash
curl -s -X PUT "http://localhost:9222/json/new?https://passport.bilibili.com/login"
```

### Step 2: Switch to SMS login + enter phone (via CDP websocket)
```python
# Click SMS tab, enter phone, click "获取验证码"
# Note: Bilibili uses Geetest CAPTCHA — cannot solve programmatically
# Tell user to complete CAPTCHA in noVNC
```

### Step 3: User scans QR code in noVNC (easier than SMS)
The QR code login is simpler — user opens noVNC, scans QR with Bilibili app.

### Step 4: Export cookies
```python
import asyncio, json, websockets

async def export_cookies(tab_id):
    ws_url = f"ws://localhost:9222/devtools/page/{tab_id}"
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({
            "id": 1,
            "method": "Network.getCookies",
            "params": {"urls": ["https://www.bilibili.com", "https://passport.bilibili.com"]}
        }))
        r = json.loads(await ws.recv())
        cookies = r.get("result", {}).get("cookies", [])
        
        # Write Netscape format for yt-dlp
        lines = ["# Netscape HTTP Cookie File"]
        for c in cookies:
            domain = c.get("domain", ".bilibili.com")
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure", False) else "FALSE"
            expires = str(int(c.get("expires", 0)))
            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{c['name']}\t{c['value']}")
        
        with open("/tmp/bilibili_cookies.txt", "w") as f:
            f.write("\n".join(lines))
        return cookies
```

### Step 5: Download with yt-dlp
```bash
# List formats
yt-dlp -F --cookies /tmp/bilibili_cookies.txt 'https://www.bilibili.com/video/BVxxxxxx'

# Download highest quality audio (no re-encoding)
yt-dlp -f 30280 --cookies /tmp/bilibili_cookies.txt -o 'output.m4a' 'URL'

# Trim with stream copy (no quality loss)
ffmpeg -y -ss 4380 -i input.m4a -t 540 -c copy output_trimmed.m4a
```

### Key learnings
- Bilibili audio max quality: 176kbps AAC (format ID 30280)
- Always use `-c copy` for trimming to avoid re-encoding loss
- Geetest CAPTCHA cannot be solved programmatically — use QR code login instead
- Cookie file needs valid expires values (skip entries with -1)
- User has Bilibili 大会员 (premium) for max quality access
