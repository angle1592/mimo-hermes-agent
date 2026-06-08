---
name: weixin-setup
description: "Configure Hermes Agent gateway to connect to Weixin (个人微信) personal accounts via Tencent iLink Bot API."
tags: [hermes, gateway, weixin, wechat, messaging]
related_skills: [dingtalk-setup, hermes-agent]
---

# Weixin (个人微信) Gateway Setup

Connect Hermes Agent to **personal WeChat accounts** via Tencent's official iLink Bot API (`ilinkai.weixin.qq.com`). Supports text, images, video, documents, and **voice messages** (MEDIA_VOICE).

**NOTE**: This is for personal WeChat (个人微信), NOT enterprise WeChat (企业微信/WeCom). Hermes has a separate `wecom` adapter for that.

## Prerequisites

- A personal WeChat account (with camera for QR scanning)
- Python dependencies: `aiohttp`, `cryptography` (check with `python3 -c "import aiohttp; from cryptography.hazmat.primitives.ciphers import Cipher"`)

## Steps

### 1. Install dependencies (if missing)

```bash
pip install aiohttp cryptography
```

### 2. Run interactive setup

```bash
hermes gateway setup
```

Select **"Weixin (WeChat)"** from the platform list.

### 3. QR Code Login

The setup wizard will:
1. Display a QR code URL in the terminal
2. Open the URL or render QR in terminal
3. Scan with WeChat → confirm login
4. Automatically store `WEIXIN_ACCOUNT_ID` and `WEIXIN_TOKEN` in `~/.hermes/.env`

### 4. DM Authorization Policy

Choose how direct messages are authorized:
- **Pairing approval** (recommended) — unknown users request access, you approve via `hermes pairing approve`
- **Open** — allow all DMs
- **Allowlist** — only specific user IDs
- **Disabled** — no DMs

### 5. Group Policy

Choose group message behavior:
- **@mention** — bot responds only when @mentioned
- **All messages** — bot responds to every message
- **Disabled** — ignore groups

### 6. Restart Gateway

```bash
hermes gateway restart
```

## Environment Variables

All set in `~/.hermes/.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `WEIXIN_ACCOUNT_ID` | Yes | Bot account ID (auto-set by QR login) |
| `WEIXIN_TOKEN` | Yes | Auth token (auto-set by QR login) |
| `WEIXIN_BASE_URL` | No | API base URL (default: `https://ilinkai.weixin.qq.com`) |
| `WEIXIN_CDN_BASE_URL` | No | CDN base URL (default: `https://novac2c.cdn.weixin.qq.com/c2c`) |
| `WEIXIN_DM_POLICY` | No | DM policy: `pairing`, `open`, `allowlist`, `disabled` |
| `WEIXIN_GROUP_POLICY` | No | Group policy: `mention`, `all`, `disabled` |
| `WEIXIN_ALLOWED_USERS` | No | Comma-separated user IDs for allowlist |
| `WEIXIN_GROUP_ALLOWED_USERS` | No | Comma-separated group IDs for allowlist |
| `WEIXIN_HOME_CHANNEL` | No | Default home channel ID |

## Key Differences from DingTalk

| Feature | DingTalk | Weixin |
|---------|----------|--------|
| Auth | AppKey + AppSecret | QR code scan |
| Voice support | ❌ | ⚠️ Inbound ✅ / Outbound → file attachment (see below) |
| Image support | Via link | ✅ Native |
| File support | ❌ | ✅ Native |
| Platform | Enterprise only | Personal accounts |

## Non-Interactive / Remote QR Login

When you can't run `hermes gateway setup` interactively (e.g., user is chatting via DingTalk, not SSH), do it programmatically:

### Prerequisites
```bash
pip install qrcode[pil]
# qrcode[pil] installs both qrcode and Pillow (PIL) for image generation
# qrcode alone only supports terminal ASCII output
```

### Step 1: Fetch QR code from iLink API

```python
import asyncio, json, aiohttp

ILINK_BASE = "https://ilinkai.weixin.qq.com"

async def get_qr():
    connector = None
    try:
        import ssl, certifi
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
    except ImportError:
        pass
    async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
        url = f"{ILINK_BASE}/ilink/bot/get_bot_qrcode?bot_type=3"
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "AuthorizationType": "ilink_bot_token"}
        async with session.get(url, headers=headers) as resp:
            data = json.loads(await resp.read())  # returns octet-stream but is JSON
            return data

data = asyncio.run(get_qr())
# data = {"qrcode": "<hex>", "qrcode_img_content": "<scannable URL>", "ret": 0}
```

**Pitfall**: The iLink API returns `Content-Type: application/octet-stream` but the body is valid JSON. Use `json.loads(await resp.read())` instead of `resp.json()`.

### Step 2: Generate QR image and host it

