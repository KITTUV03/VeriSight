"""
Agent 2 — Root Cause Classifier.

Determines whether the failure is caused by:
- TB Bug (testbench issue)
- RTL Bug (design issue)
- Spec Bug (specification ambiguity)
- Unknown (insufficient evidence)

Uses structured reasoning with the 9 decision rules and provides
confidence scores with evidence chains.
"""

import json
import re
from typing import Optional

from verisight.agents.base_agent import BaseAgent
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.classification import Classification, EvidenceItem, ClassificationReasoning
from verisight.tools.xtracer_runner import timestamp_to_ps
from verisight.utils.logger import get_logger

logger = get_logger("agent2_classifier")

SYSTEM_PROMPT = """You are a Principal ASIC Verification Engineer with 30+ years of experience
in UVM testbench debugging and RTL root cause analysis.

Your task is to classify the root cause of a simulation failure as ONE of:
- "TB Bug" — The testbench (driver, monitor, scoreboard, sequence, etc.) has a bug
- "RTL Bug" — The RTL design has a bug
- "Spec Bug" — The specification is ambiguous or contradictory
- "Unknown" — Insufficient evidence to determine

DECISION RULES (apply in order):

Case 1: Driver sending incorrect stimulus → TB Bug
Case 2: Monitor sampling incorrectly → TB Bug
Case 3: Scoreboard prediction incorrect → TB Bug
Case 4: Coverage model incorrect → TB Bug
Case 5: Assertions contradict specification → TB Bug
Case 6: RTL violates specification → RTL Bug
Case 7: RTL outputs X (uninitialized) → RTL Bug
Case 8: Protocol implemented incorrectly in RTL → RTL Bug
Case 9: Specification contradicts itself → Spec Bug

REASONING PROCESS:
1. Examine the simulation log errors — what exactly failed?
2. Cross-check expected behavior from the specification
3. Verify the RTL implementation matches the spec
4. Check if the scoreboard prediction logic is correct
5. Verify driver stimulus is correct
6. Verify monitor sampling is correct
7. Check assertions for consistency with spec
8. Examine coverage for gaps

CRITICAL RULES (grounding & anti-hallucination):
- NEVER guess — support every conclusion with evidence that is present in the input.
- VERBATIM ONLY: never invent file names, signal names, module names, line numbers,
  timestamps, or simulator messages. Cite ONLY identifiers that appear verbatim in the
  supplied RTL/TB/spec source or in the log excerpts below. If you are unsure a name
  exists, do not cite it.
- Anchor your analysis on the PRIMARY FAILURE identified below (the earliest
  causally-relevant event). Treat later events as *candidate* downstream symptoms,
  not independent causes, unless the evidence shows otherwise.
- Temporal order is not proof of causation — do not claim A caused B merely because A
  was logged first.
- Distinguish a COMPILE/ELABORATION failure from a RUNTIME failure. If the run failed to
  build, say so; do not invent a functional root cause.
- If the evidence cannot distinguish RTL vs TB, you MUST classify as "Unknown", set a
  modest confidence, fill `missing_artifacts` with the specific artifacts needed, and
  list the competing options in `alternative_hypotheses`. Declining to decide is correct
  and preferred over a confident wrong answer.
- Populate `reasoning_chain` with explicit observation→inference steps, each tagged with
  its source. Separate what the evidence DIRECTLY shows (observation) from what you INFER.
- The confidence number will be re-checked against the evidence after you answer; an
  unsupported citation lowers it. Do not inflate confidence.
"""


