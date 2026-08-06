"""Typed contracts — the only import surface other modules should use.

architecture.md §13: no node emits or accepts an untyped dict. Importing from
`analyst.contracts` rather than its submodules keeps that boundary one obvious
place to audit.
"""

from analyst.contracts.base import Contract
from analyst.contracts.config import (
    AgentsConfig,
    AgentSpec,
    Effort,
    EvalConfig,
    ModelsConfig,
    ModelSpec,
    config_dir,
    load_agents_config,
    load_eval_config,
    load_models_config,
)
from analyst.contracts.errors import Boundary, ContextTransferError, ValidationEvent
from analyst.contracts.refs import ArtifactFormat, ColumnSchema, Evidence, ResultRef
from analyst.contracts.results import AgentResult, FinalAnswer, ResultStatus
from analyst.contracts.retrieval import RetrievalResult, RetrievedChunk
from analyst.contracts.task import (
    GATE0_ROLES,
    AgentRole,
    ContextBundle,
    Handoff,
    Plan,
    SubTask,
    TaskSpec,
)

__all__ = [
    "GATE0_ROLES",
    "AgentResult",
    "AgentRole",
    "AgentSpec",
    "AgentsConfig",
    "ArtifactFormat",
    "Boundary",
    "ColumnSchema",
    "ContextBundle",
    "ContextTransferError",
    "Contract",
    "Effort",
    "EvalConfig",
    "Evidence",
    "FinalAnswer",
    "Handoff",
    "ModelSpec",
    "ModelsConfig",
    "Plan",
    "ResultRef",
    "ResultStatus",
    "RetrievalResult",
    "RetrievedChunk",
    "SubTask",
    "TaskSpec",
    "ValidationEvent",
    "config_dir",
    "load_agents_config",
    "load_eval_config",
    "load_models_config",
]