```python
import qrcode
qr_url = data["qrcode_img_content"]
img = qrcode.make(qr_url)
img.save("/tmp/weixin_qr.png")
# Copy to web server:
# cp /tmp/weixin_qr.png /usr/share/nginx/html/files/weixin_qr.png
```

Then send the URL to the user (e.g., via DingTalk): `http://<server>/files/weixin_qr.png`

**Nginx path note**: Default nginx root is `/usr/share/nginx/html`. ⚠️ **Use `/audio/` path, NOT `/files/`** — this server has a `server_name YOUR_SERVER_IP` block with a catch-all `location /` that proxies to the Hermes Dashboard (port 9119), so `/files/` gets intercepted. The `/audio/` path has a dedicated `alias` directive with `auth_basic off` in both server blocks. Copy to: `cp /tmp/weixin_qr.png /usr/share/nginx/html/audio/weixin_qr.png` → accessible at `http://YOUR_SERVER_IP/audio/weixin_qr.png`.

### Step 3: Poll for scan confirmation

```python
import time

async def poll(qrcode_value, timeout_sec=480):
    deadline = time.time() + timeout_sec
    current_base = ILINK_BASE
    async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
        while time.time() < deadline:
            url = f"{current_base}/ilink/bot/get_qrcode_status?qrcode={qrcode_value}"
            async with session.get(url, headers=headers) as resp:
                data = json.loads(await resp.read())
                status = data.get("status", "wait")
                if status == "confirmed":
                    return data  # ilink_bot_id, bot_token, baseurl, ilink_user_id
                elif status == "scaned_but_redirect":
                    rh = data.get("redirect_host", "")
                    if rh: current_base = f"https://{rh}"
                elif status == "expired":
                    return None  # QR expired, need refresh
            await asyncio.sleep(2)
    return None  # timeout
```

### Step 4: Save credentials to ~/.hermes/.env

On confirmation, write `WEIXIN_ACCOUNT_ID`, `WEIXIN_TOKEN`, `WEIXIN_BASE_URL`, `WEIXIN_CDN_BASE_URL` to `~/.hermes/.env`. Then restart gateway.

### Pitfalls
- QR expires ~35 seconds but auto-refreshes up to 3 times
- Total login timeout: ~8 minutes (480s)
- If running from gateway (DingTalk session), use background terminal for the polling script
- `send_message` MEDIA attachments don't work on DingTalk — host the QR image on nginx instead
- ⚠️ **Use `/audio/` not `/files/`** for hosting QR images — the named server block's catch-all `location /` proxies everything to the Hermes Dashboard, intercepting `/files/`. Only `/audio/`, `/token/` and root are explicitly handled.
- ⚠️ **QR codes expire fast** — if the user takes too long to scan, generate a fresh one. Don't reuse old QR values in the poll script; update `QRCODE` in the polling script to match the new one.

## WeChat Article Reading

The iLink Bot API authentication is **completely separate** from mp.weixin.qq.com browser cookies. Having a working WeChat bot connection does NOT enable reading WeChat articles. To read articles programmatically, use `wechat-reader` (see `deploy-service-china` skill, `references/wechat-reader.md`) which requires a separate Chrome browser session with manual captcha verification.

## Markdown Rendering

WeChat personal accounts **do not render Markdown** natively. The iLink Bot API sends plain text only.

**iLink message item types** (confirmed from source):

| Type | ID | Notes |
|------|---|-------|
| `ITEM_TEXT` | 1 | Plain text only — no HTML, no rich text |
| `ITEM_IMAGE` | 2 | Image upload |
| `ITEM_VOICE` | 3 | Voice message (native bubble) |
| `ITEM_FILE` | 4 | File attachment |
| `ITEM_VIDEO` | 5 | Video upload |

There is **no rich text / HTML / card / mini-program item type**. The API only supports plain text for formatted content. If users want visually richer output, the only option is generating an image (e.g., rendered HTML screenshot) and sending as `ITEM_IMAGE`. To handle this, the adapter's `format_message()` method calls `_convert_markdown_for_weixin()` which converts markdown to WeChat-friendly plain text:

| Markdown | WeChat display |
|----------|---------------|
| `# Title` | 【Title】 |
| `## Title` | 「Title」 |
| `**bold**` | bold |
| `*italic*` | italic |
| `~~strike~~` | strike |
| `` `code` `` | 「code」 |
| `[text](url)` | text (url) |
| `- list` | · list |
| `> quote` | │ quote |
| `---` | ──────────── |
| Tables | List format |

