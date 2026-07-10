"""Runtime configuration model for OpenMontage.

Loads config.yaml, merges with env overrides, and provides typed access.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class BudgetMode(str, Enum):
    OBSERVE = "observe"
    WARN = "warn"
    CAP = "cap"


class CheckpointPolicy(str, Enum):
    GUIDED = "guided"
    MANUAL_ALL = "manual_all"
    AUTO_NONCREATIVE = "auto_noncreative"


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    base_url: Optional[str] = None


class BudgetConfig(BaseModel):
    mode: BudgetMode = BudgetMode.WARN
    total_usd: float = 10.0
    reserve_pct: float = 0.10
    single_action_approval_usd: float = 0.50
    require_approval_for_new_paid_tool: bool = True


class CheckpointConfig(BaseModel):
    policy: CheckpointPolicy = CheckpointPolicy.GUIDED
    storage_dir: str = "pipeline"


class OutputConfig(BaseModel):
    default_format: str = "mp4"
    default_codec: str = "libx264"
    default_audio_codec: str = "aac"
    default_resolution: str = "1920x1080"
    default_fps: int = 30
    default_crf: int = 23


class PathsConfig(BaseModel):
    pipeline_dir: str = "pipeline"
    library_dir: str = "library"
    styles_dir: str = "styles"
    skills_dir: str = "skills"
    output_dir: str = "output"


class OpenMontageConfig(BaseModel):
    """Top-level runtime configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "OpenMontageConfig":
        """Load config from YAML file and environment overrides."""
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config.yaml"

        if config_path.exists():
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
            return cls.model_validate(_apply_env_overrides(raw))

        return cls.model_validate(_apply_env_overrides({}))

    def resolve_path(self, key: str, project_root: Optional[Path] = None) -> Path:
        """Resolve a relative path from PathsConfig against project root."""
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        value = getattr(self.paths, key)
        return (project_root / value).resolve()


def _apply_env_overrides(raw: dict) -> dict:
    """Apply deployment-friendly environment overrides to config data."""
    config = dict(raw)
    llm = dict(config.get("llm") or {})

    provider = os.environ.get("OPENMONTAGE_LLM_PROVIDER") or os.environ.get("LLM_PROVIDER")
    model = (
        os.environ.get("OPENMONTAGE_LLM_MODEL")
        or os.environ.get("LLM_MODEL")
        or os.environ.get("OLLAMA_MODEL")
    )
    base_url = (
        os.environ.get("OPENMONTAGE_LLM_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or os.environ.get("OLLAMA_BASE_URL")
    )

    if not provider and (os.environ.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_BASE_URL")):
        provider = "ollama"
    if provider:
        llm["provider"] = provider
    if model:
        llm["model"] = model
    if base_url:
        llm["base_url"] = base_url
    if "OPENMONTAGE_LLM_TEMPERATURE" in os.environ:
        llm["temperature"] = float(os.environ["OPENMONTAGE_LLM_TEMPERATURE"])
    if "OPENMONTAGE_LLM_MAX_TOKENS" in os.environ:
        llm["max_tokens"] = int(os.environ["OPENMONTAGE_LLM_MAX_TOKENS"])

    if llm:
        config["llm"] = llm

    return config
