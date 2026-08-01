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
from typing import Optional

from verisight.agents.base_agent import BaseAgent
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.classification import Classification, EvidenceItem, ClassificationReasoning
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

CRITICAL RULES:
- NEVER guess — support every conclusion with evidence
- Provide a confidence score (0-100) with rationale
- Include specific file references, line numbers, and timestamps
- If evidence is insufficient, classify as "Unknown" and list missing artifacts
- Always consider alternative hypotheses
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
        except Exception as e:
            self.logger.error(f"LLM reasoning failed: {e}")
            # Fall back to deterministic analysis
            classification = self._fallback_classification(knowledge, pre_analysis)

        self.logger.info("=" * 60)
        self.logger.info(f"Agent 2: Classification = {classification.classification}")
        self.logger.info(f"  Confidence: {classification.confidence}%")
        self.logger.info(f"  Component: {classification.component}")
        self.logger.info(f"  Reason: {classification.reason}")
        self.logger.info("=" * 60)

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

    def _build_classification_prompt(
        self, knowledge: UnifiedKnowledge, pre_analysis: dict
    ) -> str:
        """Build the LLM reasoning prompt with all evidence."""

        # Summarize errors
        error_summary = ""
        for e in knowledge.logs.errors[:10]:
            error_summary += f"- [{e.severity}] @{e.timestamp}: {e.message}\n"

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

        # Pre-analysis findings
        pre_findings = "\n".join(pre_analysis.get("evidence", [])) or "No deterministic findings"

        # RAG context
        rag_summary = ""
        if knowledge.rag_context and knowledge.rag_context.similar_failures:
            rag_summary = "SIMILAR PAST FAILURES:\n"
            for f in knowledge.rag_context.similar_failures[:3]:
                rag_summary += f"- {f.get('document', '')[:200]}\n"

        prompt = f"""Analyze this simulation failure and classify the root cause.

SIMULATION STATUS: {knowledge.logs.summary.pass_fail}
SIMULATION TIME: {knowledge.logs.summary.simulation_time}

═══ ERRORS ({len(knowledge.logs.errors)} total) ═══
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

═══ DETERMINISTIC PRE-ANALYSIS ═══
{pre_findings}
Likely classification: {pre_analysis.get('likely_classification', 'undetermined')}
Reset issues: {pre_analysis.get('reset_issues', [])}

{rag_summary}

Based on the evidence above, classify the root cause and provide your reasoning.
Apply the 9 decision rules systematically. Include evidence chain and confidence score.
"""
        return self.build_prompt(prompt, {}, Classification)

    def _fallback_classification(
        self, knowledge: UnifiedKnowledge, pre_analysis: dict
    ) -> Classification:
        """
        Deterministic fallback classification when LLM is unavailable.
        """
        # Use pre-analysis results
        if pre_analysis["x_detected"] and pre_analysis["reset_issues"]:
            evidence = []
            for e in pre_analysis["evidence"]:
                evidence.append(EvidenceItem(
                    source="rtl",
                    reference="static analysis",
                    description=e,
                ))
            for ri in pre_analysis["reset_issues"]:
                evidence.append(EvidenceItem(
                    source="rtl",
                    reference="reset analysis",
                    description=ri,
                ))

            return Classification(
                classification="RTL Bug",
                confidence=85,
                component=knowledge.rtl.modules[0].name if knowledge.rtl.modules else "unknown",
                reason=(
                    "X values detected in simulation output. "
                    "RTL analysis reveals sequential registers without reset logic. "
                    "Uninitialized registers propagate X values to outputs."
                ),
                category="X Propagation",
                spec_reference="Reset Behavior section",
                log_reference=f"First error at {knowledge.logs.errors[0].timestamp}" if knowledge.logs.errors else "",
                recommended_fix="Add reset logic for all sequential registers",
                evidence=evidence,
                reasoning_chain=[
                    ClassificationReasoning(
                        step=1,
                        observation="Scoreboard reports mismatch with 'xx' values",
                        inference="Output contains X (unknown) values",
                        source="simulation log",
                    ),
                    ClassificationReasoning(
                        step=2,
                        observation="RTL sequential block has no reset for output registers",
                        inference="Registers are never initialized, causing X from time 0",
                        source="RTL static analysis",
                    ),
                    ClassificationReasoning(
                        step=3,
                        observation="Spec requires all outputs reset to 0",
                        inference="RTL violates specification reset requirements",
                        source="design specification",
                    ),
                ],
            )

        # Generic fallback
        return Classification(
            classification="Unknown",
            confidence=30,
            reason="Insufficient evidence for deterministic classification. LLM reasoning unavailable.",
            missing_artifacts=["LLM API access for deep reasoning"],
        )
