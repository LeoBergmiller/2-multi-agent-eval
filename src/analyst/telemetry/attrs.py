"""Span attribute names.

architecture.md §8: OTel spans on every model call, tool call, and node
transition, using GenAI semantic conventions *plus* the project-specific
attributes below.

These are constants rather than inline strings because the eval harness reads
them back out of `spans.jsonl` — a typo in an attribute name would not fail
anything at write time, it would silently produce a metric of zero.

Every attribute in `GATE0_REQUIRED` has a real value at Gate 0. In particular
`context.bundle_tokens` ships with the first handoff, because it is what makes
the bounded-handoff rule (§6.1 rule 1) measurable rather than merely asserted.
"""

from __future__ import annotations

from typing import Final

# -- GenAI semantic conventions ---------------------------------------------
GEN_AI_OPERATION: Final = "gen_ai.operation.name"
GEN_AI_SYSTEM: Final = "gen_ai.system"
GEN_AI_REQUEST_MODEL: Final = "gen_ai.request.model"
GEN_AI_USAGE_INPUT_TOKENS: Final = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS: Final = "gen_ai.usage.output_tokens"

# -- Project-specific (§8) ---------------------------------------------------
SUBTASK_ID: Final = "subtask.id"
AGENT_ROLE: Final = "agent.role"
TOOL_NAME: Final = "tool.name"
TOOL_ARGS_HASH: Final = "tool.args_hash"
CONTEXT_BUNDLE_TOKENS: Final = "context.bundle_tokens"
RESULT_REF: Final = "result_ref"
COST_USD: Final = "cost.usd"
MODEL_ID: Final = "model.id"
RETRY_COUNT: Final = "retry.count"
VALIDATION_PASSED: Final = "validation.passed"
CASSETTE_MODE: Final = "cassette.mode"

# -- Retrieval (§5) ----------------------------------------------------------
# Emitted on every `search_metric_definitions` tool call. `RETRIEVAL_BACKEND` is the
# one that is easy to omit and expensive to lack: without it a cassette-replayed
# retrieval and a live one are indistinguishable in the eval record, and a nightly
# live arm could be scored as if it had been hermetic.
RETRIEVAL_STRATEGY: Final = "retrieval.strategy"
RETRIEVAL_K: Final = "retrieval.k"
RETRIEVAL_LATENCY_MS: Final = "retrieval.latency_ms"
RETRIEVAL_SCORES: Final = "retrieval.scores"
RETRIEVAL_CORPUS_VERSION: Final = "retrieval.corpus_version"
RETRIEVAL_BACKEND: Final = "retrieval.backend"
RETRIEVAL_DOC_IDS: Final = "retrieval.doc_ids"

#: Attributes that must carry a real value on any span that performs a retrieval.
RETRIEVAL_REQUIRED: Final[frozenset[str]] = frozenset(
    {
        RETRIEVAL_STRATEGY,
        RETRIEVAL_K,
        RETRIEVAL_LATENCY_MS,
        RETRIEVAL_SCORES,
        RETRIEVAL_CORPUS_VERSION,
        RETRIEVAL_BACKEND,
        RETRIEVAL_DOC_IDS,
    }
)

#: Attributes that must carry a real value somewhere in a Gate 0 run. Asserted
#: by the test suite so a regression that silently drops one is caught.
GATE0_REQUIRED: Final[frozenset[str]] = frozenset(
    {
        SUBTASK_ID,
        AGENT_ROLE,
        TOOL_NAME,
        TOOL_ARGS_HASH,
        CONTEXT_BUNDLE_TOKENS,
        RESULT_REF,
        COST_USD,
        MODEL_ID,
        VALIDATION_PASSED,
        CASSETTE_MODE,
    }
)

# -- Span names --------------------------------------------------------------
SPAN_RUN: Final = "run"
SPAN_NODE: Final = "node"
SPAN_LLM_CALL: Final = "llm.call"
SPAN_TOOL_CALL: Final = "tool.call"