Code blocks (``` fences) are preserved as-is.

**Location:** `_convert_markdown_for_weixin()` defined before `_split_text_for_weixin_delivery()` in `weixin.py`. Called by `WeixinAdapter.format_message()`.

**If conversion breaks after Hermes update:** Check that `format_message()` calls `_convert_markdown_for_weixin()` (not the old `_normalize_markdown_blocks()`). The function uses existing helpers `_rewrite_table_block_for_weixin()` and the regex patterns `_HEADER_RE`, `_FENCE_RE`, `_TABLE_RULE_RE`, `_MARKDOWN_LINK_RE`.

**Regex pitfall with CJK text:** Python 3's `\w` matches Unicode word characters including Chinese/Japanese/Korean. The italic regex uses `(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)` instead of `(?<!\w)\*...\*` because `(?<!\w)` fails after CJK characters (e.g., `有*斜体*` — `有` IS a `\w` char). Always use `(?<!\*)` lookbehind for markdown delimiter matching in CJK contexts.

## Markdown Rendering (iLink Bot API)

The Hermes weixin adapter **strips all Markdown** via `_convert_markdown_for_weixin()` in `weixin.py`:
- `**bold**` → bold
- `# Header` → 【Header】
- `` `code` `` → 「code」
- Tables → list format
- Lists → · item

The iLink Bot API only defines 5 item types: `ITEM_TEXT(1)`, `ITEM_IMAGE(2)`, `ITEM_VOICE(3)`, `ITEM_FILE(4)`, `ITEM_VIDEO(5)`. There is no native `ITEM_MARKDOWN` type.

**However:** The code comment at line 768 says "Weixin can render Markdown" — suggesting WeChat's client-side may render Markdown syntax in plain text messages. ClawBot (OpenClaw) reportedly uses the same iLink API with native Markdown rendering.

**To test raw Markdown rendering:** Send a message with `ITEM_TEXT` containing raw Markdown syntax (without the `_convert_markdown_for_weixin` conversion). If WeChat renders it natively, the conversion function could be made optional or removed.

**Key question:** Does the iLink API's `sendmessage` endpoint pass Markdown syntax through to WeChat's client for rendering, or does the server strip it? This needs testing. The current adapter assumes the former is false, but ClawBot's behavior suggests otherwise.

See `references/weixin-markdown-rendering.md` for investigation notes.

## Troubleshooting

- **Audio files sent as download attachments, not inline playable** — WeChat can't play audio inline as a native voice bubble. The `send_voice()` method in `weixin.py` falls back to `_send_file(force_file_attachment=True)` because native outbound voice bubbles are not proven-working in the iLink API. Workaround: host the audio file on nginx and share the URL. The server has a `/audio/` path with `alias` directive and `auth_basic off` — copy to `/usr/share/nginx/html/audio/` and share `http://<server_ip>/audio/<filename>`. Alternatively, FileBrowser at `http://<server_ip>/files/` also works for file sharing (proxied through nginx to port 8080).
- **"Weixin adapter import failed"** → Missing `aiohttp` or `cryptography`. Install with pip.
- **QR login timeout** — Re-run `hermes gateway setup` and scan quickly (QR expires ~35s).
- **Session expired (errcode -14)** — Re-login via `hermes gateway setup` → Weixin.
- **Rate limited (errcode -2)** — iLink frequency limit. Backoff and retry automatically.
- **SSL verification failure** — Tencent's iLink server may not verify against some CA stores. `certifi` package helps; install with `pip install certifi`.
- **Token not persisting** — Check `~/.hermes/.env` has `WEIXIN_TOKEN=` and `WEIXIN_ACCOUNT_ID=`.
- **Bot not responding** — Check gateway logs: `grep -i weixin ~/.hermes/logs/gateway.log | tail -20`
- **"My message was lost / bot didn't receive it"** — Almost always caused by the user sending `/stop` before the response finished. The `/stop` command interrupts the in-progress reply, making it look like the message was never received. Check session records (`session_search`) to confirm the message WAS received and a response was generated. Explain to the user: "Your message was received and processed, but `/stop` interrupted the reply before it could be delivered."

## User FAQ (for explaining to users before setup)

When a user asks "what does this do / will it affect my groups / how do I interact?":

- **Purpose**: The logged-in WeChat account becomes the bot's identity. Messages sent to that account are processed by Hermes, and replies appear as that account sending.
- **Existing group chats**: Depends on group policy config. Set to "disabled" → existing groups are completely unaffected. Set to "@mention" → bot only responds when @mentioned in groups.
- **Interaction**: People send messages to the WeChat account → Hermes auto-replies. The account owner can also chat with the bot directly via DM. Voice messages work natively for **receiving** (unlike DingTalk). **Sending** voice falls back to file attachment — native outbound voice bubbles are not proven-working in the iLink API (see `send_voice()` in `weixin.py`).
- **Phone WeChat still works**: iLink Bot login is like a multi-device session (similar to iPad/desktop). Your phone WeChat continues normally.
