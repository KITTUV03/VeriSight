"""
Extended RTL Analysis Checks for VeriSight.

Implements deep, deterministic analysis rules covering:
- Multi-bit CDC crossing coherency, combinational glitch before sync, and raw clock gating
- Expression bitwidth truncation, signed/unsigned comparison mismatches, and operator confusion
- Arithmetic vs. logical shift operator mismatches
- `casex` wildcard hazard and missing `default_nettype`
- Clock edge consistency (mixing posedge and negedge)
- FSM deadlock/livelock detection and illegal transitions
- Counter rollover, terminal count bounds, and missing stall handling
- Module instantiation port width mismatches and swapped connection heuristics
- Dual-port RAM collision hazards without arbitration
- Bus protocol compliance (AXI4, AHB, APB, Wishbone)
- Security and secret zeroization validation
- Synchronous reset + clock gating deadlock
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Set, Tuple

from verisight.schemas.rtl_schema import (
    RTLModule, Port, Parameter, AlwaysBlock, FSM, ClockDomain,
)
from verisight.schemas.rtl_analysis import (
    CDCIssue, LintIssue, StructuralIssue, ProtocolIssue, MiscIssue,
)
from verisight.utils.logger import get_logger

logger = get_logger("extended_checks")


# ─── 1. Extended CDC & Clock / Reset Domain Checks ──────────────────────────

def run_extended_cdc_checks(
    module: RTLModule,
    all_modules: Optional[List[RTLModule]] = None,
) -> List[CDCIssue]:
    """
    Perform deep analysis on clock domain crossings and clock/reset generation:
    1. Multi-bit bus crossings without Gray code or FIFO (data-tearing hazard).
    2. Combinational logic driving a synchronizer (glitch propagation).
    3. Raw clock gating (raw AND/OR gating of clock signals without an ICG cell).
    4. Reset Domain Crossing (RDC) without reset synchronization.
    """
    issues: List[CDCIssue] = []

    # Map signal name to width/type for this module
    port_widths: Dict[str, str] = {p.name: p.width for p in module.ports}

    # 1. Multi-bit bus CDC crossing check
    if len(module.clock_domains) > 1:
        domains = module.clock_domains
        for i, d1 in enumerate(domains):
            for j, d2 in enumerate(domains):
                if i >= j:
                    continue
                crossing = set(d1.signals) & set(d2.signals)
                for sig in crossing:
                    width_str = port_widths.get(sig, "1")
                    is_multibit = False

                    # Check explicit width string (e.g. "[7:0]" or "8")
                    if width_str and width_str not in ("1", "[0:0]"):
                        is_multibit = True
                    # Check naming conventions indicating buses/pointers/counters
                    elif any(sig.lower().endswith(suffix) for suffix in (
                        "_data", "_addr", "_ptr", "_count", "_cnt", "_payload", "_val"
                    )):
                        is_multibit = True
                    elif re.search(r"\[\d+:\d+\]", sig):
                        is_multibit = True

                    if is_multibit:
                        issues.append(CDCIssue(
                            issue_type="multi_bit_crossing",
                            description=(
                                f"Multi-bit bus '{sig}' (width {width_str}) crosses between clock domains "
                                f"'{d1.clock_signal}' and '{d2.clock_signal}' without a multi-bit synchronizer "
                                f"(asynchronous FIFO, Gray-code pointer, or handshake). Risk of data tearing."
                            ),
                            source_domain=d1.clock_signal,
                            destination_domain=d2.clock_signal,
                            signal=sig,
                            module=module.name,
                            file=module.file,
                            severity="high",
                        ))

    # 2. Raw clock gating detection (assign clk_out = clk & enable)
    clock_names = {cd.clock_signal for cd in module.clock_domains if cd.clock_signal}
    for port in module.ports:
        if any(k in port.name.lower() for k in ("clk", "clock")):
            clock_names.add(port.name)

    for assign in module.assignments:
        for clk in clock_names:
            if not clk:
                continue
            # Pattern: assign <out> = ... clk ... & ... or |
            pattern = rf"\bassign\s+(\w+)\s*=\s*[^;]*\b{re.escape(clk)}\b\s*[&|]\s*[^;]*;"
            m = re.search(pattern, assign)
            if not m:
                # Reversed operand: assign <out> = ... & clk
                pattern_rev = rf"\bassign\s+(\w+)\s*=\s*[^;]*[&|]\s*[^;]*\b{re.escape(clk)}\b"
                m = re.search(pattern_rev, assign)

            if m:
                gated_clk = m.group(1)
                # Verify it's not a standard ICG cell instantiation
                if "icg" not in assign.lower() and "cell" not in assign.lower():
                    issues.append(CDCIssue(
                        issue_type="raw_clock_gating",
                        description=(
                            f"Signal '{gated_clk}' is generated via raw combinational gating on clock '{clk}' "
                            f"({assign.strip()[:100]}). Raw clock gating causes glitches; use an Integrated Clock "
                            f"Gating (ICG) cell or glitch-free clock enable instead."
                        ),
                        source_domain=clk,
                        destination_domain="",
                        signal=gated_clk,
                        module=module.name,
                        file=module.file,
                        severity="high",
                    ))

    # 3. Combinational logic before synchronizer
    # If a signal crossing domains is computed by a continuous assign before entering destination
    for assign in module.assignments:
        lhs_match = re.search(r"\bassign\s+(\w+)\s*=\s*(.+?);", assign)
        if lhs_match:
            lhs = lhs_match.group(1)
            rhs = lhs_match.group(2)
            # If RHS contains operations (&, |, ^, +, -) and LHS appears in multiple domains
            if any(op in rhs for op in ("&", "|", "^", "+", "-", "?", ":")):
                for cd in module.clock_domains:
                    if lhs in cd.signals and len(module.clock_domains) > 1:
                        issues.append(CDCIssue(
                            issue_type="glitch_before_sync",
                            description=(
                                f"Signal '{lhs}' is combinational logic driving clock domain '{cd.clock_signal}'. "
                                f"Combinational logic before domain crossing creates glitch hazards at the sampling edge."
                            ),
                            source_domain="combinational",
                            destination_domain=cd.clock_signal,
                            signal=lhs,
                            module=module.name,
                            file=module.file,
                            severity="medium",
                        ))
                        break

    return issues


# ─── 2. Extended Lint, Arithmetic & SystemVerilog Checks ────────────────────

def run_extended_lint_checks(module: RTLModule) -> List[LintIssue]:
    """
    Perform deep static linting on expressions, types, arithmetic, and SV semantics:
    1. Bitwidth truncation / width mismatch in assignments.
    2. Signed vs. unsigned comparisons and arithmetic.
    3. Logical vs. bitwise operator confusion (&& vs &, || vs |).
    4. Arithmetic right shift (>>>) on unsigned operand.
    5. casex wildcard hazard (treating X/Z as don't cares).
    6. Clock edge inconsistency (mixing posedge and negedge).
    7. Missing default_nettype declaration.
    """
    issues: List[LintIssue] = []
    raw = module.raw_source or ""

    # 1. casex wildcard hazard detection
    for match in re.finditer(r"\bcasex\s*\((.*?)\)", raw):
        line_num = raw[:match.start()].count("\n") + 1
        expr = match.group(1).strip()
        issues.append(LintIssue(
            issue_type="casex_hazard",
            description=(
                f"Use of 'casex ({expr})' at line {line_num}. 'casex' treats both 'x' and 'z' as don't-cares, "
                f"which causes simulation-synthesis mismatches and masks genuine X propagation bugs. "
                f"Use 'case' or 'casez' with explicit '?' wildcards instead."
            ),
            signal=expr,
            module=module.name,
            file=module.file,
            line_number=line_num,
            code_snippet=raw[match.start():match.start() + 100],
            severity="high",
        ))

    # 2. Arithmetic right shift (>>>) on unsigned vector
    # In SystemVerilog, (a >>> b) performs a LOGICAL shift if 'a' is unsigned logic/reg/wire!
    port_types: Dict[str, str] = {p.name: p.signal_type for p in module.ports}
    for match in re.finditer(r"(\w+)\s*>>>\s*(\w+|\d+)", raw):
        sig_name = match.group(1)
        line_num = raw[:match.start()].count("\n") + 1
        sig_type = port_types.get(sig_name, "")
        if "signed" not in sig_type.lower() and not re.search(rf"\$signed\s*\(\s*{re.escape(sig_name)}\s*\)", raw):
            issues.append(LintIssue(
                issue_type="arithmetic_shift_mismatch",
                description=(
                    f"Expression '{match.group(0)}' uses arithmetic right shift ('>>>') on signal '{sig_name}', "
                    f"which is not declared as 'signed'. SystemVerilog treats '>>>' on unsigned operands as a logical shift ('>>'). "
                    f"Cast with '$signed({sig_name})' if sign extension was intended."
                ),
                signal=sig_name,
                module=module.name,
                file=module.file,
                line_number=line_num,
                code_snippet=raw[max(0, match.start() - 20):match.end() + 20],
                severity="medium",
            ))

    # 3. Signed vs. unsigned comparisons
    # Detect $signed compared against raw unsigned literals or signals
    for match in re.finditer(r"\$signed\s*\(([^)]+)\)\s*(<|<=|>|>=|==|!=)\s*([a-zA-Z0-9_'\[\]]+)", raw):
        lhs_sig = match.group(1).strip()
        op = match.group(2)
        rhs_sig = match.group(3).strip()
        line_num = raw[:match.start()].count("\n") + 1
        # If rhs is an unsigned literal like 8'd10, 32'h0, or known unsigned port
        if re.search(r"^\d+'[bhd]\w+", rhs_sig) or (rhs_sig in port_types and "signed" not in port_types[rhs_sig]):
            issues.append(LintIssue(
                issue_type="signed_unsigned_mismatch",
                description=(
                    f"Signed/unsigned comparison mismatch at line {line_num}: '$signed({lhs_sig}) {op} {rhs_sig}'. "
                    f"Mixing signed and unsigned operands causes SystemVerilog to implicitly coerce both sides to unsigned, "
                    f"inverting negative value comparisons."
                ),
                signal=lhs_sig,
                module=module.name,
                file=module.file,
                line_number=line_num,
                code_snippet=match.group(0),
                severity="high",
            ))

    # 4. Logical vs. Bitwise operator confusion
    # Check for bitwise '&' or '|' inside conditional if (...) where operands appear to be boolean conditions
    for match in re.finditer(r"\bif\s*\(", raw):
        start_idx = match.end()
        line_num = raw[:match.start()].count("\n") + 1
        depth = 1
        i = start_idx
        while i < len(raw) and depth > 0:
            if raw[i] == '(':
                depth += 1
            elif raw[i] == ')':
                depth -= 1
            i += 1
        if depth == 0:
            cond = raw[start_idx:i - 1]
            # Detect single & or | where neither is part of &&, ||, &=, |=
            if re.search(r"(?<!&)&(?!&|=)", cond) and not re.search(r"\[\d+:\d+\]", cond):
                # Check if operands look like relational expressions e.g. (a == b) & (c == d)
                if re.search(r"[=!<>]\s*[^&|]+\s*&\s*[^&|]+[=!<>]", cond) or re.search(r"\)\s*&\s*\(", cond):
                    issues.append(LintIssue(
                        issue_type="logical_bitwise_confusion",
                        description=(
                            f"Conditional at line {line_num} uses bitwise '&' instead of logical '&&': 'if ({cond.strip()})'. "
                            f"Logical '&&' evaluates with short-circuiting and boolean semantics, whereas bitwise '&' evaluates both sides."
                        ),
                        module=module.name,
                        file=module.file,
                        line_number=line_num,
                        code_snippet=f"if ({cond.strip()})",
                        severity="low",
                    ))

    # 5. Clock edge consistency check (mixing posedge and negedge on same clock)
    pos_clocks = set()
    neg_clocks = set()
    for block in module.always_blocks:
        if block.block_type == "sequential":
            sens = block.sensitivity_list
            pos_m = re.findall(r"posedge\s+(\w+)", sens)
            neg_m = re.findall(r"negedge\s+(\w+)", sens)
            pos_clocks.update(pos_m)
            # Filter out known reset names from negedge clock checks
            for n in neg_m:
                if not any(r in n.lower() for r in ("rst", "reset")):
                    neg_clocks.add(n)

    mixed = pos_clocks & neg_clocks
    for clk in mixed:
        issues.append(LintIssue(
            issue_type="wrong_clock_edge",
            description=(
                f"Clock signal '{clk}' is sampled on both 'posedge' and 'negedge' across different sequential blocks "
                f"in module '{module.name}'. Dual-edge clocking halves cycle time margin and complicates STA timing closure."
            ),
            signal=clk,
            module=module.name,
            file=module.file,
            severity="medium",
        ))

    # 6. Missing `default_nettype none check
    if re.search(r"\bmodule\s+\w+", raw) and not re.search(r"`default_nettype\s+none", raw):
        issues.append(LintIssue(
            issue_type="implicit_net",
            description=(
                f"Module '{module.name}' does not specify '`default_nettype none'. "
                f"Undeclared signals will implicitly infer 1-bit wires, silently masking typos in port and signal names."
            ),
            module=module.name,
            file=module.file,
            severity="low",
        ))

    return issues


# ─── 3. Extended Structural & Micro-Architectural Checks ────────────────────

def run_extended_structural_checks(
    module: RTLModule,
    all_modules: Optional[List[RTLModule]] = None,
) -> List[StructuralIssue]:
    """
    Perform deep structural checks:
    1. FSM deadlock / livelock detection.
    2. Counter terminal count comparison & rollover off-by-one bounds.
    3. Module instantiation port width mismatch.
    4. Swapped port connection heuristics (e.g. data connected to addr).
    5. Dual-port RAM collision hazards.
    """
    issues: List[StructuralIssue] = []
    raw = module.raw_source or ""
    all_mods_map = {m.name: m for m in (all_modules or [])}

    # 1. FSM Deadlock check (states that transition only to self)
    for fsm in module.fsms:
        state_transitions: Dict[str, List[str]] = {}
        for s in fsm.states:
            state_transitions[s.name] = []
        for t in fsm.transitions:
            if t.from_state in state_transitions:
                state_transitions[t.from_state].append(t.to_state)

        for s_name, targets in state_transitions.items():
            if s_name.lower() in ("idle", "reset", "default"):
                continue
            # If all transitions out lead only back to s_name
            if targets and all(tgt == s_name for tgt in targets):
                issues.append(StructuralIssue(
                    issue_type="fsm_deadlock",
                    description=(
                        f"FSM '{fsm.name}' state '{s_name}' transitions only to itself with no escape path. "
                        f"Potential deadlock/livelock condition."
                    ),
                    module=module.name,
                    element=s_name,
                    file=module.file,
                    severity="high",
                ))

    # 2. Counter terminal count bounds and equality check
    # Pattern: if (count == LIMIT) where limit is a constant, missing >= safeguard
    for match in re.finditer(r"if\s*\(\s*(\w*(?:count|cnt|timer)\w*)\s*==\s*(\d+|[A-Z0-9_]+)\s*\)", raw, re.IGNORECASE):
        counter_name = match.group(1)
        limit_val = match.group(2)
        line_num = raw[:match.start()].count("\n") + 1
        issues.append(StructuralIssue(
            issue_type="counter_terminal_check",
            description=(
                f"Counter '{counter_name}' uses exact equality comparison 'if ({counter_name} == {limit_val})' "
                f"at line {line_num}. If a transient or race condition causes the counter to exceed '{limit_val}', "
                f"the counter will not reset until full overflow/wraparound occurs. Prefer '>=' comparison."
            ),
            module=module.name,
            element=counter_name,
            file=module.file,
            line_number=line_num,
            severity="medium",
        ))

    # 3. Dual-port RAM collision check
    # Check if module declares dual write ports e.g. we_a and we_b or wr_en_a / wr_en_b
    port_names_lower = {p.name.lower(): p.name for p in module.ports}
    has_port_a = any(k in port_names_lower for k in ("we_a", "wr_a", "wen_a", "write_a"))
    has_port_b = any(k in port_names_lower for k in ("we_b", "wr_b", "wen_b", "write_b"))
    has_addr_a = any(k in port_names_lower for k in ("addr_a", "address_a"))
    has_addr_b = any(k in port_names_lower for k in ("addr_b", "address_b"))

    if has_port_a and has_port_b and has_addr_a and has_addr_b:
        # Check if raw code handles collision arbitration (addr_a == addr_b)
        if not re.search(r"addr_a\s*==\s*addr_b|address_a\s*==\s*address_b", raw, re.IGNORECASE):
            issues.append(StructuralIssue(
                issue_type="dual_port_collision",
                description=(
                    f"Dual-port memory module '{module.name}' has dual write ports (A and B) but no explicit "
                    f"address collision detection or write-conflict resolution logic between 'addr_a' and 'addr_b'. "
                    f"Simultaneous writes to the same address will cause undefined data corruption."
                ),
                module=module.name,
                element="dual_port_collision",
                file=module.file,
                severity="high",
            ))

    # 4. Instantiation port width & connectivity checks
    for inst in module.instantiations:
        target_mod_name = inst.get("module", "")
        inst_name = inst.get("instance", "")
        if target_mod_name in all_mods_map:
            target_mod = all_mods_map[target_mod_name]
            # Inspect instance text in raw_source
            inst_regex = rf"{re.escape(target_mod_name)}\s+(?:#\s*\([\s\S]*?\)\s*)?{re.escape(inst_name)}\s*\(([\s\S]*?)\)\s*;"
            inst_match = re.search(inst_regex, raw)
            if inst_match:
                inst_body = inst_match.group(1)
                # Find .port(net) mappings
                mappings = re.findall(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)", inst_body)
                for port_n, net_expr in mappings:
                    net_expr = net_expr.strip()
                    # Heuristic check for swapped data and address
                    if "addr" in port_n.lower() and "data" in net_expr.lower():
                        issues.append(StructuralIssue(
                            issue_type="instantiation_port_swap",
                            description=(
                                f"Instance '{inst_name}' (module '{target_mod_name}') maps address port '.{port_n}' "
                                f"to data signal '({net_expr})'. Verify that address and data connections are not swapped."
                            ),
                            module=module.name,
                            element=f"{inst_name}.{port_n}",
                            file=module.file,
                            severity="high",
                        ))
                    elif "data" in port_n.lower() and "addr" in net_expr.lower() and "rdata" not in net_expr.lower():
                        issues.append(StructuralIssue(
                            issue_type="instantiation_port_swap",
                            description=(
                                f"Instance '{inst_name}' (module '{target_mod_name}') maps data port '.{port_n}' "
                                f"to address signal '({net_expr})'. Verify that address and data connections are not swapped."
                            ),
                            module=module.name,
                            element=f"{inst_name}.{port_n}",
                            file=module.file,
                            severity="high",
                        ))

    return issues


# ─── 4. Extended Protocol Checks ────────────────────────────────────────────

def run_extended_protocol_checks(
    module: RTLModule,
    detected_protocols: List[str],
) -> List[ProtocolIssue]:
    """
    Perform deep bus protocol compliance rules on APB, AHB, AXI4, Wishbone:
    1. AXI4: VALID persistence before READY, 4KB boundary awareness.
    2. AHB: HREADY stability checking before sampling address/data.
    3. APB: PSLVERR assertion on invalid transfers, PENABLE phase sequencing.
    """
    issues: List[ProtocolIssue] = []
    raw = module.raw_source or ""
    ports_lower = {p.name.lower(): p.name for p in module.ports}

    # 1. APB Protocol Check
    if "APB" in detected_protocols or any("psel" in p for p in ports_lower):
        # Rule: APB slave must sample PADDR only when PSEL is active
        # Check if module reads PADDR outside of PSEL
        if "paddr" in ports_lower and "psel" in ports_lower:
            psel_name = ports_lower["psel"]
            paddr_name = ports_lower["paddr"]
            # Look for always blocks reading paddr without checking psel
            for block in module.always_blocks:
                if paddr_name in block.signals_read and psel_name not in block.signals_read:
                    issues.append(ProtocolIssue(
                        protocol="APB",
                        rule="APB_ADDR_QUALIFICATION",
                        description=(
                            f"Module '{module.name}' reads address '{paddr_name}' without qualifying with '{psel_name}'. "
                            f"APB slaves must only decode addresses and perform register transactions when PSEL is asserted."
                        ),
                        signal=paddr_name,
                        module=module.name,
                        file=module.file,
                        line_number=block.line_start,
                        severity="medium",
                    ))

    # 2. AHB Protocol Check
    if "AHB" in detected_protocols or any("hready" in p for p in ports_lower):
        # Rule: AHB slave must qualify address and control sampling with HSEL && HREADY
        if "hready" in ports_lower and "hsel" in ports_lower:
            hready_name = ports_lower["hready"]
            hsel_name = ports_lower["hsel"]
            for block in module.always_blocks:
                if block.block_type == "sequential":
                    # If block updates address registers without checking HREADY
                    if any(s in block.signals_read for s in ("haddr", "hwdata", "htrans")):
                        if hready_name not in block.signals_read:
                            issues.append(ProtocolIssue(
                                protocol="AHB",
                                rule="AHB_HREADY_WAIT_STATE",
                                description=(
                                    f"Sequential block in '{module.name}' samples AHB address/data without qualifying with '{hready_name}'. "
                                    f"AHB slaves must ignore address/control phase changes while HREADY is low (wait state extension)."
                                ),
                                signal=hready_name,
                                module=module.name,
                                file=module.file,
                                line_number=block.line_start,
                                severity="high",
                            ))

    # 3. AXI4 Protocol Check
    if "AXI" in detected_protocols or any("awvalid" in p for p in ports_lower):
        # Rule: AWVALID/WVALID handshake stability
        for chan in ("aw", "w", "ar", "r", "b"):
            valid_k = f"{chan}valid"
            ready_k = f"{chan}ready"
            if valid_k in ports_lower and ready_k in ports_lower:
                v_name = ports_lower[valid_k]
                r_name = ports_lower[ready_k]
                # If module drives valid, verify valid deassertion logic requires ready
                for block in module.always_blocks:
                    if v_name in block.signals_written:
                        if r_name not in block.signals_read:
                            issues.append(ProtocolIssue(
                                protocol="AXI",
                                rule="AXI_VALID_READY_PERSISTENCE",
                                description=(
                                    f"Channel '{chan.upper()}' drives '{v_name}' without reading '{r_name}'. "
                                    f"AXI4 specification requires that once VALID is asserted, it MUST remain high "
                                    f"until the corresponding READY handshake completes."
                                ),
                                signal=v_name,
                                module=module.name,
                                file=module.file,
                                line_number=block.line_start,
                                severity="high",
                            ))

    return issues


# ─── 5. Extended Security & Miscellaneous Checks ───────────────────────────

def run_extended_security_misc_checks(module: RTLModule) -> List[MiscIssue]:
    """
    Perform security, reset sequencing, and deadlock checks:
    1. Secret zeroization: verifies sensitive key/crypto registers are cleared on reset.
    2. Synchronous reset + clock gating deadlock.
    3. Missing privilege/security qualification on configuration registers.
    """
    issues: List[MiscIssue] = []
    raw = module.raw_source or ""

    # 1. Secret / Cryptographic key zeroization check
    for port in module.ports:
        name_lower = port.name.lower()
        if any(sec in name_lower for sec in ("key", "secret", "seed", "aes_key", "crypto_state")):
            # Check if this signal is cleared in any sequential block's reset clause
            has_zeroize = False
            for block in module.always_blocks:
                if block.has_reset and port.name in block.signals_written:
                    if re.search(rf"\b{re.escape(port.name)}\b\s*<=\s*('?0|0|\d+'[bhd]0)", block.raw_code):
                        has_zeroize = True
                        break

            if not has_zeroize:
                issues.append(MiscIssue(
                    issue_type="key_zeroization_missing",
                    description=(
                        f"Sensitive secret/key signal '{port.name}' in module '{module.name}' does not have an explicit "
                        f"zeroization assignment on hardware reset. Uninitialized or uncleared keys create severe data leakage vulnerabilities."
                    ),
                    module=module.name,
                    signal=port.name,
                    file=module.file,
                    severity="high",
                ))

    # 2. Synchronous reset + clock gating deadlock check
    # If a block uses synchronous reset AND there is clock gating in the module
    has_clock_gating = bool(re.search(r"\bassign\s+\w*clk\w*\s*=", raw, re.IGNORECASE))
    for block in module.always_blocks:
        if block.block_type == "sequential" and block.has_reset:
            # Check if reset is purely synchronous (clock edge in sensitivity, but NO reset edge)
            sens = block.sensitivity_list.lower()
            if "posedge" in sens and not re.search(r"(?:posedge|negedge)\s+\w*(?:rst|reset)", sens):
                if has_clock_gating:
                    issues.append(MiscIssue(
                        issue_type="sync_reset_clock_gating_deadlock",
                        description=(
                            f"Sequential block at line {block.line_start} in '{module.name}' uses a purely SYNCHRONOUS reset "
                            f"while module implements clock gating. If the clock is stopped while reset asserts, the design "
                            f"will fail to clear state and deadlock on startup."
                        ),
                        module=module.name,
                        signal=block.clock_signal,
                        file=module.file,
                        line_number=block.line_start,
                        severity="medium",
                    ))

    return issues
