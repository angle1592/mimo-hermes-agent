---
name: hermes-dingtalk-setup
description: Configure Hermes Agent gateway to connect to DingTalk (钉钉) via Stream Mode.
tags: [hermes, gateway, dingtalk, messaging, china, alibaba]
---

# Hermes Agent DingTalk Integration Setup

Configure DingTalk (钉钉) as a messaging platform for Hermes Agent using the dingtalk-stream SDK.

## When to Use

- User wants to chat with Hermes Agent through DingTalk
- User asks about setting up DingTalk, WeChat, or other Chinese messaging platforms
- User mentions needing to configure gateway platforms in config.yaml
- Error: `DingTalk: dingtalk-stream not installed or DINGTALK_CLIENT_ID/SECRET not set`

## Prerequisites

- Hermes Agent installed (any installation method)
- A DingTalk account (org admin or ability to create apps in DingTalk Open Platform)
- Access to [DingTalk Open Platform](https://open.dingtalk.com/)

## Steps

### 1. Create a DingTalk Internal App

1. Go to https://open.dingtalk.com/ and sign in with QR code
2. Navigate: **开发者后台 → 应用开发 → 企业内部应用 → 创建应用**
3. Fill in app name/description/icon (any values work)
4. Select **"企业自主开发"** as creation method

### 2. Get Credentials

In the app management page:

- **AppKey / Client ID** — found under **"凭证与基础信息"** or **"机器人配置"**
- **AppSecret / Client Secret** — found under **"凭证与基础信息"** (click "查看" to reveal)

### 3. Enable Bot & Stream Mode

1. Under **"消息接收模式"**, select **Stream Mode** (NOT HTTP — no URL needed)
2. Enable **机器人** (Bot) feature toggle
3. **版本管理与发布 → 创建版本** (version `1.0.0`) → **上线** (publish)

### 4. Install Dependencies in the CORRECT Python Environment

**Critical:** the gateway runs from the Hermes venv, NOT the system Python. Find and install there:

```bash
# Find the Hermes venv
which hermes
# → /usr/local/lib/hermes-agent/.venv/bin/hermes  (example)

# Install in that venv
/usr/local/lib/hermes-agent/.venv/bin/pip install "dingtalk-stream>=0.20" httpx
```

### 5. Configure Credentials

Add the DingTalk platform config to `~/.hermes/config.yaml` as a **top-level** `platforms:` key (NOT under `display.platforms:`):

```yaml
platforms:
  dingtalk:
    enabled: true
    extra:
      client_id: "your-app-key-here"
      client_secret: "your-app-secret-here"
```

For optional group-chat settings:

```yaml
platforms:
  dingtalk:
    enabled: true
    extra:
      client_id: "your-app-key-here"
      client_secret: "your-app-secret-here"
      require_mention: true     # must @bot to trigger (env: DINGTALK_REQUIRE_MENTION)
```

Alternatively, set environment variables in `~/.hermes/.env`:

```bash
DINGTALK_CLIENT_ID=your-app-key
DINGTALK_CLIENT_SECRET=your-app-secret
```

Also add `GATEWAY_ALLOW_ALL_USERS=true` to `.env` to skip user allowlist setup.

### 6. Start the Gateway

```bash
# Using the hermes command (it picks up the venv automatically)
hermes gateway run
```

### 7. Verify Connection

Check the gateway status via the web dashboard API:

```bash
curl -s http://127.0.0.1:9119/api/status
```

Expected response snippet:

```json
"gateway_platforms": {
    "dingtalk": {
        "state": "connected",
        "error_code": null,
        "error_message": null
    }
}
```

### 8. Test

Send a message in DingTalk to your bot (or @它 in a group chat if `require_mention: true`).

### 9. (Optional) Set a Home Channel for Cron Results

The home channel is where Hermes delivers cron job results and cross-platform messages. To keep cron outputs out of your main chat, create a **separate group** in DingTalk, add the bot, and configure:

1. Find the group's chat ID from gateway logs after sending a message in the group:
   ```bash
   grep "inbound message.*platform=dingtalk" ~/.hermes/logs/gateway.log
   # → chat=cidXXX==
   ```

2. Add `home_channel` to `config.yaml`:
   ```yaml
   platforms:
     dingtalk:
       enabled: true
       home_channel:
         platform: dingtalk
         chat_id: "cidXXX=="
         name: "Cron Results Group"
       extra:
         client_id: "..."
         client_secret: "..."
   ```

3. Restart the gateway for changes to take effect.

> **⚠️ Important: Setting home_channel or deliver is NOT sufficient for cron job delivery.**  
> Cron jobs run as separate agent sessions outside the active stream mode connection. The DingTalk platform adapter needs a separate webhook URL to push messages proactively. Without one, you'll see:
> ```
> WARNING [Dingtalk] No valid session_webhook for chat_id=...
> ERROR cron.scheduler: Job '...': delivery error: DingTalk not configured.
>        Set DINGTALK_WEBHOOK_URL env var or webhook_url in dingtalk platform extra config.
> ```
> See the **Cron Delivery with Webhook URL** section below for the solution.

### 10. (Required for Cron Jobs) Configure a DingTalk Webhook URL

Cron job delivery requires a separate webhook mechanism because cron jobs execute outside the Stream Mode WebSocket connection.

#### 10.1. Create a Custom Bot in the Target Group

1. Open the DingTalk group where you want cron results delivered (e.g., the home channel group)
2. Click `...` (右上角) → **群设置** → **智能群助手** → **添加机器人**
3. Choose **自定义机器人** (Custom Bot)
4. Name it (e.g., "Hermes Agent Cron")
5. **Security settings:**
   - **加签 (Signature)** — most secure, but requires configuring the secret with Hermes
   - **自定义关键词** — simple; messages must contain the keyword (annoying for cron output)
   - **IP地址段** — restrict to your server IP
6. Complete setup and **copy the Webhook URL**:
   ```
   https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxxx
   ```

#### 10.2. Configure Webhook URL in Hermes

Add to `config.yaml` under the DingTalk extra section:

```yaml
platforms:
  dingtalk:
    enabled: true
    extra:
      client_id: "your-app-key-here"
      client_secret: "your-app-secret-here"
      webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxxx"
```

Or set the environment variable in `~/.hermes/.env`:

```bash
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxxx
```

> **Note:** The webhook bot is a different bot identity from your Stream Mode bot. Messages sent via webhook appear under the custom bot's name, not the Stream Mode bot's name. This is a DingTalk platform limitation.

#### 10.5. Proactive Messaging via Robot OpenAPI (Same Bot Identity)

Instead of creating a separate custom bot, you can patch the Hermes Agent code to use the existing Stream Mode bot credentials (`client_id`/`client_secret`) to proactively send messages via DingTalk's Robot OpenAPI. This way, cron deliveries use the **same bot identity** as your Stream Mode chat.

**How it works:**

1. Get OAuth token via `POST https://api.dingtalk.com/v1.0/oauth2/accessToken` with `appKey` + `appSecret`
2. Send message via `POST https://api.dingtalk.com/v1.0/robot/groupMessages/send` (groups) or `/v1.0/robot/oToMessages/batchSend` (DMs)
3. No additional DingTalk Open Platform permission is needed — the existing app credentials suffice

**⚠️ Important header:** The DingTalk Robot OpenAPI expects the token in the **`x-acs-dingtalk-access-token`** header, NOT `Authorization: Bearer`. Using the wrong header will return `AuthenticationFailed.MissingParameter`.

**The patch (modifies tools/send_message_tool.py):**

Replace the `_send_dingtalk` function to try Robot OpenAPI first, fall back to webhook URL:

```python
# In /usr/local/lib/hermes-agent/tools/send_message_tool.py
async def _send_dingtalk(extra, chat_id, message):
    """Send via DingTalk Robot OpenAPI (proactive) with webhook fallback.

    Priority:
    1. Robot OpenAPI proactive send (uses client_id/client_secret from extra)
    2. Static webhook URL (DINGTALK_WEBHOOK_URL or webhook_url in extra)
    """
    try:
        import httpx
    except ImportError:
        return {"error": "httpx not installed"}

    # Step 1: Try Robot OpenAPI proactive send
    client_id = extra.get("client_id") or os.getenv("DINGTALK_CLIENT_ID", "")
    client_secret = extra.get("client_secret") or os.getenv("DINGTALK_CLIENT_SECRET", "")
    if client_id and client_secret:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get OAuth access token
                token_resp = await client.post(
                    "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                    json={"appKey": client_id, "appSecret": client_secret},
                )
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    access_token = token_data.get("accessToken")
                    if access_token:
                        # Determine if it's a group (cidXXXX==) or DM chat_id
                        if chat_id.startswith("cid"):
                            # Group message
                            send_url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
                            payload = {
                                "robotCode": client_id,
                                "openConversationId": chat_id,
                                "msgKey": "sampleMarkdown",
                                "msgParam": json.dumps({
                                    "title": "Hermes Agent",
                                    "text": message,
                                }),
                            }
                        else:
                            # User DM
                            send_url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
                            payload = {
                                "robotCode": client_id,
                                "userIds": [chat_id],
                                "msgKey": "sampleMarkdown",
                                "msgParam": json.dumps({
                                    "title": "Hermes Agent",
                                    "text": message,
                                }),
                            }

                        send_resp = await client.post(
                            send_url,
                            headers={"x-acs-dingtalk-access-token": access_token},
                            json=payload,
                        )

                        if send_resp.status_code == 200:
                            return {"success": True, "platform": "dingtalk", "chat_id": chat_id}
                        elif send_resp.status_code == 403:
                            try:
                                body = send_resp.json()
                                scopes = body.get("accessDeniedDetail", {}).get("requiredScopes", [])
                                if scopes:
                                    return {"error": f"DingTalk permission missing. Go to open-dev.dingtalk.com → 权限管理, search and apply: {scopes[0]}"}
                            except Exception:
                                pass
                            return {"error": f"DingTalk API 403: missing robot proactive messaging permission"}
                        else:
                            body_text = await send_resp.aread()
                            return {"error": f"DingTalk API error: HTTP {send_resp.status_code} {body_text[:200].decode()}"}
        except Exception as e:
            return {"error": f"DingTalk proactive send failed: {e}"}

    # Step 2: Fallback to static webhook URL (existing behavior)
    try:
        # ... (original webhook send code stays as-is)
        webhook_url = extra.get("webhook_url") or os.getenv("DINGTALK_WEBHOOK_URL", "")
        if not webhook_url:
            return {"error": ...}
        ...
    except Exception as e:
        return _error(f"DingTalk send failed: {e}")
```

**Save a patch file** for easy re-application after Hermes updates:

```bash
# Create the patch
cd /usr/local/lib/hermes-agent && \
  git diff -- tools/send_message_tool.py > ~/.hermes/patches/dingtalk-proactive-send.patch

# Re-apply after hermes update:
cd /usr/local/lib/hermes-agent && \
  patch -p1 < ~/.hermes/patches/dingtalk-proactive-send.patch && \
  hermes gateway restart
```

**Note:** After modifying the file, you must **restart the gateway** (`/restart` or `hermes gateway restart`) for the change to take effect. The cron scheduler loads `send_message_tool` functions at runtime from the gateway process — editing the file alone won't affect a running process.

This approach is essentially what PR **#14336** implements. Once that PR merges into a future Hermes release, this manual patch will no longer be needed.

#### 10.3. Verify Cron Delivery

Test a cron job after configuration:

```bash
# Trigger a cron job manually
hermes cron run <job-id>

# Check for delivery errors
grep -i "delivery error\|No valid session_webhook" ~/.hermes/logs/gateway.log ~/.hermes/logs/errors.log

# The cron job result should appear in the group
```

#### 10.4. Update Existing Cron Jobs

If you already have cron jobs with `deliver: "origin"`, update them to use the group's chat ID directly:

```bash
hermes cron update <job-id> --deliver "dingtalk:REDACTED_CHAT_ID"
```

This can also be done via the `cronjob` tool by passing `deliver` and `model` (as an object `{model: "...", provider: "..."}`) in the update action.

## Architecture

```
DingTalk App ──WebSocket (Stream Mode)──→ Hermes Gateway
                                              ↓
                                         AIAgent
```

The dingtalk-stream SDK maintains a persistent WebSocket connection. Inbound messages arrive via a `ChatbotHandler` callback; replies are sent via the message's session webhook URL.

## Pitfalls

- **Wrong Python environment:** `pip install dingtalk-stream` in the system Python does NOT work — the gateway runs from its own venv. Always install in the venv at `/path/to/hermes-venv/bin/pip install dingtalk-stream`.
- **Wrong config key location:** The `platforms:` section must be at the **top level** of `config.yaml`, NOT nested under `display.platforms:`. The gateway config loader reads from `yaml_cfg.get("platforms")`.
- **Missing `GATEWAY_ALLOW_ALL_USERS`:** Without this, all unauthorized users are denied. Either set it to `true` or configure `DINGTALK_ALLOWED_USERS` with specific user IDs.
- **.env not read by background process:** If .env isn't being loaded (check error message), add credentials directly to `config.yaml` under `platforms.dingtalk.extra.client_id` and `client_secret`. For reliability, put credentials in BOTH `.env` AND `config.yaml`.
- **HTTP mode vs Stream mode:** Always use Stream Mode in the DingTalk dev console. HTTP mode requires a public webhook URL which is harder to configure.
- **Dashboard \"connected\" status is misleading:** The web dashboard `/api/status` may show `\"state\": \"connected\"` even when the actual WebSocket stream is failing auth. The adapter reports connected before the handshake completes. Always verify by checking the *actual* stream errors in `/root/.hermes/logs/errors.log` or `/root/.hermes/logs/gateway.log` — look for `\"authFailed\"` or \"鉴权失败\".
- **Typo-prone AppKeys:** DingTalk Client IDs often contain visually ambiguous chars like `0` (zero) vs `O`/`o` (letter), or `1` vs `l`. If auth fails (\"鉴权失败\"), the most common cause is a single wrong character. Re-read from the DingTalk dev console carefully.
- **Cron job delivery fails with `DINGTALK_WEBHOOK_URL not set`:** Stream Mode works for real-time chat but cron jobs need a separate delivery mechanism. Setting `home_channel` or changing cron `deliver` to `dingtalk:chat_id` does NOT fix this alone. Two solutions: (a) Create a custom bot in the target group and configure `webhook_url`/`DINGTALK_WEBHOOK_URL` (see section 10.3), or (b) apply the proactive messaging patch (see section 10.5) to use Robot OpenAPI with the same bot identity.
- **App must be published:** Creating the app is not enough — it must be versioned and published (\"上线\") before it can receive messages.
- **Typo-prone AppKeys:** DingTalk Client IDs often contain visually ambiguous chars like `0` (zero) vs `O`/`o` (letter), or `1` vs `l`. If auth fails ("鉴权失败"), the most common cause is a single wrong character. Re-read from the DingTalk dev console carefully.
