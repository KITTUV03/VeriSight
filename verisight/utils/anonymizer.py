"""
AST/Token-based RTL Anonymization and IP Masking Engine for VeriSight.

Enables confidential verification in zero-leakage enterprise environments
by scrubbing proprietary signal names, module hierarchies, register maps,
and confidential comments before reasoning, and restoring them seamlessly.
"""

import re
from typing import Dict, Tuple, Set
from verisight.utils.sv_lexer import _MASTER_REGEX, TOKEN_PATTERNS, TokenType, SV_KEYWORDS
from verisight.utils.logger import get_logger

logger = get_logger("rtl_anonymizer")

# Standard hardware control signals that do not constitute proprietary IP leakage
STANDARD_SIGNALS: Set[str] = {
    "clk", "clock", "aclk", "hclk", "pclk", "core_clk", "sys_clk",
    "rst", "rst_n", "aresetn", "hresetn", "presetn", "reset", "reset_n",
    "enable", "en", "valid", "ready", "ack", "req", "data", "addr",
    "wr", "rd", "write", "read", "we", "re", "wdata", "rdata",
    "sel", "strb", "resp", "error", "err",
}


class RTLAnonymizer:
    """
    Bi-directional RTL IP anonymizer.
    Scrubs proprietary naming and trade secrets while preserving exact circuit logic.
    """

    def __init__(self):
        self.orig_to_anon: Dict[str, str] = {}
        self.anon_to_orig: Dict[str, str] = {}
        self._mod_counter = 0
        self._sig_counter = 0
        self._param_counter = 0

    def _get_anon_name(self, original: str, category: str = "sig") -> str:
        """Get or create an anonymized replacement identifier."""
        if original in self.orig_to_anon:
            return self.orig_to_anon[original]

        low = original.lower()
        if low in STANDARD_SIGNALS:
            return original

        if category == "mod":
            self._mod_counter += 1
            anon = f"DUT_MODULE_{self._mod_counter:02d}"
        elif category == "param":
            self._param_counter += 1
            anon = f"PARAM_{self._param_counter:02d}"
        else:
            self._sig_counter += 1
            anon = f"sig_{self._sig_counter:03d}"

        self.orig_to_anon[original] = anon
        self.anon_to_orig[anon] = original
        return anon

    def anonymize_rtl(self, sv_source: str) -> Tuple[str, Dict[str, str]]:
        """
        Anonymize SystemVerilog source code:
        - Replaces proprietary module names
        - Replaces internal register and signal identifiers
        - Replaces non-standard parameter names
        - Scrubs proprietary header comments
        """
        output_parts = []
        prev_token_value = ""

        for match in _MASTER_REGEX.finditer(sv_source):
            val = match.group()
            token_type = TokenType.IDENTIFIER
            for i, (tt, _) in enumerate(TOKEN_PATTERNS):
                if match.group(f"g{i}") is not None:
                    token_type = tt
                    break

            if token_type == TokenType.COMMENT:
                # Scrub proprietary comments / copyright / internal disclosures
                if any(k in val.lower() for k in ("copyright", "proprietary", "confidential", "secret")):
                    output_parts.append("/* [CONFIDENTIAL IP COMMENTS SCRUBBED FOR SECURITY] */")
                else:
                    output_parts.append(val)

            elif token_type == TokenType.IDENTIFIER:
                if val in SV_KEYWORDS:
                    output_parts.append(val)
                elif prev_token_value in ("module", "endmodule"):
                    anon_val = self._get_anon_name(val, category="mod")
                    output_parts.append(anon_val)
                elif prev_token_value in ("parameter", "localparam"):
                    anon_val = self._get_anon_name(val, category="param")
                    output_parts.append(anon_val)
                else:
                    anon_val = self._get_anon_name(val, category="sig")
                    output_parts.append(anon_val)

            else:
                output_parts.append(val)

            if token_type not in (TokenType.WHITESPACE, TokenType.NEWLINE, TokenType.COMMENT):
                prev_token_value = val

        anonymized_source = "".join(output_parts)
        logger.info(
            f"🛡️ RTL Anonymizer scrubbed {len(self.orig_to_anon)} proprietary identifiers "
            f"for zero cloud RTL leakage."
        )
        return anonymized_source, dict(self.anon_to_orig)

    def de_anonymize(self, text: str) -> str:
        """
        Restore original proprietary signal and module names from an anonymized patch or text.
        """
        result = text
        # Replace longer tokens first to avoid substring collisions
        sorted_keys = sorted(self.anon_to_orig.keys(), key=len, reverse=True)
        for anon in sorted_keys:
            orig = self.anon_to_orig[anon]
            result = re.sub(r'\b' + re.escape(anon) + r'\b', orig, result)
        return result
