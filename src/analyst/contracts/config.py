"""YAML configuration deserialised into frozen models.

architecture.md §1 requires YAML configs deserialised into frozen models, and
§13 forbids hardcoded values. Config schemas are themselves typed contracts, so
they live here rather than in a separate loader module.

The price table gets special treatment. §9 says the sweep cost is "a README
metric — measure it, don't estimate it", which only holds if a run's cost can be
recomputed later. So `ModelsConfig` exposes `price_table_hash`, recorded in every
run's `meta.json`: edit a price afterwards and the hash changes, so old runs are
visibly priced under a different table rather than silently re-costed.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import Field, model_validator

from analyst.contracts.base import Contract
from analyst.contracts.task import AgentRole

#: Effort levels accepted by the current models. Note there is no temperature
#: knob: `temperature`/`top_p`/`top_k` are rejected with a 400 on Opus 5 and
#: Sonnet 5, which is why §7.5's determinism story is cassette replay plus n=3
#: and a tolerance band, not temperature 0.
Effort = Literal["low", "medium", "high", "xhigh", "max"]


def _repo_root() -> Path:
    # src/analyst/contracts/config.py -> repo root
    return Path(__file__).resolve().parents[3]


def config_dir() -> Path:
    """Config directory, overridable for tests. Never an absolute literal."""
    override = os.environ.get("ANALYST_CONFIG_DIR")
    return Path(override) if override else _repo_root() / "config"


class ModelSpec(Contract):
    """One role's model binding and its prices."""

    id: str
    effort: Effort = "high"
    max_tokens: int = Field(
        gt=0,
        description=(
            "Caps thinking AND response text together on current models. Too "
            "tight and the Planner truncates mid-plan."
        ),
    )
    price_input_per_mtok: float = Field(ge=0)
    price_output_per_mtok: float = Field(ge=0)

    def cost_usd(self, *, input_tokens: int, output_tokens: int) -> float:
        """Cost of one call. The only place tokens become dollars."""
        return (
            input_tokens * self.price_input_per_mtok
            + output_tokens * self.price_output_per_mtok
        ) / 1_000_000


class ModelsConfig(Contract):
    """config/models.yaml — per-role model bindings plus a dated price table."""

    checked: date = Field(
        description="Date the prices were verified against the vendor pricing page"
    )
    roles: dict[AgentRole, ModelSpec]

    @model_validator(mode="after")
    def _gate0_roles_present(self) -> Self:
        from analyst.contracts.task import GATE0_ROLES

        missing = GATE0_ROLES - self.roles.keys()
        if missing:
            names = ", ".join(sorted(r.value for r in missing))
            raise ValueError(f"models.yaml is missing Gate 0 roles: {names}")
        return self

    @property
    def price_table_hash(self) -> str:
        """Stable hash of prices + check date. Recorded in every meta.json."""
        payload = {
            "checked": self.checked.isoformat(),
            "prices": {
                role.value: [
                    spec.id,
                    spec.price_input_per_mtok,
                    spec.price_output_per_mtok,
                ]
                for role, spec in sorted(self.roles.items())
            },
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class AgentSpec(Contract):
    """config/agents.yaml — one node's prompt, budget, and tool allow-list."""

    prompt: str
    max_steps: int = Field(gt=0, default=8)
    max_usd: float = Field(gt=0, default=0.25)
    allowed_tools: tuple[str, ...] = ()


class AgentsConfig(Contract):
    roles: dict[AgentRole, AgentSpec]


class EvalConfig(Contract):
    """config/eval.yaml — Gate 0 scores one metric; floors are the backstop."""

    task_success_floor: float = Field(ge=0.0, le=1.0, default=1.0)
    require_verified_ground_truth: bool = Field(
        default=True,
        description=(
            "When true, a task whose ground_truth.status is still 'draft' is "
            "reported but never counted as a pass. reference_sql and "
            "ground_truth are human-verified artifacts (§13, D17)."
        ),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Config file not found: {path}. Run from the repo root, or set "
            f"ANALYST_CONFIG_DIR."
        )
    with path.open() as fh:
        loaded = yaml.safe_load(fh)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a YAML mapping, got {type(loaded)}")
    return loaded


def load_models_config(path: Path | None = None) -> ModelsConfig:
    return ModelsConfig.model_validate(_load_yaml(path or config_dir() / "models.yaml"))


def load_agents_config(path: Path | None = None) -> AgentsConfig:
    return AgentsConfig.model_validate(_load_yaml(path or config_dir() / "agents.yaml"))


def load_eval_config(path: Path | None = None) -> EvalConfig:
    return EvalConfig.model_validate(_load_yaml(path or config_dir() / "eval.yaml"))
