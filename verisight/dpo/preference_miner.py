"""
Verification Planning Preference Miner & Oracle for DPO.

Mines and curates high-fidelity pairwise preferences for VeriSight Workflow 2:
1. Automated EDA Compiler Oracle: Evaluates candidate SVA and covergroups using
   pyslang AST parsing to deterministically prefer syntactically and semantically
   sound verification artifacts.
2. Human-in-the-Loop Logging: Captures engineer reviews, upvotes/downvotes, and
   diff edits from the Web Studio Coverage Cockpit.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from verisight.utils.logger import get_logger

logger = get_logger("preference_miner")

DEFAULT_PREFERENCE_FILE = Path("data/preferences/workflow2_dpo.jsonl")


class VerificationPreferenceMiner:
    """Mines, validates, and logs DPO preference pairs for Workflow 2."""

    def __init__(self, preference_path: Optional[Path] = None):
        self.preference_path = preference_path or DEFAULT_PREFERENCE_FILE
        self.preference_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_sv_syntax_with_slang(self, sv_code: str) -> Tuple[bool, List[str]]:
        """
        Runs pyslang compiler frontend on an SV snippet to check syntax correctness.
        Returns (is_valid, list_of_diagnostics).
        """
        try:
            import pyslang
            # Wrap snippet in a dummy module if it's just an assertion or covergroup
            clean_code = sv_code.strip()
            if not ("module" in clean_code and "endmodule" in clean_code):
                test_harness = (
                    "module __dpo_eval_harness (\n"
                    "  input logic clk, rst_n, pclk, presetn, aclk, aresetn,\n"
                    "  input logic scl, sda, psel, penable, pready, pwrite, pslverr,\n"
                    "  input logic [31:0] paddr, wdata, rdata,\n"
                    "  input logic bvalid, bready, [1:0] bresp, [3:0] bid,\n"
                    "  input logic [15:0] fifo_count, empty, full, wr_en, rd_en,\n"
                    "  input logic [7:0] fsm_state, state, bus_busy, bus_active\n"
                    ");\n"
                    f"{clean_code}\n"
                    "endmodule\n"
                )
            else:
                test_harness = clean_code

            tree = pyslang.SyntaxTree.fromText(test_harness)
            diags = [str(d) for d in tree.diagnostics]
            has_errors = any("error:" in d.lower() for d in diags)
            return (not has_errors, diags)
        except ImportError:
            logger.debug("pyslang not available for deterministic AST checking. Falling back to rule heuristics.")
            # Heuristic syntax check
            has_unbalanced_braces = clean_code.count("{") != clean_code.count("}")
            has_unbalanced_parens = clean_code.count("(") != clean_code.count(")")
            is_valid = not (has_unbalanced_braces or has_unbalanced_parens)
            return (is_valid, ["heuristic validation"])
        except Exception as e:
            return (False, [str(e)])

    def evaluate_and_mine_candidates(
        self,
        prompt: str,
        candidate_a: str,
        candidate_b: str,
        category: str = "sva_protocol",
        feature_id: str = "AUTO_REQ",
    ) -> Optional[Dict[str, Any]]:
        """
        Uses the EDA compiler oracle to determine chosen vs. rejected candidates.
        """
        valid_a, diags_a = self.validate_sv_syntax_with_slang(candidate_a)
        valid_b, diags_b = self.validate_sv_syntax_with_slang(candidate_b)

        if valid_a and not valid_b:
            chosen = candidate_a
            rejected = candidate_b
        elif valid_b and not valid_a:
            chosen = candidate_b
            rejected = candidate_a
        else:
            # If both pass or both fail, prefer the more specific/informative candidate
            score_a = len(candidate_a) + (50 if "disable iff" in candidate_a else 0) + (50 if "$error" in candidate_a else 0)
            score_b = len(candidate_b) + (50 if "disable iff" in candidate_b else 0) + (50 if "$error" in candidate_b else 0)
            if score_a > score_b:
                chosen, rejected = candidate_a, candidate_b
            elif score_b > score_a:
                chosen, rejected = candidate_b, candidate_a
            else:
                return None  # Indistinguishable

        pair = {
            "prompt": prompt,
            "chosen": chosen.strip(),
            "rejected": rejected.strip(),
            "category": category,
            "feature": feature_id,
            "timestamp": datetime.now().isoformat(),
        }
        self.append_preference(pair)
        return pair

    def record_human_feedback(
        self,
        prompt: str,
        chosen: str,
        rejected: str,
        category: str = "human_review",
        feature_id: str = "REVIEW_REQ",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Records an explicit human verification lead preference."""
        pair = {
            "prompt": prompt,
            "chosen": chosen.strip(),
            "rejected": rejected.strip(),
            "category": category,
            "feature": feature_id,
            "notes": notes,
            "source": "human_lead",
            "timestamp": datetime.now().isoformat(),
        }
        self.append_preference(pair)
        return pair

    def append_preference(self, pair: Dict[str, Any]):
        """Safely appends a preference pair to the JSONL dataset."""
        with open(self.preference_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(pair) + "\n")
        logger.info(f"Recorded DPO preference pair for feature '{pair.get('feature', 'UNKNOWN')}'")

    def get_statistics(self) -> Dict[str, Any]:
        """Computes summary statistics of the current DPO preference corpus."""
        if not self.preference_path.exists():
            return {"total_pairs": 0, "categories": {}}

        total = 0
        categories: Dict[str, int] = {}
        with open(self.preference_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    total += 1
                    cat = data.get("category", "unspecified")
                    categories[cat] = categories.get(cat, 0) + 1
                except Exception:
                    continue

        return {
            "total_pairs": total,
            "categories": categories,
            "dataset_path": str(self.preference_path),
        }

