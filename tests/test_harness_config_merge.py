"""Tests for ``TeamManager._apply_runtime_max_rounds``.

Settings-UI writes only touch ``max_rounds`` for the orchestrator and
browser-use sub-sections. Sibling harness knobs (``approval_policy``,
``temperature``) come from the CLI/file and must be preserved.
"""

from __future__ import annotations

from typing import Any

from magentic_ui.backend.teammanager.teammanager import TeamManager
from magentic_ui.magentic_ui_config import (
    ApprovalPolicy,
    HarnessConfig,
    OrchestratorHarnessConfig,
    WebSurferHarnessConfig,
)


def _baseline() -> HarnessConfig:
    """Non-default baseline simulating a CLI/file config with custom knobs."""
    return HarnessConfig(
        orchestrator=OrchestratorHarnessConfig(
            approval_policy=ApprovalPolicy.AUTO_APPROVE,
            temperature=0.2,
            max_rounds=42,
        ),
        web_surfer=WebSurferHarnessConfig(max_rounds=77),
    )


def test_no_db_section_keeps_baseline_unchanged() -> None:
    baseline = _baseline()
    merged = TeamManager._apply_runtime_max_rounds(baseline, {"agent_mode": "all"})
    assert merged == baseline


def test_invalid_db_section_keeps_baseline_unchanged() -> None:
    baseline = _baseline()
    merged = TeamManager._apply_runtime_max_rounds(
        baseline, {"harness_config": "not-a-dict"}
    )
    assert merged == baseline


def test_max_rounds_override_preserves_siblings() -> None:
    """A DB write touching ``max_rounds`` must NOT clobber sibling knobs."""
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {
            "orchestrator": {"max_rounds": 99},
            "web_surfer": {"max_rounds": 200},
        }
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    # Overrides applied
    assert merged.orchestrator.max_rounds == 99
    assert merged.web_surfer.max_rounds == 200
    # Sibling fields preserved from baseline
    assert merged.orchestrator.approval_policy == ApprovalPolicy.AUTO_APPROVE
    assert merged.orchestrator.temperature == 0.2


def test_unrelated_db_field_is_ignored() -> None:
    """Only ``max_rounds`` is read from DB; other harness DB fields are
    intentionally ignored to keep this code path narrow (Settings UI
    is the only writer and it only sends ``max_rounds``)."""
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {
            "orchestrator": {
                "approval_policy": "require_approval_all",  # not honored
                "max_rounds": 99,
            },
        }
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    assert merged.orchestrator.max_rounds == 99
    # approval_policy still comes from baseline, not DB.
    assert merged.orchestrator.approval_policy == ApprovalPolicy.AUTO_APPROVE


def test_partial_section_only_orchestrator() -> None:
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {"orchestrator": {"max_rounds": 5}},
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    assert merged.orchestrator.max_rounds == 5
    # web_surfer section absent from DB → baseline preserved.
    assert merged.web_surfer.max_rounds == baseline.web_surfer.max_rounds


def test_partial_section_only_web_surfer() -> None:
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {"web_surfer": {"max_rounds": 250}},
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    assert merged.web_surfer.max_rounds == 250
    assert merged.orchestrator.max_rounds == baseline.orchestrator.max_rounds
    assert merged.orchestrator.approval_policy == ApprovalPolicy.AUTO_APPROVE


def test_non_numeric_max_rounds_is_ignored() -> None:
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {"orchestrator": {"max_rounds": "not-an-int"}},
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    assert merged.orchestrator.max_rounds == baseline.orchestrator.max_rounds


def test_out_of_range_max_rounds_is_ignored() -> None:
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {
            "orchestrator": {"max_rounds": 0},
            "web_surfer": {"max_rounds": 1001},
        },
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    assert merged.orchestrator.max_rounds == baseline.orchestrator.max_rounds
    assert merged.web_surfer.max_rounds == baseline.web_surfer.max_rounds


def test_string_int_max_rounds_is_coerced() -> None:
    """DB values stored as strings (legacy / hand edits) must coerce."""
    baseline = _baseline()
    raw: dict[str, Any] = {
        "harness_config": {"orchestrator": {"max_rounds": "50"}},
    }
    merged = TeamManager._apply_runtime_max_rounds(baseline, raw)
    assert merged.orchestrator.max_rounds == 50