class RootCauseClassifierAgent(BaseAgent):
    """
    Agent 2: Root Cause Classifier.

    Classifies failures as TB Bug, RTL Bug, Spec Bug, or Unknown.
    """

    def __init__(self):
        super().__init__("root_cause_classifier")

    def execute(self, knowledge: UnifiedKnowledge) -> Classification:
        """
        Classify the root cause of simulation failure.

        Args:
            knowledge: UnifiedKnowledge from Agent 1.

        Returns:
            Classification with confidence and evidence.
        """
        self.logger.info("=" * 60)
        self.logger.info("Agent 2: Root Cause Classifier — Starting")
        self.logger.info("=" * 60)

        # Check if simulation actually failed
        if knowledge.logs.summary.pass_fail == "PASS":
            self.logger.info("Simulation PASSED — no failure to classify")
            return Classification(
                classification="Unknown",
                confidence=100,
                reason="Simulation passed — no failure detected",
            )

        # Perform deterministic pre-analysis before LLM reasoning
        pre_analysis = self._pre_analyze(knowledge)
        self.logger.info(f"Pre-analysis result: {pre_analysis.get('likely_classification', 'undetermined')}")

        # Build the reasoning prompt
        prompt = self._build_classification_prompt(knowledge, pre_analysis)

        # Use LLM for deep reasoning
        try:
            classification = self.reason(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                output_model=Classification,
            )
            # Anti-hallucination: verify the LLM's citations against the actual
            # inputs and penalize confidence for any that cannot be substantiated.
            classification = self._verify_and_calibrate(classification, knowledge)
        except Exception as e:
            self.logger.error(f"LLM reasoning failed: {e}")
            # Fall back to the evidence-based deterministic classifier.
            classification = self._deterministic_classify(knowledge, pre_analysis)

        self.logger.info("=" * 60)
        self.logger.info(f"Agent 2: Classification = {classification.classification}")
        self.logger.info(f"  Component: {classification.component}")
        self.logger.info(f"  Reason: {classification.reason}")
        self.logger.info("=" * 60)

        return classification

    def _verify_and_calibrate(
        self, classification: Classification, knowledge: UnifiedKnowledge
    ) -> Classification:
        """Verify LLM-produced citations and penalize confidence for fabrications.

        Validates that every file:line the LLM cited corresponds to a file the
        pipeline actually saw (RTL/TB/spec source or a filename printed in the
        log). Unsupported citations are recorded in the evidence and the
        confidence is capped, because a diagnosis resting on invented references
        cannot be trusted at face value.
        """
        try:
            from verisight.utils.evidence_verifier import verify_citations
            problems = verify_citations(classification, knowledge)
        except Exception as e:  # never let verification crash the pipeline
            self.logger.warning(f"Citation verification skipped: {e}")
            return classification

        if not problems:
            return classification

        self.logger.warning(
            f"Agent 2: {len(problems)} unsupported citation(s) in LLM output — "
            "capping confidence and flagging."
        )
        # Record the problem transparently and cap confidence.
        for p in problems[:5]:
            classification.evidence.append(EvidenceItem(
                source="verifier",
                reference="citation verification",
                description=f"UNSUPPORTED CITATION (not found in inputs): {p}",
            ))
        note = (
            " [Automated check: this diagnosis contained "
            f"{len(problems)} citation(s) that could not be verified against the "
            "supplied inputs; confidence reduced accordingly.]"
        )
        classification.reason = (classification.reason or "") + note
        # Each unsupported citation removes 20 points, floored at 10.
        classification.confidence = max(10, int(classification.confidence) - 20 * len(problems))
        if "unverified citations" not in [m.lower() for m in classification.missing_artifacts]:
            classification.missing_artifacts.append(
                "Verification of the flagged source citations (some did not match any input file)"
            )
        return classification

    def _pre_analyze(self, knowledge: UnifiedKnowledge) -> dict:
        """
        Perform deterministic pre-analysis before LLM reasoning.

        Checks for clear indicators that don't need LLM judgment.
        """
        analysis = {
            "likely_classification": "undetermined",
            "evidence": [],
            "x_detected": False,
            "mismatch_pattern": "",
            "reset_issues": [],
        }

        # Check for X values in mismatches (strong RTL Bug indicator)
        for mismatch in knowledge.logs.scoreboard_mismatches:
            if "xx" in mismatch.actual.lower() or "x" in mismatch.actual.lower():
                analysis["x_detected"] = True
                analysis["evidence"].append(
                    f"X value detected in actual result: {mismatch.actual} "
                    f"at {mismatch.timestamp}"
                )

        # Corroborate log-derived X mismatches against the real VCD waveform,
        # when one was supplied or produced by --simulate. This gives Agent 2
        # waveform-backed evidence without requiring the real x-tracer tool.
        analysis["vcd_evidence"] = []
        if knowledge.vcd and knowledge.vcd.tool_status == "ok":
            fields, times_ps = [], []
            for mismatch in knowledge.logs.scoreboard_mismatches:
                if not mismatch.field:
                    continue
                time_ps = timestamp_to_ps(mismatch.timestamp)
                if time_ps is None:
                    continue
                fields.append(mismatch.field)
                times_ps.append(time_ps)
            analysis["vcd_evidence"] = knowledge.vcd.evidence_near_mismatches(fields, times_ps)
            if analysis["vcd_evidence"]:
                analysis["x_detected"] = True
                analysis["evidence"].extend(analysis["vcd_evidence"])

        # Check RTL for missing resets
        for module in knowledge.rtl.modules:
            for block in module.always_blocks:
                if block.block_type == "sequential" and not block.has_reset:
                    # Sequential block without reset — potential X source
                    for sig in block.signals_written:
                        analysis["reset_issues"].append(
                            f"Signal '{sig}' in module '{module.name}' has no reset "
                            f"(always block at line {block.line_start})"
                        )
                elif block.block_type == "sequential" and block.has_reset:
                    # Block has reset, but check if ALL written signals are reset
                    import re as _re
                    reset_match = _re.search(
                        r"if\s*\(\s*!?\s*\w*(?:rst|reset)\w*\s*\)\s*begin([\s\S]*?)end",
                        block.raw_code, _re.IGNORECASE
                    )
                    if reset_match:
                        reset_body = reset_match.group(1)
                        for sig in block.signals_written:
                            if not _re.search(rf"\b{_re.escape(sig)}\b\s*<=", reset_body):
                                analysis["reset_issues"].append(
                                    f"Signal '{sig}' in module '{module.name}' is written "
                                    f"in sequential block but MISSING from reset clause "
                                    f"(always block at line {block.line_start})"
                                )

        # Check if mismatches only occur early (X propagation pattern)
        if knowledge.logs.scoreboard_mismatches:
            timestamps = []
            for m in knowledge.logs.scoreboard_mismatches:
                try:
                    ts = float(m.timestamp.replace(" ns", "").strip())
                    timestamps.append(ts)
                except (ValueError, AttributeError):
                    pass

            if timestamps:
                max_fail_time = max(timestamps)
                max_sim_time_str = knowledge.logs.summary.simulation_time
                try:
                    max_sim_time = float(max_sim_time_str.replace(" ns", "").strip())
                    if max_fail_time < max_sim_time * 0.5:
                        analysis["mismatch_pattern"] = "early_failures_only"
                        analysis["evidence"].append(
                            f"Mismatches occur only in early simulation "
                            f"(last mismatch at {max_fail_time} ns, "
                            f"simulation ends at {max_sim_time} ns)"
                        )
                except (ValueError, AttributeError):
                    pass

        # ── Additional deterministic signals (stage, primary event, protocol,
        #    assertions, artifact availability) used by the evidence-based
        #    deterministic classifier below. ──────────────────────────────────
        log = knowledge.logs
        analysis["failure_stage"] = log.summary.failure_stage
        analysis["primary_event"] = log.primary_event
        analysis["protocol_signal"] = bool(log.protocol_violations)
        analysis["assertion_signal"] = bool(log.assertion_failures)
        analysis["mismatch_no_x"] = bool(
            log.scoreboard_mismatches and not analysis["x_detected"]
        )
        analysis["has_rtl"] = bool(knowledge.rtl.modules)
        analysis["has_tb"] = bool(
            knowledge.tb.drivers or knowledge.tb.monitors or knowledge.tb.scoreboards
        )
        analysis["has_spec"] = bool(knowledge.spec.functional_requirements)

        # Files named by compile/elaboration errors (for RTL-vs-TB attribution).
        import re as _re2
        tool_files = []
        for te in log.tool_errors:
            tool_files += _re2.findall(r"([\w./\\-]+\.(?:sv|svh|v|vh))", te.text)
        analysis["tool_error_files"] = tool_files

        # Determine likely classification
        if analysis["x_detected"] and analysis["reset_issues"]:
            analysis["likely_classification"] = "RTL Bug"
            analysis["likely_category"] = "X Propagation"
        elif analysis["x_detected"]:
            analysis["likely_classification"] = "RTL Bug"
            analysis["likely_category"] = "X Propagation"
        elif analysis["reset_issues"]:
            analysis["likely_classification"] = "RTL Bug"
            analysis["likely_category"] = "Missing Reset"

        return analysis

    def _select_error_lines(self, log, budget: int = 20):
        """Evidence-prioritized error selection for the prompt.

        Returns (text, n_shown, n_total). Keeps the primary event's log line,
        the first few errors, and any error whose message carries an X/Z value
        or an assertion/protocol signature, up to `budget`. This avoids the old
        `errors[:10]` truncation that could hide the real root cause while still
        bounding prompt size. The total count is always reported honestly.
        """
        errors = list(log.errors)
        n_total = len(errors)
        if n_total == 0:
            return "", 0, 0

        scored = []
        primary_line = log.primary_event.log_line if log.primary_event else -1
        for idx, e in enumerate(errors):
            msg = (e.message or "").lower()
            priority = 0
            if e.line_number_in_log == primary_line:
                priority = 100  # the causal anchor always shown
            elif idx < 5:
                priority = 50 - idx  # early errors
            if re.search(r"\b[0-9a-f]*[xz][0-9a-f]*\b", msg) and ("=" in msg):
                priority += 20  # X/Z value present
            if any(k in msg for k in ("assert", "protocol", "pslverr", "fatal")):
                priority += 15
            scored.append((priority, idx, e))

        scored.sort(key=lambda t: (-t[0], t[1]))
        chosen = sorted(scored[:budget], key=lambda t: t[1])  # restore log order
        lines = "".join(
            f"- [{e.severity}] @{e.timestamp or 'n/a'} "
            f"{(e.file + ':' + str(e.line) + ' ') if e.file else ''}: {e.message}\n"
            for _, _, e in chosen
        )
        return lines, len(chosen), n_total

    def _build_classification_prompt(
        self, knowledge: UnifiedKnowledge, pre_analysis: dict
    ) -> str:
        """Build the LLM reasoning prompt with all evidence."""

        # Summarize errors — evidence-prioritized selection instead of a blind
        # first-10 truncation that can drop the real root cause. We always keep
        # the primary event, the first few errors, and any error carrying an X
        # or an assertion/protocol signature, then note how many were omitted.
        error_summary, n_shown, n_total = self._select_error_lines(knowledge.logs)

        # Primary failure + stage give the model an explicit root-cause anchor.
        primary = knowledge.logs.primary_event
        stage = knowledge.logs.summary.failure_stage
        if primary is not None:
            primary_block = (
                f"Kind: {primary.kind} | Stage: {primary.stage} | "
                f"Time: {primary.timestamp or 'n/a'} | "
                f"Source: {(primary.file + ':' + str(primary.line)) if primary.file else 'n/a'}\n"
                f"Message: {primary.message[:240]}\n"
                f"Why primary: {primary.rationale}"
            )
            if knowledge.logs.cascade_events:
                primary_block += (
                    f"\nCandidate downstream symptoms (not proven causal): "
                    f"{len(knowledge.logs.cascade_events)}"
                )
        else:
            primary_block = "No primary failure event identified."

        # Summarize mismatches
        mismatch_summary = ""
        for m in knowledge.logs.scoreboard_mismatches[:10]:
            mismatch_summary += (
                f"- @{m.timestamp}: expected={m.expected} actual={m.actual}\n"
            )

        # Summarize spec requirements
        spec_summary = ""
        for req in knowledge.spec.functional_requirements[:15]:
            spec_summary += f"- [{req.id}] {req.description}\n"

        # Reset behavior
        reset_summary = ""
        for rb in knowledge.spec.reset_behavior:
            reset_summary += (
                f"- {rb.reset_signal} ({rb.active_level}, {rb.type}): "
                f"resets {', '.join(rb.affected_signals[:5])}\n"
            )

        # RTL always blocks summary
        rtl_summary = ""
        for module in knowledge.rtl.modules:
            rtl_summary += f"\nModule: {module.name} (file: {module.file})\n"
            for block in module.always_blocks:
                reset_info = "HAS RESET" if block.has_reset else "NO RESET"
                rtl_summary += (
                    f"  - {block.block_type} block @ line {block.line_start}: "
                    f"writes {block.signals_written}, {reset_info}\n"
                )
                for issue in block.issues:
                    rtl_summary += f"    ⚠ {issue}\n"

        # Scoreboard logic
        sb_summary = ""
        for sb in knowledge.tb.scoreboards:
            sb_summary += f"\nScoreboard: {sb.name} (file: {sb.file})\n"
            sb_summary += f"  Prediction logic:\n{sb.prediction_logic[:500]}\n"

        # VCD waveform evidence (independent of real x-tracer availability)
        vcd_summary = ""
        if knowledge.vcd and knowledge.vcd.tool_status == "ok":
            vcd_evidence = pre_analysis.get("vcd_evidence", [])
            vcd_summary = (
                f"Parsed {len(knowledge.vcd.signals)} signals via "
                f"{knowledge.vcd.parser_backend} from {knowledge.vcd.source_file}.\n"
                + ("\n".join(f"- {e}" for e in vcd_evidence) if vcd_evidence
                   else "No X/Z values found near reported mismatch times.")
            )
        elif knowledge.vcd:
            vcd_summary = f"VCD waveform unavailable: {knowledge.vcd.tool_message}"

        # Pre-analysis findings
        pre_findings = "\n".join(pre_analysis.get("evidence", [])) or "No deterministic findings"

        # RAG context — explicitly framed as *similar prior cases*, NOT proof.
        # A similar past case does not establish that THIS failure has the same
        # cause; the model must verify independently against the evidence above.
        rag_summary = ""
        if knowledge.rag_context and knowledge.rag_context.similar_failures:
            rag_summary = (
                "SIMILAR PRIOR CASES (reference only — NOT proof of this cause; "
                "verify independently before relying on them):\n"
            )
            for f in knowledge.rag_context.similar_failures[:3]:
                sim = f.get("similarity")
                sim_str = f" (similarity={sim:.2f})" if isinstance(sim, (int, float)) else ""
                rag_summary += f"- {f.get('document', '')[:200]}{sim_str}\n"

        prompt = f"""Analyze this simulation failure and classify the root cause.

SIMULATION STATUS: {knowledge.logs.summary.pass_fail}
SIMULATION TIME: {knowledge.logs.summary.simulation_time}
FAILURE STAGE: {stage}  (compile/elaboration → build failed before runtime)

═══ PRIMARY FAILURE (root-cause anchor — reason from THIS first) ═══
{primary_block}

═══ ERRORS (showing {n_shown} of {n_total}; prioritized, not just the first {n_shown}) ═══
{error_summary or "No errors"}

═══ SCOREBOARD MISMATCHES ({len(knowledge.logs.scoreboard_mismatches)} total) ═══
{mismatch_summary or "No mismatches"}

═══ SPECIFICATION REQUIREMENTS ═══
{spec_summary or "No specification provided"}

═══ RESET BEHAVIOR (from spec) ═══
{reset_summary or "No reset spec"}

═══ RTL ANALYSIS ═══
{rtl_summary or "No RTL provided"}

═══ SCOREBOARD LOGIC ═══
{sb_summary or "No scoreboard found"}

═══ VCD WAVEFORM EVIDENCE ═══
{vcd_summary or "No VCD waveform provided"}

═══ DETERMINISTIC PRE-ANALYSIS ═══
{pre_findings}
Likely classification: {pre_analysis.get('likely_classification', 'undetermined')}
Reset issues: {pre_analysis.get('reset_issues', [])}

{rag_summary}

Based on the evidence above, classify the root cause and provide your reasoning.
Apply the 9 decision rules systematically. Include evidence chain and confidence score.
"""
        return self.build_prompt(prompt, {}, Classification)

    # ── Evidence-based confidence calibration ───────────────────────────────
    # Confidence is derived from which GROUNDED evidence factors are present for
    # a diagnosis, NOT chosen by the model. Each factor contributes a fixed
    # weight; the total is clamped to 0.95 (we never claim certainty). This is
    # the methodology referenced in the deliverables and is evaluated for
    # correlation with correctness on the eval set.
    _CONF_FACTORS = {
        "compile_or_elab_proven": 0.80,   # a build error is a hard, checkable fact
        "file_cited": 0.10,               # diagnosis names a real source location
        "x_values_observed": 0.45,        # X/Z seen in log or VCD
        "static_missing_reset_matches_x": 0.40,  # RTL reset gap explains the X
        "protocol_violation_logged": 0.35,
        "sva_assertion_failed": 0.30,
        "spec_requirement_corroborates": 0.15,
    }
    _ABSTAIN_CONFIDENCE = 40  # "moderately sure we CANNOT decide" (an Unknown verdict)

    def _calibrate_confidence(self, factors: list) -> int:
        """Return an evidence-derived confidence (0-100) for a positive label."""
        score = sum(self._CONF_FACTORS.get(f, 0.0) for f in factors)
        return int(round(min(0.95, score) * 100))

    def _deterministic_classify(
        self, knowledge: UnifiedKnowledge, pre_analysis: dict
    ) -> Classification:
        """
        Evidence-based deterministic classifier.

        Used both as the fallback when the LLM is unavailable AND as a strong,
        grounded prior. Every field it emits is backed by parsed facts (real
        file/line/timestamps), so it never fabricates. When the evidence is
        insufficient to distinguish RTL vs TB it returns 'Unknown' with the
        specific missing artifacts and the plausible alternatives, rather than
        guessing — this is the trustworthiness contract.
        """
        from pathlib import Path as _Path

        log = knowledge.logs
        primary = pre_analysis.get("primary_event")
        stage = pre_analysis.get("failure_stage", "none")

        evidence: list = []
        chain: list = []

        # Grounded primary-event evidence + a log_reference that names the
        # earliest causally-relevant failure (and its source file when known).
        if primary is not None:
            ref = f"log line {primary.log_line}"
            if primary.file:
                ref = f"{primary.file}:{primary.line} ({ref})" if primary.line else f"{primary.file} ({ref})"
            if primary.timestamp:
                ref += f", t={primary.timestamp}"
            evidence.append(EvidenceItem(
                source="log", reference=ref,
                description=primary.rationale, snippet=primary.message[:200],
            ))
            file_part = f"{primary.file}:{primary.line} " if primary.file else ""
            log_ref = f"{file_part}{primary.message[:180]}".strip()
        elif log.errors:
            log_ref = log.errors[0].message[:180]
        else:
            log_ref = ""

        def finalize(cls, comp, reason, category, confidence,
                     rtl_ref="", tb_ref="", spec_ref="", fix="",
                     missing=None, alts=None, extra_ev=None):
            return Classification(
                classification=cls, confidence=confidence, component=comp,
                reason=reason, category=category, log_reference=log_ref,
                rtl_reference=rtl_ref, tb_reference=tb_ref, spec_reference=spec_ref,
                recommended_fix=fix, evidence=evidence + (extra_ev or []),
                reasoning_chain=chain, missing_artifacts=missing or [],
                alternative_hypotheses=alts or [],
            )

        # ── 1) Compile / elaboration failure ────────────────────────────────
        if stage in ("compile", "elaboration"):
            rtl_base = {_Path(f).name.lower() for f in knowledge.rtl.file_list}
            tb_base = {_Path(f).name.lower() for f in knowledge.tb.file_list}
            files = pre_analysis.get("tool_error_files", [])
            cls, comp, rtl_ref, tb_ref = "Unknown", "", "", ""
            for f in files:
                b = _Path(f).name.lower()
                if b in rtl_base or "/rtl/" in f.lower().replace("\\", "/"):
                    cls, rtl_ref, comp = "RTL Bug", f, _Path(f).stem
                    break
                if b in tb_base or "/tb/" in f.lower().replace("\\", "/") or any(
                    k in b for k in ("_tb", "test", "driver", "monitor", "scoreboard", "seq", "env", "agent")
                ):
                    cls, tb_ref, comp = "TB Bug", f, _Path(f).stem
                    break
            if cls == "Unknown" and files:
                # A bare compile error in an unclassified .sv/.v is, by default,
                # most often in the design/source under test.
                cls, rtl_ref, comp = "RTL Bug", files[0], _Path(files[0]).stem
            for te in log.tool_errors[:4]:
                evidence.append(EvidenceItem(
                    source="log", reference=f"log line {te.line_no}",
                    description=f"{te.tool} {te.stage} error", snippet=te.text[:160],
                ))
            first_te = log.tool_errors[0].text[:160] if log.tool_errors else ""
            chain.append(ClassificationReasoning(
                step=1,
                observation=f"{stage.capitalize()} error(s) present; zero simulation output",
                inference="The build failed; this precedes and causes any runtime symptom",
                source="log",
            ))
            reason = (
                f"The run failed at {stage} time, before simulation started "
                f"({len(log.tool_errors)} {stage} error(s)). First error: {first_te}. "
                "No functional (RTL/TB) root-cause diagnosis is possible until the build succeeds."
            )
            conf = self._calibrate_confidence(
                ["compile_or_elab_proven"] + (["file_cited"] if (rtl_ref or tb_ref) else [])
            )
            return finalize(
                cls, comp, reason,
                "Compilation Error" if stage == "compile" else "Elaboration Error",
                conf, rtl_ref=rtl_ref, tb_ref=tb_ref,
                fix=f"Resolve the {stage} error in {comp or 'the cited source file'} and re-run.",
            )

        # ── 2) X propagation with an identified reset cause ─────────────────
        if pre_analysis["x_detected"] and pre_analysis["reset_issues"]:
            for e in pre_analysis["evidence"]:
                evidence.append(EvidenceItem(source="log", reference="deterministic pre-analysis", description=e))
            for ri in pre_analysis["reset_issues"]:
                evidence.append(EvidenceItem(source="rtl", reference="RTL reset static analysis", description=ri))
            comp = knowledge.rtl.modules[0].name if knowledge.rtl.modules else "unknown"
            rtl_ref = knowledge.rtl.modules[0].file if knowledge.rtl.modules else ""
            chain += [
                ClassificationReasoning(step=1, observation="Scoreboard/VCD shows X (unknown) values in DUT output",
                                        inference="An uninitialised register is driving X", source="log/VCD"),
                ClassificationReasoning(step=2, observation="RTL sequential block writes a signal that is absent from its reset clause",
                                        inference="That register is never initialised, producing X from time 0", source="RTL static analysis"),
            ]
            conf = self._calibrate_confidence(
                ["x_values_observed", "static_missing_reset_matches_x"] + (["file_cited"] if rtl_ref else [])
            )
            return finalize(
                "RTL Bug", comp,
                "X values observed in DUT output, and RTL static analysis found a sequential "
                "register written without a reset assignment — an uninitialised register "
                "propagates X from time 0.",
                "X Propagation", conf, rtl_ref=rtl_ref,
                fix="Add a reset assignment for the identified register(s) in the reset clause.",
            )

        # ── 2b) X observed but no reset gap pinned ──────────────────────────
        if pre_analysis["x_detected"]:
            comp = knowledge.rtl.modules[0].name if knowledge.rtl.modules else ""
            rtl_ref = knowledge.rtl.modules[0].file if knowledge.rtl.modules else ""
            conf = self._calibrate_confidence(["x_values_observed"] + (["file_cited"] if rtl_ref else []))
            return finalize(
                "RTL Bug", comp,
                "X (unknown) values observed in DUT output. The precise uninitialised source "
                "was not isolated by static analysis; an X almost always originates in RTL.",
                "X Propagation", conf, rtl_ref=rtl_ref,
                missing=["Waveform (VCD) X-origin trace to pin the exact uninitialised signal"],
                alts=[{"classification": "TB Bug", "reason": "A driver could drive X stimulus, though this is less common", "confidence": 15}],
            )

        # ── 3) Protocol violation / SVA assertion failure ───────────────────
        if pre_analysis.get("protocol_signal") or pre_analysis.get("assertion_signal"):
            factors = ["file_cited"]
            assert_file = ""
            for a in log.assertion_failures[:3]:
                if a.file:
                    assert_file = a.file
                evidence.append(EvidenceItem(
                    source="log", reference=(f"{a.file}:{a.line}" if a.file else "assertion"),
                    description=f"SVA assertion failed: {a.assertion_name}".strip(), snippet=(a.message or "")[:160],
                ))
            for pv in log.protocol_violations[:3]:
                evidence.append(EvidenceItem(source="log", reference="protocol check", description=pv.message[:160]))
            if pre_analysis.get("assertion_signal"):
                factors.append("sva_assertion_failed")
            if pre_analysis.get("protocol_signal"):
                factors.append("protocol_violation_logged")
            if pre_analysis.get("has_spec"):
                factors.append("spec_requirement_corroborates")
            comp = knowledge.rtl.modules[0].name if knowledge.rtl.modules else ""
            rtl_ref = knowledge.rtl.modules[0].file if knowledge.rtl.modules else assert_file
            chain.append(ClassificationReasoning(
                step=1, observation="A protocol check / SVA assertion bound to the DUT failed",
                inference="The RTL violated a required protocol/behavioural rule", source="log",
            ))
            return finalize(
                "RTL Bug", comp,
                "A design-bound SVA assertion / protocol check failed, indicating the RTL "
                "violated a required protocol or behavioural rule. The earliest such failure "
                f"is: {log_ref}.",
                "Protocol Violation", self._calibrate_confidence(factors),
                rtl_ref=rtl_ref, spec_ref=("specification protocol requirements" if pre_analysis.get("has_spec") else ""),
                fix="Correct the RTL so the flagged protocol/behavioural requirement holds.",
                alts=[{"classification": "TB Bug", "reason": "The assertion itself could be wrong if it contradicts the spec", "confidence": 15}],
            )

        # ── 4) Value mismatch with no deterministic RTL-vs-TB discriminator ──
        if log.scoreboard_mismatches or log.errors:
            missing = []
            if not pre_analysis.get("has_rtl"):
                missing.append("RTL source (to check whether the DUT computes the wrong value)")
            if not pre_analysis.get("has_tb"):
                missing.append("UVM scoreboard/driver/monitor source (to check the reference model/stimulus)")
            if not pre_analysis.get("has_spec"):
                missing.append("design specification (to establish the expected behaviour)")
            alts = [
                {"classification": "RTL Bug", "reason": "The DUT may compute/return an incorrect value at the cited time", "confidence": 40},
                {"classification": "TB Bug", "reason": "The scoreboard prediction, reference model, or stimulus timing may be wrong", "confidence": 40},
            ]
            if missing:
                reason = (
                    f"A value mismatch was observed (earliest: {log_ref}), but the artifacts "
                    "needed to attribute it are missing, so RTL cannot be distinguished from TB. "
                    "Declining to guess."
                )
                return finalize("Unknown", "", reason, "Data Mismatch",
                                self._ABSTAIN_CONFIDENCE, missing=missing, alts=alts,
                                rtl_ref=(knowledge.rtl.modules[0].file if knowledge.rtl.modules else ""))
            # All artifacts present, but a deterministic static check cannot
            # decide. This is where the LLM reasoning path adds value.
            comp = knowledge.rtl.modules[0].name if knowledge.rtl.modules else ""
            reason = (
                f"Earliest failure: {log_ref}. A deterministic static check did not isolate a "
                "definitive RTL or TB defect. Distinguishing a wrong DUT value from a wrong "
                "reference-model prediction requires behavioural comparison (LLM reasoning or a "
                "targeted re-simulation), which was unavailable in this run."
            )
            return finalize("Unknown", comp, reason, "Data Mismatch",
                            self._ABSTAIN_CONFIDENCE,
                            rtl_ref=(knowledge.rtl.modules[0].file if knowledge.rtl.modules else ""),
                            missing=["Behavioural RTL-vs-reference-model comparison (LLM or targeted re-simulation)"],
                            alts=alts)

        # ── 5) Nothing actionable ───────────────────────────────────────────
        return finalize(
            "Unknown", "", "Insufficient evidence for a deterministic classification.",
            "", self._ABSTAIN_CONFIDENCE,
            missing=["A simulation log with recognisable errors, plus RTL/TB/spec source"],
        )

    # Backwards-compatible alias (older callers / tests).
    def _fallback_classification(
        self, knowledge: UnifiedKnowledge, pre_analysis: dict
    ) -> Classification:
        return self._deterministic_classify(knowledge, pre_analysis)
