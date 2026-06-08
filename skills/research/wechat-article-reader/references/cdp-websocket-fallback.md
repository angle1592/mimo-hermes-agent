# CDP Websocket Fallback (Raw Python stdlib)

When Playwright's `connect_over_cdp('http://127.0.0.1:9222')` fails with HTTP 400, use this raw websocket approach.

## Why it fails

Playwright does an HTTP GET to `/json/version` and expects specific response headers. Chrome versions (e.g. 147+) may return a response that Playwright's HTTP client rejects as status 400, even though `curl` sees it as valid JSON. The websocket endpoint itself works fine — it's the HTTP handshake negotiation that breaks.

## Solution: Raw websocket CDP client

A minimal Python stdlib implementation (no third-party deps) that connects to Chrome's CDP websocket and issues commands.

### Get cookies via CDP websocket

```python
import json, http.client, struct, base64, os, socket, time
from urllib.parse import urlparse

# 1. Get the browser websocket URL
conn = http.client.HTTPConnection("127.0.0.1", 9222)
conn.request("GET", "/json/version")
version = json.loads(conn.getresponse().read().decode())
ws_url = version["webSocketDebuggerUrl"]

# 2. Connect via raw websocket
def ws_connect(url):
    parsed = urlparse(url)
    sock = socket.create_connection((parsed.hostname, parsed.port))
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET {parsed.path} HTTP/1.1\r\n"
        f"Host: {parsed.hostname}:{parsed.port}\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.send(request.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
    return sock

def ws_send(sock, data):
    payload = json.dumps(data).encode()
    frame = bytearray()
    frame.append(0x81)  # FIN + text
    mask_key = os.urandom(4)
    if len(payload) < 126:
        frame.append(0x80 | len(payload))
    elif len(payload) < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", len(payload)))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", len(payload)))
    frame.extend(mask_key)
    for i, b in enumerate(payload):
        frame.append(b ^ mask_key[i % 4])
    sock.send(bytes(frame))

def ws_recv(sock):
    data = sock.recv(65536)
    if not data:
        return None
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7F
    offset = 2
    if length == 126:
        length = struct.unpack(">H", data[2:4])[0]
        offset = 4
    elif length == 127:
        length = struct.unpack(">Q", data[2:10])[0]
        offset = 10
    mask = None
    if masked:
        mask = data[offset:offset+4]
        offset += 4
    payload = data[offset:offset+length]
    if masked and mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return payload.decode()

# 3. Get cookies
sock = ws_connect(ws_url)
ws_send(sock, {"id": 1, "method": "Storage.getCookies"})
resp = ws_recv(sock)
result = json.loads(resp)
cookies = result.get("result", {}).get("cookies", [])

# 4. Check poc_sid
now = time.time()
for c in cookies:
    if c["name"] == "poc_sid":
        days = (c["expires"] - now) / 86400
        print(f"poc_sid expires in {days:.1f} days")
        break

sock.close()
```

## Deployment

The script above is deployed at `/opt/wechat-reader/check_cookies.py`. The cron job `wechat-reader-cookies-check` invokes it directly.

## Key gotchas

- **Bitwise vs logical operators**: In the websocket frame parser, use `&` (bitwise AND) not `and` (logical AND). `data[1] and 0x80` evaluates to `0x80` (truthy) instead of the actual bit value.
- **Heredoc `&` issue**: Do NOT wrap this script in a bash heredoc (`<< 'PYEOF'`) — the `&` in `0x80 & ...` gets interpreted by bash as a background operator. Always write to a file first.
- **Client-side masking**: The websocket spec requires client-to-server frames to be masked. Server-to-client frames may or may not be masked — handle both cases.
