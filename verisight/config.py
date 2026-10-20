"""
Global configuration for VeriSight framework.

Manages LLM provider settings, ChromaDB paths, logging levels,
and pipeline configuration. Reads from environment variables
and .env files.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = ""
    api_key: str = ""
    model_name: str = ""
    temperature: float = 0.1
    max_output_tokens: int = 16000
    max_retries: int = 3
    airgap: bool = False
    local_endpoint: str = ""
    anonymize_rtl: bool = False

    def __post_init__(self):
        # Resolve Air-Gap policy
        env_airgap = os.getenv("VERISIGHT_AIRGAP")
        if env_airgap is not None:
            self.airgap = env_airgap.lower() in ("1", "true", "yes", "on")

        # Resolve local endpoint (for Ollama, vLLM, or on-premise inference servers)
        if not self.local_endpoint:
            self.local_endpoint = os.getenv(
                "VERISIGHT_LOCAL_ENDPOINT", "http://localhost:11434"
            )

        # Resolve RTL anonymization flag
        env_anon = os.getenv("VERISIGHT_ANONYMIZE_RTL")
        if env_anon is not None:
            self.anonymize_rtl = env_anon.lower() in ("1", "true", "yes", "on")

        # Resolve provider: explicit arg > env var > airgap policy > auto-detect > default
        if not self.provider:
            env_provider = os.getenv("VERISIGHT_PROVIDER")
            if env_provider:
                self.provider = env_provider.lower()
            elif self.airgap:
                self.provider = "ollama"
            else:
                self.provider = "gemini"
        else:
            self.provider = self.provider.lower()

        # Model override from environment (only when not explicitly set)
        if not self.model_name:
            model_override = os.getenv("VERISIGHT_MODEL")
            if model_override:
                self.model_name = model_override

        # Auto-detect provider if model name starts with claude
        if self.model_name and self.model_name.lower().startswith("claude"):
            self.provider = "anthropic"
        # Auto-switch to anthropic if ANTHROPIC_API_KEY is present and GEMINI_API_KEY is missing
        elif self.provider == "gemini" and not os.getenv("GEMINI_API_KEY") and (os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")):
            self.provider = "anthropic"

        # Normalize aliases
        if self.provider in ("claude",):
            self.provider = "anthropic"
        elif self.provider in ("local", "vllm", "localai", "airgap"):
            pass

        # Set default model name if not provided
        if not self.model_name:
            if self.provider in ("ollama", "local", "vllm", "localai", "airgap"):
                self.model_name = "deepseek-coder:33b"
            elif self.provider == "anthropic":
                self.model_name = "claude-sonnet-5"
            else:
                self.model_name = "gemini-2.0-flash"

        # Resolve API key based on provider
        if not self.api_key and self.provider not in ("ollama", "local", "vllm", "localai", "airgap"):
            if self.provider == "anthropic":
                self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY", "")
            else:
                self.api_key = os.getenv("GEMINI_API_KEY", "")


@dataclass
class ChromaConfig:
    """ChromaDB configuration."""
    persist_path: str = ""
    embedding_model: str = "default"

    def __post_init__(self):
        if not self.persist_path:
            self.persist_path = os.getenv(
                "VERISIGHT_CHROMA_PATH",
                str(Path(__file__).parent.parent / "verisight_knowledge_db")
            )


@dataclass
class PipelineConfig:
    """Pipeline execution configuration."""
    save_intermediates: bool = True
    enable_rag: bool = True
    rag_n_results: int = 5
    verbose: bool = False
    output_dir: str = "output"


@dataclass
class XTracerConfig:
    """
    Configuration for real X-propagation root-cause tracing via x-tracer
    (https://github.com/kuchlous/x-tracer), synthesizing a netlist with
    yosys when the user doesn't supply one. Entirely optional — when
    disabled, Agent 3 falls back to its static heuristic X analysis.
    """
    enabled: bool = False
    netlist_paths: List[str] = field(default_factory=list)
    top_module: str = ""
    vcd_path: str = ""
    signal: str = ""
    time_ps: Optional[int] = None
    xtracer_path: str = ""
    max_depth: int = 100

    def __post_init__(self):
        if not self.xtracer_path:
            env_path = os.getenv("VERISIGHT_XTRACER_PATH")
            if env_path:
                self.xtracer_path = env_path
            else:
                candidate = Path(__file__).parent.parent / "third_party" / "x-tracer" / "x_tracer.py"
                if candidate.exists():
                    self.xtracer_path = str(candidate)


@dataclass
class FixConfig:
    """
    Configuration for Agent 5 — Automated Fix Generator.

    enabled=False makes Agent 5 a no-op, preserving the existing pipeline
    behaviour exactly. min_confidence is the evidence-weighted threshold
    below which the agent declines to emit a fix.
    """
    enabled: bool = True
    min_confidence: float = 0.70
    fix_output_subdir: str = "fix"   # relative to pipeline output_dir

    def __post_init__(self):
        env_enabled = os.getenv("VERISIGHT_FIX_ENABLED")
        if env_enabled is not None:
            self.enabled = env_enabled.lower() not in ("0", "false", "no")

        env_conf = os.getenv("VERISIGHT_FIX_MIN_CONFIDENCE")
        if env_conf is not None:
            try:
                self.min_confidence = float(env_conf)
            except ValueError:
                pass


@dataclass
class VeriSightConfig:
    """Top-level configuration for the VeriSight framework."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    xtracer: XTracerConfig = field(default_factory=XTracerConfig)
    fix: FixConfig = field(default_factory=FixConfig)
    log_level: str = ""

    def __post_init__(self):
        if not self.log_level:
            self.log_level = os.getenv("VERISIGHT_LOG_LEVEL", "INFO")

    @classmethod
    def from_defaults(cls) -> "VeriSightConfig":
        """Create configuration with all defaults from environment."""
        return cls()


# Global singleton configuration
_config: Optional[VeriSightConfig] = None


def get_config() -> VeriSightConfig:
    """Get or create the global configuration singleton."""
    global _config
    if _config is None:
        _config = VeriSightConfig.from_defaults()
    return _config


def set_config(config: VeriSightConfig) -> None:
    """Override the global configuration."""
    global _config
    _config = config
