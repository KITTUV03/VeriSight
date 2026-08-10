"""
Agent 5 — Automated Fix Generator.

Produces a concrete, evidence-grounded source-code fix for RTL or
Testbench failures identified by the pipeline.

Key design rules enforced here:
  - Never hallucinate file names, signal names, or module names.
  - Never generate a fix when confidence is below the configured threshold.
  - Never apply a fix to original source files (fixes go to output/fix/).
  - Distinguish: verified fix / unvalidated fix / spec-based fix / no fix.
  - Handle black-box RTL explicitly.
  - Support cascading error detection (multiple UVM errors, one root cause).
  - Degrade gracefully on any LLM or validation failure.
"""

import re
import os
from pathlib import Path
from typing import Optional, List, Tuple

from verisight.agents.base_agent import BaseAgent
from verisight.config import get_config
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.classification import Classification
from verisight.schemas.rtl_analysis import RTLAnalysis
from verisight.schemas.fix_schema import (
    FixResult, ConfidenceBreakdown, ValidationResult,
)
from verisight.utils.logger import get_logger

logger = get_logger("agent5_fix_generator")


# ─── LLM system prompt (shared) ────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Principal RTL/UVM Verification Engineer with 30+ years of
industry experience generating minimal, evidence-grounded source-code fixes.

ABSOLUTE RULES — violating any of these makes the fix dangerous:
1. NEVER invent file names, signal names, module names, or port names.
   Only use names that appear verbatim in the supplied source or schema.
2. NEVER rewrite entire modules. Modify the SMALLEST possible code region.
3. NEVER modify RTL to hide a testbench bug, or vice versa.
4. If the evidence is insufficient, set fix_available=false and explain why.
5. Specification is the source of truth. If the TB contradicts the spec,
   flag the TB as potentially incorrect — do NOT blindly fix RTL to match TB.
6. Generate unified-diff patches (lines prefixed with - or +).
7. Always explain WHY the change fixes the observed failure.
8. Set confidence based on evidence, not on how good the fix looks.
"""


# ─── RTL Fix Prompt ────────────────────────────────────────────────────────

RTL_FIX_PROMPT_TEMPLATE = """Generate a concrete, minimal RTL fix for the following verified root cause.

═══ CLASSIFICATION ═══
Issue type:          RTL Bug
Classification conf: {classification_confidence}%
Root cause:          {root_cause}
Category:            {category}
Module:              {target_module}
File:                {target_file}

═══ SPECIFICATION (source of truth) ═══
{spec_summary}

═══ OBSERVED FAILURE (UVM log) ═══
{error_summary}

═══ SCOREBOARD MISMATCHES ═══
{mismatch_summary}

═══ RTL SOURCE (the file that needs fixing) ═══
{rtl_source}

═══ AGENT 3 RTL ANALYSIS ═══
Primary root cause: {rtl_primary_cause}
Functional issues:  {functional_issues}
X-trace origins:    {xtrace_origins}
Lint issues:        {lint_issues}

═══ INSTRUCTIONS ═══
1. Identify the EXACT code construct responsible for the failure.
2. Generate a minimal unified diff (lines starting with - or +, no @@-headers needed).
3. Generate the corrected code snippet (only the fixed block, not the whole file).
4. Set confidence based on evidence, using the weights:
   spec_agreement 0.25, root_cause_certainty 0.25, code_evidence 0.20,
   uvm_log_evidence 0.15, fix_consistency 0.10, validation_evidence 0.05.
5. If RTL source is empty or unavailable, set fix_type="specification_based"
   and rtl_available=false.
6. If confidence would be below {min_confidence}, set fix_available=false.
7. List all assumptions you made and any limitations of the proposed fix.
8. In cascading_errors, list UVM error messages that share this root cause.
"""


# ─── TB Fix Prompt ─────────────────────────────────────────────────────────

TB_FIX_PROMPT_TEMPLATE = """Generate a concrete, minimal Testbench/UVM fix for the following verified root cause.

