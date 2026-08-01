"""
Global configuration for VeriSight framework.

Manages LLM provider settings, ChromaDB paths, logging levels,
and pipeline configuration. Reads from environment variables
and .env files.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "gemini"
    api_key: str = ""
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.1
    max_output_tokens: int = 8192
    max_retries: int = 3

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv("GEMINI_API_KEY", "")
        model_override = os.getenv("VERISIGHT_MODEL")
        if model_override:
            self.model_name = model_override


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
class VeriSightConfig:
    """Top-level configuration for the VeriSight framework."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
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
