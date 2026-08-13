"""
Agent 3 — RTL Root Cause Analyzer.

Performs exhaustive RTL diagnosis across 7 sub-modules:
1. X-Tracer — Track X origin and propagation
2. Functional Analyzer — Compare spec vs RTL
3. CDC Analyzer — Clock domain crossing issues
4. Lint Analyzer — Coding style and common errors
5. Structural Analyzer — FSM, loops, dead states
6. Protocol Compliance — APB/AHB/AXI/Wishbone
7. Misc Analyzer — Timing, reset sequencing, races
"""

import re
from pathlib import Path
from typing import Optional, List

from verisight.agents.base_agent import BaseAgent
from verisight.config import get_config
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.classification import Classification
from verisight.schemas.rtl_analysis import (
    RTLAnalysis, XTraceResult, XPropagationPath, XTracerTraceResult,
    FunctionalResult, FunctionalIssue,
    CDCResult, CDCIssue,
    LintResult, LintIssue,
    StructuralResult, StructuralIssue,
    ProtocolResult, ProtocolIssue,
    MiscResult, MiscIssue,
)
from verisight.tools import yosys_runner, xtracer_runner
from verisight.tools.xtracer_runner import XTracerNotFoundError
from verisight.utils.logger import get_logger

logger = get_logger("agent3_rtl_analyzer")

SYSTEM_PROMPT = """You are a Principal ASIC Design and Verification Engineer specializing in
RTL debugging, static analysis, and root cause analysis.

You are performing exhaustive RTL diagnosis to identify the exact root cause
of a simulation failure that has been classified as an RTL Bug.

Your analysis covers 7 areas:
1. X Propagation — uninitialized registers, multi-driven signals, tri-state
2. Functional — spec vs RTL discrepancies
3. CDC — clock domain crossing issues
4. Lint — coding style violations
5. Structural — FSM issues, dead states, unreachable logic
6. Protocol — bus protocol compliance
7. Miscellaneous — timing, reset sequencing, races

CRITICAL RULES:
- Every finding must cite specific modules, signals, files, and line numbers
- Rate severity as: critical/high/medium/low
- Provide actionable fix recommendations
- Distinguish confirmed bugs from potential issues
"""


