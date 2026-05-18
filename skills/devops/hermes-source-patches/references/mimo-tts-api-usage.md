# MiMo TTS API Usage Guide

## Endpoint

- Base URL: `https://token-plan-sgp.xiaomimimo.com/v1`
- API Key: env `XIAOMI_API_KEY` (stored in `~/.hermes/.env`, NOT auto-exported — must source manually when running outside agent loop)
- Uses OpenAI-compatible `/v1/chat/completions` with `audio` parameter

## Models

| Model | Use Case | Voice Param |
|---|---|---|
| `mimo-v2.5-tts` | Built-in voices | `audio.voice` required |
| `mimo-v2.5-tts-voicedesign` | AI-generated voices from text description | `audio.voice` NOT supported, omit it |
| `mimo-v2.5-tts-voiceclone` | Clone from audio sample | Requires reference audio |

## Built-in Voices (mimo-v2.5-tts)

- **茉莉** (default) — Chinese female, standard
- **冰糖** — Chinese female
- **苏打** — Chinese female
- **白桦** — Chinese female
- **Mia** — English female
- **Chloe** — English female
- **Milo** — Male
- **Dean** — Male
- **mimo_default** — Generic default

## Style Parameter (built-in voices)

The `style` field adds a director's instruction. It becomes the `user` message in the API call. Examples:
- `用温柔甜美的语气说`
- `轻松自然，像朋友聊天`
- `活泼俏皮`
- `沉稳大方`

## Voicedesign Model — Critical Differences

The voicedesign model uses the `user` message as the voice description and `assistant` message as the text to speak. Key constraints:

1. **DO NOT pass `audio.voice`** — returns 400: "audio.voice is not supported for voice design model"
2. **User message must not be empty** — returns 400: "user message content must not be empty"
3. Voice description goes in `user` message, target text in `assistant` message

### Working Call Pattern (Python)

```python
completion = client.chat.completions.create(
    model='mimo-v2.5-tts-voicedesign',
    messages=[
        {'role': 'user', 'content': '一个20岁左右的中国女生，声音温柔甜美，语速适中'},
        {'role': 'assistant', 'content': '要合成的文字内容'}
    ],
    audio={'format': 'mp3'}  # NO 'voice' key!
)
audio_bytes = base64.b64decode(completion.choices[0].message.audio.data)
```

### Voice Description Examples

- 可爱萝莉: `一个可爱的萝莉女孩，声音软萌甜美，语调上扬，像动画片里的小女孩`
- 傲娇女高: `一个傲娇的高中女生，语气高冷但有点害羞，说话带点不屑但其实很关心人`
- 温柔女生: `一个20岁左右的中国女生，声音温柔甜美，语速适中，像在和好朋友聊天一样轻松自然`

## Built-in Voice Call Pattern

```python
completion = client.chat.completions.create(
    model='mimo-v2.5-tts',
    messages=[
        {'role': 'user', 'content': '用温柔甜美的语气说'},  # style, optional
        {'role': 'assistant', 'content': '要合成的文字内容'}
    ],
    audio={'format': 'mp3', 'voice': '冰糖'}  # voice required
)
```

## Output Formats

Supported: `wav`, `mp3`, `pcm`, `pcm16`

## Response Handling

```python
message = completion.choices[0].message
if hasattr(message, 'audio') and message.audio:
    audio_bytes = base64.b64decode(message.audio.data)
```

## Tool File Location

`/usr/local/lib/hermes-agent/tools/xiaomi_tts_tool.py` — registered as `xiaomi_tts` custom tool under `tts` toolset.

## Static File Hosting (this server)

Audio files can be served via nginx at `/audio/` path:
- Directory: `/usr/share/nginx/html/audio/`
- URL: `http://YOUR_SERVER_IP/audio/`
- No auth required (`auth_basic off`)
- TTS demo page: `/usr/share/nginx/html/audio/tts/index.html`

## WeChat Limitation

The weixin adapter cannot send native voice bubbles (绿色语音气泡). Audio files are sent as file attachments. This is a known limitation in the adapter code (`send_voice` method).
