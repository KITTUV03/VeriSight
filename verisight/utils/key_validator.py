"""
Interactive API Key Health Prober & Graceful Diagnostic for VeriSight.

Performs fast (sub-second) non-destructive probes against Google Gemini,
Anthropic Claude, and Sovereign On-Premise (Ollama/vLLM) endpoints to verify
credentials before pipeline execution, preventing ugly retry spam.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Tuple, Dict, Any, Optional

# Known template/placeholder tokens that users frequently leave in .env
PLACEHOLDER_SUBSTRINGS = [
    "your_gemini", "your_api_key", "your_anthropic", "your_key",
    "placeholder", "paste_here", "sk-xxx", "aizasy..."
]


def is_placeholder(key: str) -> bool:
    """Return True if the key is obviously a template placeholder string."""
    if not key or len(key.strip()) < 8:
        return True
    low = key.strip().lower()
    return any(p in low for p in PLACEHOLDER_SUBSTRINGS)


def probe_gemini_key(api_key: str, timeout: float = 2.0) -> Tuple[bool, str]:
    """
    Probe Google Gemini API key via lightweight models metadata endpoint.

    Returns:
        (is_valid, status_message)
    """
    key = api_key.strip() if api_key else ""
    if not key:
        return False, "Not set / missing"
    if is_placeholder(key):
        return False, "Template placeholder ('your_gemini_api_key_here')"

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(url, headers={"User-Agent": "VeriSight-Prober/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                model_count = len(data.get("models", []))
                return True, f"Valid & Active ({model_count} models online)"
            return False, f"Unexpected response status: {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return False, "Invalid API Key (Google rejected: API_KEY_INVALID)"
        elif e.code == 403:
            return False, "Forbidden / Quota Exceeded (HTTP 403)"
        elif e.code == 404:
            return False, "Endpoint not found (HTTP 404)"
        return False, f"Google API error (HTTP {e.code})"
    except urllib.error.URLError as e:
        return False, f"Network unreachable: {e.reason}"
    except Exception as e:
        return False, f"Probe error: {e}"


def probe_anthropic_key(api_key: str, timeout: float = 2.0) -> Tuple[bool, str]:
    """
    Probe Anthropic Claude API key via models list endpoint.

    Returns:
        (is_valid, status_message)
    """
    key = api_key.strip() if api_key else ""
    if not key:
        return False, "Not set / missing"
    if is_placeholder(key):
        return False, "Template placeholder"

    url = "https://api.anthropic.com/v1/models"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "User-Agent": "VeriSight-Prober/1.0",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                models = [m["id"] for m in data.get("data", [])]
                model_sample = models[0] if models else "claude"
                return True, f"Valid & Active ({len(models)} models: {model_sample})"
            return False, f"Unexpected response status: {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid API Key (Anthropic rejected: 401 Unauthorized)"
        elif e.code == 403:
            return False, "Access Forbidden (HTTP 403)"
        return False, f"Anthropic error (HTTP {e.code})"
    except urllib.error.URLError as e:
        return False, f"Network unreachable: {e.reason}"
    except Exception as e:
        return False, f"Probe error: {e}"


def probe_local_engine(endpoint: str = "http://localhost:11434", timeout: float = 0.5) -> Tuple[bool, str]:
    """
    Probe on-premise local inference server (Ollama or vLLM).

    Returns:
        (is_valid, status_message)
    """
    ep = (endpoint or "http://localhost:11434").rstrip("/")
    probe_urls = [
        f"{ep}/api/tags",           # Ollama
        f"{ep}/v1/models",           # vLLM / LocalAI
    ]

    for url in probe_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VeriSight-Prober/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if "models" in data:
                        model_names = [m.get("name", "") for m in data["models"]]
                        return True, f"Online ({len(model_names)} models: {', '.join(model_names[:2]) or 'none loaded'})"
                    elif "data" in data:
                        model_names = [m.get("id", "") for m in data["data"]]
                        return True, f"Online ({len(model_names)} models loaded)"
                    return True, "Online"
        except Exception:
            continue

    return False, "Offline (not detected on port)"
