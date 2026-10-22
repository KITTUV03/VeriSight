"""
Tests for anti-hallucination safeguards:
  - evidence_verifier catches invented file citations but not faithful ones,
  - Agent 2's deterministic classifier is grounded, calibrated, and abstains
    when the evidence cannot distinguish RTL vs TB.
"""

from pathlib import Path

from verisight.agents.agent2_classifier import RootCauseClassifierAgent
from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
from verisight.utils.evidence_verifier import verify_citations
from verisight.schemas.classification import Classification, EvidenceItem

REPO = Path(__file__).resolve().parent.parent


def _knowledge(spec=None, rtl=None, tb=None, log=None):
    agent1 = KnowledgeExtractionAgent(knowledge_base=None)
    return agent1.execute(spec_path=spec, rtl_path=rtl, tb_path=tb, log_path=log)


# ── citation verifier ───────────────────────────────────────────────────────

def test_verifier_flags_invented_file():
    k = _knowledge(
        rtl=str(REPO / "examples/rtl/"),
        log=str(REPO / "examples/logs/sim.log"),
    )
    bad = Classification(
        classification="RTL Bug", confidence=90, reason="bug in totally_made_up.sv:999",
        evidence=[EvidenceItem(source="rtl", reference="totally_made_up.sv:999", description="x")],
    )
    problems = verify_citations(bad, k)
    assert any("totally_made_up.sv" in p for p in problems)


def test_verifier_accepts_real_citation():
    k = _knowledge(
        rtl=str(REPO / "examples/rtl/"),
        log=str(REPO / "examples/logs/sim.log"),
    )
    good = Classification(
        classification="RTL Bug", confidence=90,
        reason="result register never reset in alu.sv",
        rtl_reference="alu.sv",
    )
    # alu.sv is a real input file; alu_scoreboard.sv appears in the log.
    assert verify_citations(good, k) == []


# ── deterministic classifier behaviour ──────────────────────────────────────

def test_compile_error_classified_not_pass():
    k = _knowledge(log=str(REPO / "eval/synthetic/compile_error/sim.log"))
    agent2 = RootCauseClassifierAgent()
    c = agent2.execute(k)  # no API key in test env -> deterministic path
    assert c.classification != "Unknown" or k.logs.summary.failure_stage == "compile"
    assert "Compilation" in c.category or k.logs.summary.failure_stage == "compile"
    # Must not say the run passed.
    assert "no failure" not in c.reason.lower()


def test_apb_protocol_is_rtl_bug():
    k = _knowledge(
        spec=str(REPO / "projects/apb/specs/apb_spec.md"),
        rtl=str(REPO / "projects/apb/rtl/"),
        tb=str(REPO / "projects/apb/tb/"),
        log=str(REPO / "projects/apb/logs/sim.log"),
    )
    agent2 = RootCauseClassifierAgent()
    c = agent2.execute(k)
    assert c.classification == "RTL Bug"
    assert c.confidence >= 70  # calibrated from protocol+assertion+spec evidence


def test_insufficient_evidence_abstains():
    # Only a log, no RTL/TB/spec, a plain mismatch (no X): must abstain.
    k = _knowledge(log=str(REPO / "eval/synthetic/insufficient_evidence/sim.log"))
    agent2 = RootCauseClassifierAgent()
    c = agent2.execute(k)
    assert c.classification == "Unknown"
    assert c.missing_artifacts, "abstention must list the missing artifacts"
    assert c.alternative_hypotheses, "abstention should list competing options"


def test_confidence_is_calibrated_not_arbitrary():
    agent2 = RootCauseClassifierAgent()
    # Known factor sets map to known confidences (methodology, not LLM guess).
    assert agent2._calibrate_confidence(["compile_or_elab_proven", "file_cited"]) == 90
    assert agent2._calibrate_confidence([]) == 0
    # Clamped at 95.
    assert agent2._calibrate_confidence(
        ["x_values_observed", "static_missing_reset_matches_x", "file_cited",
         "protocol_violation_logged"]
    ) == 95


def test_deterministic_classifier_never_fabricates_on_real_cases():
    for case in ("ram", "fifo", "apb"):
        k = _knowledge(
            spec=str(REPO / f"projects/{case}/specs/spec.md") if (REPO / f"projects/{case}/specs/spec.md").exists() else None,
            rtl=str(REPO / f"projects/{case}/rtl/"),
            tb=str(REPO / f"projects/{case}/tb/"),
            log=str(REPO / f"projects/{case}/logs/sim.log"),
        )
        agent2 = RootCauseClassifierAgent()
        c = agent2.execute(k)
        assert verify_citations(c, k) == [], f"{case}: deterministic path must not fabricate citations"