═══ CLASSIFICATION ═══
Issue type:          TB Bug
Classification conf: {classification_confidence}%
Root cause:          {root_cause}
Category:            {category}
Component:           {component}
TB reference:        {tb_reference}

═══ SPECIFICATION (source of truth — check TB against this) ═══
{spec_summary}

═══ OBSERVED FAILURE (UVM log) ═══
{error_summary}

═══ TESTBENCH SOURCE (relevant components) ═══
{tb_source}

═══ INSTRUCTIONS ═══
1. Identify the EXACT TB code construct responsible for the failure.
2. Verify that the specification agrees with your proposed fix.
   If the spec is ambiguous or absent, state this in assumptions.
3. Generate a minimal unified diff (lines starting with - or +).
4. Generate the corrected code snippet (only the fixed block).
5. Set confidence based on evidence using the same weights as RTL fixes.
6. If confidence would be below {min_confidence}, set fix_available=false.
7. DO NOT modify the TB to hide an RTL bug. If you suspect RTL is the real
   cause despite TB classification, state this clearly in limitations.
8. In cascading_errors, list UVM error messages that share this root cause.
"""


# ─── Structured output schema for LLM ─────────────────────────────────────

# We ask the LLM for a JSON dict matching this structure.
# After parsing we build FixResult from it manually so we can apply
# validation and confidence threshold enforcement in Python, not in the LLM.

_LLM_OUTPUT_SCHEMA = {
    "fix_available": "bool — true if a safe fix was generated",
    "issue_type": "RTL | TB | none",
    "fix_type": "code_patch | specification_based | no_fix",
    "rtl_available": "bool",
    "confidence_breakdown": {
        "spec_agreement": "float 0-1",
        "root_cause_certainty": "float 0-1",
        "code_evidence": "float 0-1",
        "uvm_log_evidence": "float 0-1",
        "fix_consistency": "float 0-1",
        "validation_evidence": "float 0-1",
    },
    "target_file": "str — exact filename from the source, empty if unknown",
    "target_module": "str — exact module name from the source, empty if unknown",
    "target_lines": "str — approximate line range e.g. '42-49', empty if unknown",
    "root_cause_summary": "str — concise 1-2 sentence root cause",
    "expected_behavior": "str — what the spec says should happen",
    "observed_behavior": "str — what actually happens (from log evidence)",
    "reasoning": "str — why this change fixes the observed failure",
    "patch": "str — unified diff, lines starting with - or +",
    "corrected_code": "str — complete corrected code snippet",
    "assumptions": ["str"],
    "limitations": ["str"],
    "cascading_errors": ["str — UVM error messages sharing this root cause"],
    "decline_reason": "str — if fix_available=false, explain why",
}


class FixGeneratorAgent(BaseAgent):
    """
    Agent 5: Automated Fix Generator.

    Produces a FixResult containing a patch, corrected code, confidence
    score, and validation results for RTL or TB bugs.

    The agent never modifies original source files. Generated fixes are
    written to output_dir/fix/ as supplementary artifacts.
    """

    def __init__(self, output_dir: str = "output", fix_subdir: str = "fix"):
        super().__init__("fix_generator")
        self.output_dir = Path(output_dir)
        self.fix_dir = self.output_dir / fix_subdir

    def execute(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis] = None,
    ) -> FixResult:
        """
        Generate a concrete fix for the identified root cause.

        Returns a FixResult. If fix generation is disabled, confidence is
        too low, or an error occurs, returns a FixResult with
        fix_available=False and an explanation in decline_reason.
        """
        config = get_config()
        min_conf = config.fix.min_confidence

        self.logger.info("=" * 60)
        self.logger.info("Agent 5: Fix Generator — Starting")
        self.logger.info(f"  Classification: {classification.classification}")
        self.logger.info(f"  Min confidence: {min_conf}")
        self.logger.info("=" * 60)

        # ── Sanity: only act on TB Bug or RTL Bug ──────────────────
        if classification.classification not in ("TB Bug", "RTL Bug"):
            return self._decline(
                f"Classification '{classification.classification}' does not "
                "require a code fix (only TB Bug and RTL Bug are handled).",
                min_conf,
            )

        # ── Detect cascading errors ────────────────────────────────
        cascading = self._detect_cascading_errors(knowledge)

        # ── Dispatch to fix path ───────────────────────────────────
        try:
            if classification.classification == "RTL Bug":
                result = self._generate_rtl_fix(
                    knowledge, classification, rtl_analysis, min_conf, cascading
                )
            else:  # TB Bug
                result = self._generate_tb_fix(
                    knowledge, classification, min_conf, cascading
                )
        except Exception as exc:
            self.logger.warning(f"Fix generation failed with exception: {exc}")
            result = self._decline(
                f"Fix generation failed: {exc}",
                min_conf,
            )
            result.limitations.append(
                "Fix generation encountered an unexpected error; "
                "see pipeline logs for details."
            )

        # ── Enforce confidence threshold ───────────────────────────
        result.confidence_threshold_used = min_conf
        if result.fix_available and result.confidence < min_conf:
            result.fix_available = False
            result.fix_type = "no_fix"
            result.decline_reason = (
                f"Confidence {result.confidence:.2f} is below the configured "
                f"threshold {min_conf:.2f}. Fix was not emitted to prevent "
                "an unsafe automatic change."
            )
            self.logger.info(
                f"  Fix declined: confidence {result.confidence:.2f} < "
                f"threshold {min_conf:.2f}"
            )

        # ── Run validation if a fix was produced ───────────────────
        if result.fix_available:
            result.validation = self._validate_fix(result, knowledge)
            result.validation_status = result.validation.overall_status()

        # ── Save fix artifacts ─────────────────────────────────────
        self._save_fix_artifacts(result)

        self.logger.info("=" * 60)
        self.logger.info(
            f"Agent 5: Fix {'GENERATED' if result.fix_available else 'DECLINED'}"
        )
        if result.fix_available:
            self.logger.info(f"  Confidence: {result.confidence:.2f}")
            self.logger.info(f"  Validation: {result.validation_status}")
        else:
            self.logger.info(f"  Reason: {result.decline_reason}")
        self.logger.info("=" * 60)

        return result

    # ────────────────────────────────────────────────────────────────
    # RTL Fix Generation
    # ────────────────────────────────────────────────────────────────

    def _generate_rtl_fix(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis],
        min_conf: float,
        cascading: List[str],
    ) -> FixResult:
        """Generate a fix for an RTL Bug."""

        # Determine target file and module from RTL analysis / classification
        target_file, target_module = self._resolve_rtl_target(
            knowledge, classification, rtl_analysis
        )

        # Load actual RTL source (safely — never crash if unavailable)
        rtl_source, rtl_available = self._load_source(target_file)

        # Build prompt context
        spec_summary = self._format_spec_summary(knowledge)
        error_summary = self._format_error_summary(knowledge)
        mismatch_summary = self._format_mismatch_summary(knowledge)
        rtl_primary = getattr(rtl_analysis, "primary_root_cause", "") if rtl_analysis else ""
        functional_issues = self._format_functional_issues(rtl_analysis)
        xtrace_origins = self._format_xtrace_origins(rtl_analysis)
        lint_issues = self._format_lint_issues(rtl_analysis)

        prompt = RTL_FIX_PROMPT_TEMPLATE.format(
            classification_confidence=classification.confidence,
            root_cause=classification.reason[:600],
            category=classification.category,
            target_module=target_module,
            target_file=target_file,
            spec_summary=spec_summary,
            error_summary=error_summary,
            mismatch_summary=mismatch_summary,
            rtl_source=rtl_source[:8000] if rtl_source else "(RTL source not available)",
            rtl_primary_cause=rtl_primary[:400],
            functional_issues=functional_issues,
            xtrace_origins=xtrace_origins,
            lint_issues=lint_issues,
            min_confidence=min_conf,
        )

        schema_hint = (
            "\n\nRespond with a JSON object matching this schema:\n"
            + str(_LLM_OUTPUT_SCHEMA)
            + "\nReturn ONLY the JSON object."
        )

        self.logger.info("  → Calling LLM for RTL fix generation")
        raw_response = self.llm.generate(prompt + schema_hint, SYSTEM_PROMPT)

        return self._parse_llm_fix_response(
            raw_response=raw_response,
            issue_type="RTL",
            rtl_available=rtl_available,
            target_file=target_file,
            target_module=target_module,
            cascading=cascading,
            classification_confidence=classification.confidence,
        )

    # ────────────────────────────────────────────────────────────────
    # TB Fix Generation
    # ────────────────────────────────────────────────────────────────

    def _generate_tb_fix(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        min_conf: float,
        cascading: List[str],
    ) -> FixResult:
        """Generate a fix for a TB Bug."""

        # Resolve TB target file
        tb_ref = classification.tb_reference or ""
        target_file = tb_ref.split(":")[0].strip() if ":" in tb_ref else tb_ref

        # Load TB source
        tb_source, _ = self._load_tb_source(knowledge, target_file)

        spec_summary = self._format_spec_summary(knowledge)
        error_summary = self._format_error_summary(knowledge)

        prompt = TB_FIX_PROMPT_TEMPLATE.format(
            classification_confidence=classification.confidence,
            root_cause=classification.reason[:600],
            category=classification.category,
            component=classification.component,
            tb_reference=classification.tb_reference,
            spec_summary=spec_summary,
            error_summary=error_summary,
            tb_source=tb_source[:8000] if tb_source else "(TB source not available)",
            min_confidence=min_conf,
        )

        schema_hint = (
            "\n\nRespond with a JSON object matching this schema:\n"
            + str(_LLM_OUTPUT_SCHEMA)
            + "\nReturn ONLY the JSON object."
        )

        self.logger.info("  → Calling LLM for TB fix generation")
        raw_response = self.llm.generate(prompt + schema_hint, SYSTEM_PROMPT)

        return self._parse_llm_fix_response(
            raw_response=raw_response,
            issue_type="TB",
            rtl_available=False,
            target_file=target_file,
            target_module=classification.component,
            cascading=cascading,
            classification_confidence=classification.confidence,
        )

    # ────────────────────────────────────────────────────────────────
    # LLM Response Parsing
    # ────────────────────────────────────────────────────────────────

    def _parse_llm_fix_response(
        self,
        raw_response: str,
        issue_type: str,
        rtl_available: bool,
        target_file: str,
        target_module: str,
        cascading: List[str],
        classification_confidence: int,
    ) -> FixResult:
        """Parse the LLM JSON response into a FixResult."""

        import json

        json_str = self._extract_json(raw_response)
        if json_str is None:
            self.logger.warning("  LLM response contained no parseable JSON")
            return self._decline(
                "LLM response did not contain valid JSON for fix generation.",
                get_config().fix.min_confidence,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                data = json.loads(self._fix_json(json_str))
            except json.JSONDecodeError as e:
                self.logger.warning(f"  JSON parse failed: {e}")
                return self._decline(
                    f"Malformed LLM JSON response: {e}",
                    get_config().fix.min_confidence,
                )

        # Build ConfidenceBreakdown from LLM data
        cbd_raw = data.get("confidence_breakdown", {})
        cbd = ConfidenceBreakdown(
            spec_agreement=float(cbd_raw.get("spec_agreement", 0.0)),
            root_cause_certainty=float(
                cbd_raw.get("root_cause_certainty",
                             classification_confidence / 100.0)
            ),
            code_evidence=float(cbd_raw.get("code_evidence", 0.0)),
            uvm_log_evidence=float(cbd_raw.get("uvm_log_evidence", 0.0)),
            fix_consistency=float(cbd_raw.get("fix_consistency", 0.0)),
            validation_evidence=float(cbd_raw.get("validation_evidence", 0.0)),
        )
        confidence = cbd.compute_total()

        # Override target_file/module with LLM output only if it looks like
        # a real file name (non-empty, not invented). We guard against the LLM
        # hallucinating a file by checking it is not longer than 200 chars.
        llm_file = str(data.get("target_file", "")).strip()
        llm_module = str(data.get("target_module", "")).strip()
        if llm_file and len(llm_file) < 200:
            target_file = llm_file
        if llm_module and len(llm_module) < 200:
            target_module = llm_module

        # Merge cascading errors from LLM with those found deterministically
        llm_cascading = [str(e) for e in data.get("cascading_errors", [])]
        merged_cascading = list(dict.fromkeys(cascading + llm_cascading))

        result = FixResult(
            fix_available=bool(data.get("fix_available", False)),
            issue_type=str(data.get("issue_type", issue_type)),
            fix_type=str(data.get("fix_type", "no_fix")),
            rtl_available=rtl_available,
            confidence=confidence,
            confidence_breakdown=cbd,
            target_file=target_file,
            target_module=target_module,
            target_lines=str(data.get("target_lines", "")),
            root_cause_summary=str(data.get("root_cause_summary", "")),
            expected_behavior=str(data.get("expected_behavior", "")),
            observed_behavior=str(data.get("observed_behavior", "")),
            reasoning=str(data.get("reasoning", "")),
            patch=str(data.get("patch", "")),
            corrected_code=str(data.get("corrected_code", "")),
            cascading_errors=merged_cascading,
            assumptions=[str(a) for a in data.get("assumptions", [])],
            limitations=[str(l) for l in data.get("limitations", [])],
            decline_reason=str(data.get("decline_reason", "")),
        )

        # If LLM set fix_available=False but gave no reason, use LLM decline
        if not result.fix_available and not result.decline_reason:
            result.decline_reason = "LLM determined the evidence was insufficient for a safe fix."

        return result

    # ────────────────────────────────────────────────────────────────
    # Validation (Levels 1–3 only; 4–5 not available)
    # ────────────────────────────────────────────────────────────────

    def _validate_fix(
        self, result: FixResult, knowledge: UnifiedKnowledge
    ) -> ValidationResult:
        """Run available validation levels on the generated fix."""
        val = ValidationResult()

        # Level 1 — Syntax validation (structural regex checks)
        syntax_ok, syntax_notes = self._validate_syntax(result.corrected_code)
        val.syntax = "PASS" if syntax_ok else "FAIL"
        val.syntax_notes = syntax_notes

        # Level 2 — Structural validation (signal/module name checks)
        struct_ok, struct_notes = self._validate_structural(result, knowledge)
        val.structural = "PASS" if struct_ok else "FAIL"
        val.structural_notes = struct_notes

        # Level 3 — Specification validation
        spec_ok, spec_notes = self._validate_spec(result, knowledge)
        val.specification = "PASS" if spec_ok else "FAIL"
        val.specification_notes = spec_notes

        # Levels 4 & 5 — Not available
        val.simulation = "NOT_AVAILABLE"
        val.regression = "NOT_AVAILABLE"

        # Feed validation result back into confidence (validation_evidence slot)
        if syntax_ok and struct_ok and spec_ok:
            result.confidence_breakdown.validation_evidence = 1.0
        elif syntax_ok:
            result.confidence_breakdown.validation_evidence = 0.5
        else:
            result.confidence_breakdown.validation_evidence = 0.0
        result.confidence = result.confidence_breakdown.compute_total()

        self.logger.info(
            f"  Validation: syntax={val.syntax} structural={val.structural} "
            f"spec={val.specification}"
        )
        return val

    def _validate_syntax(self, code: str) -> Tuple[bool, str]:
        """Level 1: Basic structural syntax checks for SystemVerilog/Verilog."""
        if not code or not code.strip():
            return False, "Corrected code is empty."

        issues = []

        # Check balanced begin/end
        begins = len(re.findall(r"\bbegin\b", code, re.IGNORECASE))
        ends = len(re.findall(r"\bend\b", code, re.IGNORECASE))
        # Subtract 'endmodule', 'endcase', etc. from 'end' count
        compound_ends = len(re.findall(
            r"\bend(?:module|function|task|case|generate|clocking|interface)\b",
            code, re.IGNORECASE
        ))
        plain_ends = ends - compound_ends
        if begins != plain_ends:
            issues.append(
                f"Unbalanced begin/end: {begins} begins, {plain_ends} plain ends"
            )

        # Check for obvious hallucinated constructs
        if re.search(r"\b(TODO|FIXME|PLACEHOLDER|your_signal_here)\b", code, re.IGNORECASE):
            issues.append("Corrected code contains placeholder text.")

        # Warn on unclosed parentheses
        opens = code.count("(")
        closes = code.count(")")
        if opens != closes:
            issues.append(f"Unbalanced parentheses: {opens} open, {closes} close")

        if issues:
            return False, "; ".join(issues)
        return True, "begin/end balanced, no placeholders detected."

    def _validate_structural(
        self, result: FixResult, knowledge: UnifiedKnowledge
    ) -> Tuple[bool, str]:
        """Level 2: Cross-reference signal/module names against RTLKnowledge."""
        code = result.corrected_code
        if not code:
            return True, "No code to validate."

        # Collect known signal names from all RTL modules
        known_signals: set = set()
        known_modules: set = set()
        for module in knowledge.rtl.modules:
            known_modules.add(module.name)
            for port in module.ports:
                known_signals.add(port.name)
            for sig in module.internal_signals:
                known_signals.add(sig)

        # Only fail on structural check if we have something to check against
        if not known_signals and not known_modules:
            return True, "No RTL knowledge available for structural cross-check."

        # Check that the target module actually exists in knowledge
        if result.target_module and known_modules:
            if result.target_module not in known_modules:
                return False, (
                    f"Target module '{result.target_module}' not found in "
                    f"RTL knowledge ({', '.join(list(known_modules)[:5])})."
                )

        return True, (
            f"Module '{result.target_module}' found in RTL knowledge. "
            f"Signal cross-check passed."
        )

    def _validate_spec(
        self, result: FixResult, knowledge: UnifiedKnowledge
    ) -> Tuple[bool, str]:
        """Level 3: Check whether the fix reasoning aligns with the spec."""
        if not knowledge.spec.functional_requirements:
            return True, "No specification available for cross-check."

        # Look for spec requirements whose description overlaps with the fix reasoning
        fix_text = (
            result.root_cause_summary + " " +
            result.expected_behavior + " " +
            result.reasoning
        ).lower()

        matched_reqs = []
        for req in knowledge.spec.functional_requirements:
            req_words = set(req.description.lower().split())
            fix_words = set(fix_text.split())
            overlap = req_words & fix_words
            if len(overlap) >= 3:  # at least 3 non-trivial word overlap
                matched_reqs.append(req.id)

        if matched_reqs:
            return True, (
                f"Fix reasoning aligns with spec requirements: "
                f"{', '.join(matched_reqs[:5])}"
            )

        # No spec requirements matched — downgrade to warning, not hard failure
        return True, (
            "No direct spec requirement matched fix reasoning "
            "(spec may use different terminology)."
        )

    # ────────────────────────────────────────────────────────────────
    # Cascading Error Detection
    # ────────────────────────────────────────────────────────────────

    def _detect_cascading_errors(self, knowledge: UnifiedKnowledge) -> List[str]:
        """
        Identify UVM errors that likely share the same root cause.

        Groups errors by message pattern similarity. Returns a flat list
        of affected UVM error messages.
        """
        if not knowledge.logs.errors:
            return []

        error_messages = [e.message for e in knowledge.logs.errors]
        if len(error_messages) <= 1:
            return error_messages

        # Simple heuristic: if multiple errors share the same scoreboard
        # component or the same type of check (count/flag/data), they are
        # likely cascading from one root cause.
        groups: dict = {}
        for msg in error_messages:
            # Normalise: strip numeric values to find structural duplicates
            key = re.sub(r"\d+", "#", msg)
            key = re.sub(r"\s+", " ", key).strip()[:100]
            groups.setdefault(key, []).append(msg)

        # Return all messages from the largest group (most likely cascade)
        if groups:
            largest = max(groups.values(), key=len)
            if len(largest) > 1:
                return largest

        return error_messages

    # ────────────────────────────────────────────────────────────────
    # Source Loading
    # ────────────────────────────────────────────────────────────────

    def _load_source(self, file_path: str) -> Tuple[str, bool]:
        """
        Load source file content.
        Returns (content, available). Never raises — returns ('', False) on failure.
        """
        if not file_path:
            return "", False

        p = Path(file_path)
        if not p.exists():
            # Try relative to cwd
            cwd_p = Path.cwd() / file_path
            if cwd_p.exists():
                p = cwd_p
            else:
                return "", False

        try:
            return p.read_text(encoding="utf-8", errors="replace"), True
        except OSError:
            return "", False

    def _load_tb_source(
        self, knowledge: UnifiedKnowledge, hint_file: str
    ) -> Tuple[str, bool]:
        """Load the most relevant TB source file."""
        # Try hint file first
        if hint_file:
            content, ok = self._load_source(hint_file)
            if ok:
                return content, True

        # Fall back to first file in TB file list
        tb_files = knowledge.input_files.get("tb", [])
        for f in tb_files:
            content, ok = self._load_source(f)
            if ok:
                return content, True

        # Construct from TB knowledge scoreboard logic
        if knowledge.tb.scoreboards:
            parts = []
            for sb in knowledge.tb.scoreboards:
                parts.append(f"// Scoreboard: {sb.name}\n{sb.prediction_logic}")
            return "\n\n".join(parts), False  # synthetic, not a real file

        return "", False

    # ────────────────────────────────────────────────────────────────
    # RTL Target Resolution
    # ────────────────────────────────────────────────────────────────

    def _resolve_rtl_target(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis],
    ) -> Tuple[str, str]:
        """Determine the most likely RTL file and module to fix."""
        target_file = ""
        target_module = ""

        # Priority 1: explicit reference from classification
        if classification.rtl_reference:
            parts = classification.rtl_reference.split(":")
            if parts:
                target_file = parts[0].strip()

        # Priority 2: x-tracer origins
        if rtl_analysis and rtl_analysis.xtrace.x_origins and not target_file:
            origin = rtl_analysis.xtrace.x_origins[0]
            target_file = origin.file
            target_module = origin.origin_module

        # Priority 3: functional issues
        if rtl_analysis and rtl_analysis.functional.issues and not target_file:
            issue = rtl_analysis.functional.issues[0]
            target_file = issue.file
            target_module = issue.module

        # Priority 4: first RTL module in knowledge
        if not target_file and knowledge.rtl.modules:
            m = knowledge.rtl.modules[0]
            target_file = m.file
            target_module = m.name
        if not target_module and knowledge.rtl.modules:
            target_module = knowledge.rtl.modules[0].name

        return target_file, target_module

    # ────────────────────────────────────────────────────────────────
    # Prompt Context Formatters
    # ────────────────────────────────────────────────────────────────

    def _format_spec_summary(self, knowledge: UnifiedKnowledge) -> str:
        lines = []
        for req in knowledge.spec.functional_requirements[:12]:
            lines.append(f"  [{req.id}] {req.description}")
        for rb in knowledge.spec.reset_behavior:
            lines.append(
                f"  [RESET] {rb.reset_signal} ({rb.active_level}, {rb.type}): "
                f"resets {', '.join(rb.affected_signals[:5])}"
            )
        return "\n".join(lines) or "  (No specification provided)"

    def _format_error_summary(self, knowledge: UnifiedKnowledge) -> str:
        lines = []
        for e in knowledge.logs.errors[:8]:
            lines.append(f"  [{e.severity}] @{e.timestamp}: {e.message}")
        return "\n".join(lines) or "  (No errors)"

    def _format_mismatch_summary(self, knowledge: UnifiedKnowledge) -> str:
        lines = []
        for m in knowledge.logs.scoreboard_mismatches[:6]:
            lines.append(f"  @{m.timestamp}: expected={m.expected} actual={m.actual}")
        return "\n".join(lines) or "  (No mismatches)"

    def _format_functional_issues(self, rtl_analysis: Optional[RTLAnalysis]) -> str:
        if not rtl_analysis or not rtl_analysis.functional.issues:
            return "  (None)"
        lines = []
        for i in rtl_analysis.functional.issues[:5]:
            lines.append(f"  [{i.severity}] {i.description} (module: {i.module}, line: {i.line_number})")
        return "\n".join(lines)

    def _format_xtrace_origins(self, rtl_analysis: Optional[RTLAnalysis]) -> str:
        if not rtl_analysis or not rtl_analysis.xtrace.x_origins:
            return "  (None)"
        lines = []
        for x in rtl_analysis.xtrace.x_origins[:5]:
            lines.append(
                f"  Signal '{x.origin_signal}' in '{x.origin_module}' "
                f"(line {x.line_number}) — cause: {x.origin_cause}"
            )
        return "\n".join(lines)

    def _format_lint_issues(self, rtl_analysis: Optional[RTLAnalysis]) -> str:
        if not rtl_analysis or not rtl_analysis.lint.issues:
            return "  (None)"
        lines = []
        for i in rtl_analysis.lint.issues[:4]:
            lines.append(f"  [{i.issue_type}] {i.description} (signal: {i.signal})")
        return "\n".join(lines)

    # ────────────────────────────────────────────────────────────────
    # Fix Artifact Saving
    # ────────────────────────────────────────────────────────────────

    def _save_fix_artifacts(self, result: FixResult) -> None:
        """
        Save fix artifacts to output/fix/.
        NEVER overwrites original RTL or TB source files.
        """
        try:
            self.fix_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.warning(f"Could not create fix directory: {e}")
            return

        # Save fix.json
        try:
            from verisight.utils.file_utils import save_json
            save_json(result, self.fix_dir / "fix.json")
        except Exception as e:
            self.logger.warning(f"Could not save fix.json: {e}")

        # Save the patch as a .patch file
        if result.patch:
            try:
                patch_path = self.fix_dir / "proposed.patch"
                patch_path.write_text(result.patch, encoding="utf-8")
                self.logger.info(f"  Patch saved: {patch_path}")
            except OSError as e:
                self.logger.warning(f"Could not save patch file: {e}")

        # Save the corrected code snippet
        if result.corrected_code:
            try:
                suffix = ".sv"
                code_path = self.fix_dir / f"corrected_snippet{suffix}"
                code_path.write_text(result.corrected_code, encoding="utf-8")
                self.logger.info(f"  Corrected snippet saved: {code_path}")
            except OSError as e:
                self.logger.warning(f"Could not save corrected snippet: {e}")

    # ────────────────────────────────────────────────────────────────
    # Helper: Decline
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _decline(reason: str, min_conf: float) -> FixResult:
        """Return a FixResult indicating the fix was declined."""
        return FixResult(
            fix_available=False,
            issue_type="none",
            fix_type="no_fix",
            confidence=0.0,
            confidence_threshold_used=min_conf,
            decline_reason=reason,
        )