class RTLRootCauseAnalyzer(BaseAgent):
    """
    Agent 3: RTL Root Cause Analyzer with 7 sub-modules.
    """

    def __init__(self, output_dir: str = "output"):
        super().__init__("rtl_root_cause_analyzer")
        self.output_dir = Path(output_dir)

    def execute(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
    ) -> RTLAnalysis:
        """
        Perform exhaustive RTL root cause analysis.

        Args:
            knowledge: UnifiedKnowledge from Agent 1.
            classification: Classification from Agent 2.

        Returns:
            RTLAnalysis with results from all 7 sub-modules.
        """
        self.logger.info("=" * 60)
        self.logger.info("Agent 3: RTL Root Cause Analyzer — Starting")
        self.logger.info("=" * 60)

        analysis = RTLAnalysis()

        # Module 1: X-Tracer
        self.logger.info("Module 1: X-Tracer Analysis")
        analysis.xtrace = self._analyze_x_propagation(knowledge)
        analysis.xtrace = self._augment_with_real_xtracer(analysis.xtrace, knowledge)
        analysis.xtrace = self._augment_with_vcd_evidence(analysis.xtrace, knowledge)

        # Module 2: Functional Analyzer
        self.logger.info("Module 2: Functional Analysis")
        analysis.functional = self._analyze_functional(knowledge)

        # Module 3: CDC Analyzer
        self.logger.info("Module 3: CDC Analysis")
        analysis.cdc = self._analyze_cdc(knowledge)

        # Module 4: Lint Analyzer
        self.logger.info("Module 4: Lint Analysis")
        analysis.lint = self._analyze_lint(knowledge)

        # Module 5: Structural Analyzer
        self.logger.info("Module 5: Structural Analysis")
        analysis.structural = self._analyze_structural(knowledge)

        # Module 6: Protocol Compliance
        self.logger.info("Module 6: Protocol Compliance")
        analysis.protocol = self._analyze_protocol(knowledge)

        # Module 7: Misc Analyzer
        self.logger.info("Module 7: Miscellaneous Analysis")
        analysis.misc = self._analyze_misc(knowledge)

        # Determine primary root cause
        analysis = self._determine_primary_root_cause(analysis, classification)

        self.logger.info("=" * 60)
        self.logger.info(f"Agent 3: Primary Root Cause = {analysis.primary_root_cause}")
        self.logger.info(f"  Category: {analysis.primary_category}")
        self.logger.info(f"  Confidence: {analysis.confidence}%")
        self.logger.info("=" * 60)

        return analysis

    # ─── Module 1: X-Tracer ────────────────────────────────────────

    def _analyze_x_propagation(self, knowledge: UnifiedKnowledge) -> XTraceResult:
        """Analyze X value origins and propagation paths."""
        result = XTraceResult()

        for module in knowledge.rtl.modules:
            # Find registers without reset (X origins)
            for block in module.always_blocks:
                if block.block_type == "sequential":
                    if block.has_reset:
                        # Check which signals have reset vs which are written
                        reset_code = block.raw_code
                        for sig in block.signals_written:
                            # Check if this signal appears in the reset clause
                            if not self._signal_has_reset(sig, reset_code):
                                result.uninitialized_registers.append(
                                    f"{module.name}.{sig}"
                                )
                                result.x_origins.append(XPropagationPath(
                                    origin_signal=sig,
                                    origin_module=module.name,
                                    origin_cause="uninitialized",
                                    propagation_chain=[sig],
                                    affected_outputs=self._find_affected_outputs(
                                        sig, module
                                    ),
                                    line_number=block.line_start,
                                    file=module.file,
                                ))
                    else:
                        # Entire block has no reset
                        for sig in block.signals_written:
                            result.uninitialized_registers.append(
                                f"{module.name}.{sig}"
                            )
                            result.x_origins.append(XPropagationPath(
                                origin_signal=sig,
                                origin_module=module.name,
                                origin_cause="uninitialized",
                                propagation_chain=[sig],
                                affected_outputs=self._find_affected_outputs(
                                    sig, module
                                ),
                                line_number=block.line_start,
                                file=module.file,
                            ))

        # Set severity based on findings
        if result.x_origins:
            result.severity = "critical" if len(result.x_origins) > 2 else "high"
            result.summary = (
                f"Found {len(result.x_origins)} X propagation source(s): "
                f"{', '.join(r.origin_signal for r in result.x_origins[:5])}. "
                f"Uninitialized registers: {', '.join(result.uninitialized_registers[:5])}"
            )
        else:
            result.severity = "none"
            result.summary = "No X propagation issues detected"

        self.logger.info(f"  → X-Trace: {result.severity} — {len(result.x_origins)} origins")
        return result

    def _signal_has_reset(self, signal: str, reset_code: str) -> bool:
        """Check if a signal is assigned in the reset clause of an always block."""
        # Look for the reset if/else pattern
        reset_match = re.search(
            r"if\s*\(\s*!?\s*\w*(?:rst|reset)\w*\s*\)\s*begin([\s\S]*?)end",
            reset_code, re.IGNORECASE
        )
        if reset_match:
            reset_body = reset_match.group(1)
            # Check if signal is assigned in reset body
            if re.search(rf"\b{re.escape(signal)}\b\s*<=", reset_body):
                return True
        return False

    def _find_affected_outputs(self, signal: str, module) -> List[str]:
        """Find output ports affected by a signal."""
        affected = []
        for port in module.ports:
            if port.direction == "output" and port.name == signal:
                affected.append(port.name)
        # Also check continuous assignments
        for assign in module.assignments:
            if signal in assign:
                lhs = assign.split("=")[0].strip()
                for port in module.ports:
                    if port.direction == "output" and port.name == lhs:
                        affected.append(port.name)
        return affected

    def _augment_with_real_xtracer(
        self, result: XTraceResult, knowledge: UnifiedKnowledge
    ) -> XTraceResult:
        """
        Run real x-tracer analysis (netlist + VCD backed) on top of the
        static heuristic above, when the user has opted in via config.

        Every external-tool step is wrapped so a missing/failing tool
        degrades to a clear tool_status/tool_message instead of crashing
        the pipeline — the heuristic result above always still stands.
        """
        config = get_config().xtracer

        if not config.enabled:
            result.tool_status = "disabled"
            return result

        top_module = config.top_module or knowledge.rtl.top_module

        # Step 1: resolve netlist (user-supplied, or synthesize with yosys).
        if config.netlist_paths:
            netlists = [Path(p) for p in config.netlist_paths]
        else:
            try:
                netlist_path = yosys_runner.synthesize_netlist(
                    knowledge.rtl.file_list,
                    top_module,
                    self.output_dir / "xtracer" / "netlist.v",
                )
                netlists = [netlist_path]
            except RuntimeError as e:
                self.logger.warning(f"x-tracer: yosys synthesis failed — {e}")
                result.tool_status = "error"
                result.tool_message = f"yosys synthesis failed: {e}"
                return result

        # Step 2: require a VCD waveform.
        if not config.vcd_path:
            result.tool_status = "skipped_no_vcd"
            result.tool_message = (
                "Real x-tracer analysis requires a VCD waveform. Pass --vcd "
                "to enable it; falling back to static heuristic X analysis."
            )
            return result
        vcd_path = Path(config.vcd_path)

        # Step 3: locate x-tracer itself.
        try:
            xtracer_path = xtracer_runner.find_xtracer(config.xtracer_path)
        except XTracerNotFoundError as e:
            self.logger.warning(f"x-tracer: not found — {e}")
            result.tool_status = "skipped_not_installed"
            result.tool_message = str(e)
            return result

        # Step 4: build queries (explicit override, or auto-derived from
        # sim-log scoreboard mismatches).
        if config.signal and config.time_ps is not None:
            queries = [xtracer_runner.XTraceQuery(
                field_name=config.signal,
                signal_candidates=[config.signal],
                time_ps=config.time_ps,
            )]
        else:
            queries = xtracer_runner.derive_queries(knowledge, top_module)

        if not queries:
            result.tool_status = "skipped_no_query"
            result.tool_message = (
                "Could not derive an X-valued signal/time to trace from the "
                "sim log. Pass --xtrace-signal and --xtrace-time explicitly."
            )
            return result

        # Step 5: run x-tracer per query, tolerating individual failures.
        for query in queries:
            try:
                trace_json = xtracer_runner.run_xtracer_with_candidates(
                    xtracer_path, netlists, vcd_path,
                    query.signal_candidates, query.time_ps, config.max_depth,
                )
                result.real_traces.append(XTracerTraceResult(
                    query_signal=trace_json.get("signal", query.signal_candidates[0]),
                    query_time_ps=query.time_ps,
                    root_cause_type=trace_json.get("root_cause_type", ""),
                    summary=trace_json.get("summary", ""),
                    cause_tree=trace_json,
                ))
            except RuntimeError as e:
                self.logger.warning(
                    f"x-tracer: query for '{query.field_name}' failed on all "
                    f"candidate paths — {e}"
                )

        # Step 6: real evidence outranks the heuristic guess.
        if result.real_traces:
            result.tool_status = "ok"
            lead = result.real_traces[0]
            result.summary = (
                f"x-tracer confirmed: {lead.query_signal} is {lead.root_cause_type or 'X'} "
                f"at {lead.query_time_ps}ps. {lead.summary}"
            ).strip()
            if result.severity == "none":
                result.severity = "high"
        else:
            result.tool_status = "error"
            result.tool_message = (
                "x-tracer ran but no query resolved against the given netlist/VCD; "
                "see logs for per-signal errors."
            )

        return result

    def _augment_with_vcd_evidence(
        self, result: XTraceResult, knowledge: UnifiedKnowledge
    ) -> XTraceResult:
        """
        Add lightweight VCD-derived evidence for the same derived queries
        real x-tracer would use, but sourced from Agent 1's post-processed
        knowledge.vcd — so this evidence is available even when the real
        x-tracer binary isn't installed or --xtrace wasn't passed at all,
        as long as a VCD (user-supplied or --simulate-generated) exists.
        """
        if not knowledge.vcd or knowledge.vcd.tool_status != "ok":
            return result

        top_module = get_config().xtracer.top_module or knowledge.rtl.top_module
        queries = xtracer_runner.derive_queries(knowledge, top_module)

        for query in queries:
            for candidate in query.signal_candidates:
                for path in knowledge.vcd.find_matching_signals(candidate):
                    value = knowledge.vcd.signals[path].value_at(query.time_ps)
                    if value and ("x" in value.lower() or "z" in value.lower()):
                        result.vcd_evidence.append(
                            f"VCD: signal '{path}' = {value} at {query.time_ps}ps "
                            f"(derived from mismatch on field '{query.field_name}')"
                        )

        if result.vcd_evidence and result.severity == "none":
            result.severity = "medium"
            prefix = f"{result.summary} " if result.summary else ""
            result.summary = (
                f"{prefix}VCD waveform independently confirms X/Z on "
                f"{len(result.vcd_evidence)} signal(s)."
            )

        return result

    # ─── Module 2: Functional Analyzer ─────────────────────────────

    def _analyze_functional(self, knowledge: UnifiedKnowledge) -> FunctionalResult:
        """Analyze functional discrepancies between spec and RTL."""
        result = FunctionalResult()

        # Check reset requirements vs implementation
        for reset_spec in knowledge.spec.reset_behavior:
            for sig in reset_spec.affected_signals:
                # Verify signal has reset in RTL
                found_reset = False
                for module in knowledge.rtl.modules:
                    for block in module.always_blocks:
                        if block.has_reset and sig in block.signals_written:
                            if self._signal_has_reset(sig, block.raw_code):
                                found_reset = True
                                break

                if not found_reset:
                    result.issues.append(FunctionalIssue(
                        issue_type="missing_reset",
                        description=(
                            f"Spec requires '{sig}' to be reset to "
                            f"{reset_spec.reset_values.get(sig, '0')}, "
                            f"but RTL does not reset this signal"
                        ),
                        spec_requirement=(
                            f"Section: {reset_spec.section} — "
                            f"{reset_spec.reset_signal} resets {sig}"
                        ),
                        rtl_implementation="Signal has no reset assignment in any sequential block",
                        signal=sig,
                        severity="critical",
                    ))

        if result.issues:
            result.summary = f"Found {len(result.issues)} functional issue(s)"
        else:
            result.summary = "No functional discrepancies detected"

        self.logger.info(f"  → Functional: {len(result.issues)} issues")
        return result

    # ─── Module 3: CDC Analyzer ────────────────────────────────────

    def _analyze_cdc(self, knowledge: UnifiedKnowledge) -> CDCResult:
        """Analyze clock domain crossing issues."""
        result = CDCResult()

        for module in knowledge.rtl.modules:
            if len(module.clock_domains) > 1:
                # Multiple clock domains detected
                domains = module.clock_domains
                result.clock_domains = [
                    {
                        "name": d.clock_signal,
                        "clock": d.clock_signal,
                        "signals": d.signals,
                    }
                    for d in domains
                ]

                # Check for signals crossing domains without synchronizers
                for i, d1 in enumerate(domains):
                    for j, d2 in enumerate(domains):
                        if i >= j:
                            continue
                        crossing = set(d1.signals) & set(d2.signals)
                        for sig in crossing:
                            result.crossings.append(CDCIssue(
                                issue_type="unsynchronized_crossing",
                                description=(
                                    f"Signal '{sig}' appears in both "
                                    f"'{d1.clock_signal}' and '{d2.clock_signal}' domains"
                                ),
                                source_domain=d1.clock_signal,
                                destination_domain=d2.clock_signal,
                                signal=sig,
                                module=module.name,
                                file=module.file,
                            ))

            # Check for async resets
            for block in module.always_blocks:
                if block.reset_signal and "negedge" in block.sensitivity_list:
                    result.async_resets.append(block.reset_signal)

        result.summary = (
            f"Found {len(result.crossings)} CDC issue(s), "
            f"{len(result.async_resets)} async reset(s)"
        )
        self.logger.info(f"  → CDC: {len(result.crossings)} crossings")
        return result

    # ─── Module 4: Lint Analyzer ───────────────────────────────────

    def _analyze_lint(self, knowledge: UnifiedKnowledge) -> LintResult:
        """Analyze lint/coding style issues."""
        result = LintResult()
        counts = {}

        for module in knowledge.rtl.modules:
            # Collect issues already found by parser
            for block in module.always_blocks:
                for issue_str in block.issues:
                    issue_type = issue_str.split(":")[0].strip()
                    description = issue_str.split(":", 1)[-1].strip() if ":" in issue_str else issue_str

                    result.issues.append(LintIssue(
                        issue_type=issue_type,
                        description=description,
                        module=module.name,
                        file=module.file,
                        line_number=block.line_start,
                        code_snippet=block.raw_code[:200],
                    ))
                    counts[issue_type] = counts.get(issue_type, 0) + 1

            # Check for unused ports (ports not appearing in any always block)
            all_read = set()
            all_written = set()
            for block in module.always_blocks:
                all_read.update(block.signals_read)
                all_written.update(block.signals_written)

            for port in module.ports:
                if port.direction == "input" and port.name not in all_read:
                    if port.name not in ("clk", "rst_n", "rst", "reset"):
                        result.issues.append(LintIssue(
                            issue_type="unused_variable",
                            description=f"Input port '{port.name}' appears unused",
                            signal=port.name,
                            module=module.name,
                            file=module.file,
                            severity="low",
                        ))
                        counts["unused_variable"] = counts.get("unused_variable", 0) + 1

        result.issue_counts = counts
        result.summary = f"Found {len(result.issues)} lint issue(s)"
        self.logger.info(f"  → Lint: {len(result.issues)} issues")
        return result

    # ─── Module 5: Structural Analyzer ─────────────────────────────

    def _analyze_structural(self, knowledge: UnifiedKnowledge) -> StructuralResult:
        """Analyze structural design issues (FSMs, dead states, etc.)."""
        result = StructuralResult()

        for module in knowledge.rtl.modules:
            for fsm in module.fsms:
                state_names = {s.name for s in fsm.states}
                target_states = {t.to_state for t in fsm.transitions}
                source_states = {t.from_state for t in fsm.transitions}

                # Find dead states (states with no outgoing transitions)
                dead = state_names - source_states
                for ds in dead:
                    if ds != "default":
                        result.issues.append(StructuralIssue(
                            issue_type="dead_state",
                            description=f"State '{ds}' has no outgoing transitions",
                            module=module.name,
                            element=ds,
                            file=module.file,
                        ))

                # Find unreachable states (states with no incoming transitions)
                unreachable = state_names - target_states - {fsm.reset_state}
                for us in unreachable:
                    if us != fsm.reset_state:
                        result.issues.append(StructuralIssue(
                            issue_type="unreachable_logic",
                            description=f"State '{us}' may be unreachable",
                            module=module.name,
                            element=us,
                            file=module.file,
                        ))

                result.fsm_analysis.append({
                    "name": fsm.name,
                    "total_states": len(fsm.states),
                    "reachable_states": len(state_names - unreachable),
                    "dead_states": list(dead),
                    "has_default": fsm.has_default,
                })

        result.summary = f"Found {len(result.issues)} structural issue(s)"
        self.logger.info(f"  → Structural: {len(result.issues)} issues")
        return result

    # ─── Module 6: Protocol Compliance ─────────────────────────────

    def _analyze_protocol(self, knowledge: UnifiedKnowledge) -> ProtocolResult:
        """Analyze protocol compliance (APB/AHB/AXI/Wishbone)."""
        result = ProtocolResult()

        # Detect protocols from port names and spec
        protocol_signals = {
            "APB": ["psel", "penable", "pwrite", "paddr", "pwdata", "prdata", "pready"],
            "AHB": ["hsel", "htrans", "hwrite", "haddr", "hwdata", "hrdata", "hready"],
            "AXI": ["awvalid", "awready", "wvalid", "wready", "bvalid", "bready",
                     "arvalid", "arready", "rvalid", "rready"],
            "Wishbone": ["wb_cyc", "wb_stb", "wb_we", "wb_ack"],
        }

        for module in knowledge.rtl.modules:
            port_names = {p.name.lower() for p in module.ports}
            for proto, signals in protocol_signals.items():
                matching = [s for s in signals if any(s in pn for pn in port_names)]
                if len(matching) >= 3:
                    result.detected_protocols.append(proto)

        # Check protocol rules from spec
        for rule in knowledge.spec.protocol_rules:
            result.detected_protocols.append(rule.protocol)

        result.detected_protocols = list(set(result.detected_protocols))
        result.summary = f"Detected protocols: {', '.join(result.detected_protocols) or 'none'}"
        self.logger.info(f"  → Protocol: {len(result.detected_protocols)} detected")
        return result

    # ─── Module 7: Misc Analyzer ───────────────────────────────────

    def _analyze_misc(self, knowledge: UnifiedKnowledge) -> MiscResult:
        """Analyze miscellaneous issues."""
        result = MiscResult()

        # Check reset sequencing
        for module in knowledge.rtl.modules:
            has_async_reset = False
            has_sync_reset = False
            for block in module.always_blocks:
                if block.reset_signal:
                    if "negedge" in block.sensitivity_list or "posedge" in block.sensitivity_list:
                        if block.reset_signal in block.sensitivity_list:
                            has_async_reset = True
                        else:
                            has_sync_reset = True

            if has_async_reset and has_sync_reset:
                result.issues.append(MiscIssue(
                    issue_type="reset_sequencing",
                    description=(
                        f"Module '{module.name}' mixes async and sync resets"
                    ),
                    module=module.name,
                    file=module.file,
                    severity="medium",
                ))

        result.summary = f"Found {len(result.issues)} miscellaneous issue(s)"
        self.logger.info(f"  → Misc: {len(result.issues)} issues")
        return result

    # ─── Primary Root Cause Determination ──────────────────────────

    def _determine_primary_root_cause(
        self, analysis: RTLAnalysis, classification: Classification
    ) -> RTLAnalysis:
        """Determine the primary root cause across all sub-modules."""

        # Priority order: X-Trace > Functional > CDC > Lint > Structural > Protocol > Misc
        if analysis.xtrace.severity in ("critical", "high"):
            analysis.primary_root_cause = analysis.xtrace.summary
            analysis.primary_category = "X Propagation"
            analysis.confidence = 95 if analysis.xtrace.severity == "critical" else 85
        elif analysis.functional.issues:
            critical = [i for i in analysis.functional.issues if i.severity == "critical"]
            if critical:
                analysis.primary_root_cause = critical[0].description
                analysis.primary_category = "Functional"
                analysis.confidence = 90
            else:
                analysis.primary_root_cause = analysis.functional.issues[0].description
                analysis.primary_category = "Functional"
                analysis.confidence = 75
        elif analysis.cdc.crossings:
            analysis.primary_root_cause = analysis.cdc.crossings[0].description
            analysis.primary_category = "CDC"
            analysis.confidence = 70
        elif analysis.lint.issues:
            analysis.primary_root_cause = analysis.lint.issues[0].description
            analysis.primary_category = "Lint"
            analysis.confidence = 60
        elif analysis.structural.issues:
            analysis.primary_root_cause = analysis.structural.issues[0].description
            analysis.primary_category = "Structural"
            analysis.confidence = 65
        else:
            analysis.primary_root_cause = "No specific RTL issue identified"
            analysis.primary_category = "Unknown"
            analysis.confidence = 30

        return analysis
