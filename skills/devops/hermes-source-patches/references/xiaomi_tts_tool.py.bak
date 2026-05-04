#!/usr/bin/env python3
"""
Xiaomi MiMo TTS Tool Module

Supports Xiaomi MiMo-V2.5-TTS series models for text-to-speech synthesis.
Uses the /v1/chat/completions endpoint with audio parameter.

Models supported:
- mimo-v2.5-tts: Built-in voices
- mimo-v2.5-tts-voicedesign: Voice design via text description
- mimo-v2.5-tts-voiceclone: Voice cloning from audio samples

Configuration is loaded from ~/.hermes/config.yaml under 'tts.xiaomi' key.
Required environment variable: XIAOMI_API_KEY
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy imports
def _import_openai_client():
    """Lazy import OpenAI client."""
    from openai import OpenAI as OpenAIClient
    return OpenAIClient

# Defaults
DEFAULT_MODEL = "mimo-v2.5-tts"
DEFAULT_VOICE = "茉莉"
DEFAULT_FORMAT = "wav"

# Available voices for mimo-v2.5-tts
AVAILABLE_VOICES = {
    "mimo-v2.5-tts": ["茉莉", "冰糖", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean", "mimo_default"],
    "mimo-v2-tts": ["mimo_default", "default_en", "default_zh"],
}


def check_requirements() -> bool:
    """Check if Xiaomi MiMo TTS is configured."""
    return bool(os.getenv("XIAOMI_API_KEY"))


def xiaomi_tts_tool(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    audio_format: str = DEFAULT_FORMAT,
    style: str = "",
    task_id: str = None
) -> str:
    """
    Generate speech from text using Xiaomi MiMo TTS.
    
    Args:
        text: Text to convert to speech
        voice: Voice name (e.g., "茉莉", "Chloe", "Milo")
        model: TTS model (default: mimo-v2.5-tts)
        audio_format: Output format (wav, mp3, pcm, pcm16)
        style: Style description for voice control (optional)
        task_id: Task ID for tracking
    
    Returns:
        JSON string with audio file path or error
    """
    api_key = os.getenv("XIAOMI_API_KEY")
    if not api_key:
        return json.dumps({
            "success": False,
            "error": "XIAOMI_API_KEY not configured"
        })
    
    # Get base URL from config or use default
    base_url = os.getenv("XIAOMI_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
    
    try:
        OpenAIClient = _import_openai_client()
        client = OpenAIClient(api_key=api_key, base_url=base_url)
        
        # Prepare messages
        messages = []
        if style:
            messages.append({"role": "user", "content": style})
        messages.append({"role": "assistant", "content": text})
        
        # Call API
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            audio={"format": audio_format, "voice": voice}
        )
        
        # Extract audio data
        message = completion.choices[0].message
        if not hasattr(message, 'audio') or not message.audio:
            return json.dumps({
                "success": False,
                "error": "No audio data in response"
            })
        
        audio_bytes = base64.b64decode(message.audio.data)
        
        # Save to temporary file
        suffix = f".{audio_format}" if audio_format != "pcm16" else ".pcm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            output_path = f.name
        
        return json.dumps({
            "success": True,
            "audio_path": output_path,
            "model": model,
            "voice": voice,
            "format": audio_format,
            "size_bytes": len(audio_bytes)
        })
        
    except Exception as e:
        logger.error(f"Xiaomi TTS error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


# Register tool
from tools.registry import registry

registry.register(
    name="xiaomi_tts",
    toolset="tts",
    schema={
        "name": "xiaomi_tts",
        "description": "Generate speech from text using Xiaomi MiMo TTS models",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech"
                },
                "voice": {
                    "type": "string",
                    "description": "Voice name (e.g., 茉莉, Chloe, Milo)",
                    "default": DEFAULT_VOICE
                },
                "model": {
                    "type": "string",
                    "description": "TTS model (mimo-v2.5-tts, mimo-v2.5-tts-voicedesign, mimo-v2.5-tts-voiceclone)",
                    "default": DEFAULT_MODEL
                },
                "audio_format": {
                    "type": "string",
                    "description": "Output format (wav, mp3, pcm, pcm16)",
                    "default": DEFAULT_FORMAT
                },
                "style": {
                    "type": "string",
                    "description": "Style description for voice control (optional)",
                    "default": ""
                }
            },
            "required": ["text"]
        }
    },
    handler=lambda args, **kw: xiaomi_tts_tool(
        text=args.get("text", ""),
        voice=args.get("voice", DEFAULT_VOICE),
        model=args.get("model", DEFAULT_MODEL),
        audio_format=args.get("audio_format", DEFAULT_FORMAT),
        style=args.get("style", ""),
        task_id=kw.get("task_id")
    ),
    check_fn=check_requirements,
    requires_env=["XIAOMI_API_KEY"]
)
