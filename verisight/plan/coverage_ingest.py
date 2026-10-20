"""
Coverage Database Ingestion Engine for VeriSight Plan.

Ingests actual simulator coverage databases and reports:
- Siemens Questa / Mentor UCDB text/xml exports (vcover report -details)
- Synopsys VCS vDB / URG text reports (urg -dir simv.vdb)
- Cadence IMC text/summary reports
- Structured JSON coverage dumps
- General EDA covergroup/coverpoint/bin execution reports

Deterministic, air-gapped, zero external network dependency.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from verisight.utils.file_utils import read_file
from verisight.utils.logger import get_logger

logger = get_logger("plan.coverage_ingest")


class IngestedBin(BaseModel):
    """Raw bin coverage sampled in simulation."""
    bin_name: str
    coverpoint_name: str
    covergroup_name: str
    hits: int = 0
    at_least: int = 1
    is_hit: bool = False
    condition: Optional[str] = None
    metric_type: str = "functional"  # functional, toggle, branch, line


class IngestedCoverpoint(BaseModel):
    """Raw coverpoint coverage sampled in simulation."""
    name: str
    covergroup_name: str
    target_signal: Optional[str] = None
    coverage_pct: float = 0.0
    total_bins: int = 0
    hit_bins: int = 0
    bins: Dict[str, IngestedBin] = Field(default_factory=dict)
    unhit_bins: List[str] = Field(default_factory=list)


class IngestedCovergroup(BaseModel):
    """Raw covergroup coverage sampled in simulation."""
    name: str
    coverage_pct: float = 0.0
    total_bins: int = 0
    hit_bins: int = 0
    coverpoints: Dict[str, IngestedCoverpoint] = Field(default_factory=dict)


class SimulatorCoverageDB(BaseModel):
    """Unified container for ingested simulator coverage database."""
    source_path: str
    simulator_format: str = "Generic"  # UCDB, Synopsys_vDB, Cadence_IMC, JSON, Generic
    overall_coverage_pct: float = 0.0
    total_bins: int = 0
    hit_bins: int = 0
    unhit_bins_count: int = 0
    covergroups: Dict[str, IngestedCovergroup] = Field(default_factory=dict)
    unhit_bins_list: List[IngestedBin] = Field(default_factory=list)
    raw_content: Optional[str] = None


class CoverageIngester:
    """Parser and normalizer for simulator coverage files."""

    def ingest(self, filepath: str) -> SimulatorCoverageDB:
        """
        Ingest any supported coverage file (JSON, UCDB text, Synopsys URG, or log).

        Args:
            filepath: Path to coverage report file or directory.

        Returns:
            SimulatorCoverageDB unified representation.
        """
        path = Path(filepath).expanduser()
        if not path.exists():
            logger.warning(f"Coverage file not found: {filepath}")
            return SimulatorCoverageDB(source_path=filepath, simulator_format="NotFound")

        # If a directory was provided (e.g. simv.vdb or coverage_dir)
        if path.is_dir():
            candidates = (
                list(path.glob("**/*urg*.txt")) +
                list(path.glob("**/*.txt")) +
                list(path.glob("**/*.json")) +
                list(path.glob("**/*.rpt")) +
                list(path.glob("**/*.log"))
            )
            if candidates:
                path = candidates[0]
                logger.info(f"Auto-selected coverage report file from directory: {path}")
            else:
                logger.warning(f"No parseable coverage reports found in directory {path}")
                return SimulatorCoverageDB(source_path=str(path), simulator_format="Directory_Empty")

        content = read_file(path)
        if not content:
            logger.warning(f"Empty coverage content in {path}")
            return SimulatorCoverageDB(source_path=str(path), simulator_format="Empty")

        # 1. Try JSON format first
        if path.suffix.lower() == ".json" or content.strip().startswith("{"):
            try:
                data = json.loads(content)
                db = self._parse_json_coverage(data, str(path))
                if db and db.total_bins > 0:
                    db.raw_content = content
                    return db
            except Exception as e:
                logger.debug(f"JSON coverage parsing failed, falling back to text parsing: {e}")

        # 2. Check for Synopsys vDB / URG format
        if "urg" in content.lower() or "synopsys" in content.lower() or "group :" in content.lower():
            db = self._parse_synopsys_urg(content, str(path))
            if db and db.total_bins > 0:
                db.raw_content = content
                return db

        # 3. Check for Questa / Mentor UCDB format
        if "vcover" in content.lower() or "questa" in content.lower() or "ucdb" in content.lower() or "covergroup:" in content.lower():
            db = self._parse_questa_ucdb(content, str(path))
            if db and db.total_bins > 0:
                db.raw_content = content
                return db

        # 4. Fallback: Generic text tabular coverage parser
        db = self._parse_generic_coverage_text(content, str(path))
        db.raw_content = content
        return db

    def _parse_json_coverage(self, data: Dict[str, Any], filepath: str) -> SimulatorCoverageDB:
        """Parse structured JSON coverage database."""
        cgs: Dict[str, IngestedCovergroup] = {}
        all_unhit: List[IngestedBin] = []
        tot_bins = 0
        tot_hits = 0

        # Handle various common JSON shapes
        cg_list = data.get("covergroups") or data.get("groups") or []
        if isinstance(cg_list, dict):
            cg_items = list(cg_list.items())
        elif isinstance(cg_list, list):
            cg_items = [(cg.get("name") or cg.get("group_name", f"cg_{i}"), cg) for i, cg in enumerate(cg_list)]
        else:
            cg_items = []

        for cg_name, cg_obj in cg_items:
            cg = IngestedCovergroup(name=cg_name)
            cp_list = cg_obj.get("coverpoints") or cg_obj.get("points") or []
            if isinstance(cp_list, dict):
                cp_items = list(cp_list.items())
            elif isinstance(cp_list, list):
                cp_items = [(cp.get("name", f"cp_{i}"), cp) for i, cp in enumerate(cp_list)]
            else:
                cp_items = []

            for cp_name, cp_obj in cp_items:
                cp = IngestedCoverpoint(
                    name=cp_name,
                    covergroup_name=cg_name,
                    target_signal=cp_obj.get("target_signal") or cp_obj.get("signal"),
                )
                bin_list = cp_obj.get("bins") or []
                if isinstance(bin_list, dict):
                    bin_items = list(bin_list.items())
                elif isinstance(bin_list, list):
                    bin_items = [(b.get("name") or b.get("bin_name", f"bin_{i}"), b) for i, b in enumerate(bin_list)]
                else:
                    bin_items = []

                for b_name, b_obj in bin_items:
                    hits = int(b_obj.get("hits", 0))
                    at_least = int(b_obj.get("at_least", 1))
                    is_hit = hits >= at_least or str(b_obj.get("status", "")).lower() in ("covered", "hit")
                    cond = b_obj.get("condition") or b_obj.get("expr") or ""

                    b_inst = IngestedBin(
                        bin_name=b_name,
                        coverpoint_name=cp_name,
                        covergroup_name=cg_name,
                        hits=hits,
                        at_least=at_least,
                        is_hit=is_hit,
                        condition=cond,
                    )
                    cp.bins[b_name] = b_inst
                    cp.total_bins += 1
                    tot_bins += 1

                    if is_hit:
                        cp.hit_bins += 1
                        tot_hits += 1
                    else:
                        cp.unhit_bins.append(b_name)
                        all_unhit.append(b_inst)

                if cp.total_bins > 0:
                    cp.coverage_pct = round((cp.hit_bins / cp.total_bins) * 100.0, 2)
                elif "coverage" in cp_obj:
                    cp.coverage_pct = float(cp_obj["coverage"])

                cg.coverpoints[cp_name] = cp
                cg.total_bins += cp.total_bins
                cg.hit_bins += cp.hit_bins

            if cg.total_bins > 0:
                cg.coverage_pct = round((cg.hit_bins / cg.total_bins) * 100.0, 2)
            elif "coverage" in cg_obj:
                cg.coverage_pct = float(cg_obj["coverage"])

            cgs[cg_name] = cg

        overall_pct = round((tot_hits / max(tot_bins, 1)) * 100.0, 2)
        if "overall_coverage" in data:
            overall_pct = float(data["overall_coverage"])

        return SimulatorCoverageDB(
            source_path=filepath,
            simulator_format="JSON",
            overall_coverage_pct=overall_pct,
            total_bins=tot_bins,
            hit_bins=tot_hits,
            unhit_bins_count=len(all_unhit),
            covergroups=cgs,
            unhit_bins_list=all_unhit,
        )

    def _parse_synopsys_urg(self, content: str, filepath: str) -> SimulatorCoverageDB:
        """Parse Synopsys VCS URG text report."""
        cgs: Dict[str, IngestedCovergroup] = {}
        all_unhit: List[IngestedBin] = []
        tot_bins = 0
        tot_hits = 0

        # Regex for Group / Coverpoint / Bins in URG
        # Group : tb_top.cg_alu
        current_cg: Optional[IngestedCovergroup] = None
        current_cp: Optional[IngestedCoverpoint] = None

        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()

            # Group header
            group_m = re.match(r"(?:Group|Covergroup)\s*[:=]\s*([^\s]+)", stripped, re.IGNORECASE)
            if group_m:
                cg_raw = group_m.group(1).split(".")[-1]
                current_cg = IngestedCovergroup(name=cg_raw)
                cgs[cg_raw] = current_cg
                current_cp = None
                continue

            # Coverpoint header
            cp_m = re.match(r"(?:Coverpoint|Point)\s*[:=]\s*([^\s]+)", stripped, re.IGNORECASE)
            if cp_m:
                cp_raw = cp_m.group(1).split(".")[-1]
                if not current_cg:
                    current_cg = IngestedCovergroup(name="cg_default")
                    cgs["cg_default"] = current_cg
                current_cp = IngestedCoverpoint(name=cp_raw, covergroup_name=current_cg.name)
                current_cg.coverpoints[cp_raw] = current_cp
                continue

            # Bin line: e.g. "bin_add  145  1  Covered" or "bin_overflow  0  1  Uncovered"
            bin_m = re.match(r"([a-zA-Z_0-9\[\]:\$]+)\s+(\d+)\s+(\d+)\s+(Covered|Uncovered|Hit|Missed)", stripped, re.IGNORECASE)
            if bin_m and current_cp and current_cg:
                b_name = bin_m.group(1)
                hits = int(bin_m.group(2))
                at_least = int(bin_m.group(3))
                status = bin_m.group(4).lower()
                is_hit = hits >= at_least or status in ("covered", "hit")

                b_inst = IngestedBin(
                    bin_name=b_name,
                    coverpoint_name=current_cp.name,
                    covergroup_name=current_cg.name,
                    hits=hits,
                    at_least=at_least,
                    is_hit=is_hit,
                )
                current_cp.bins[b_name] = b_inst
                current_cp.total_bins += 1
                tot_bins += 1
                if is_hit:
                    current_cp.hit_bins += 1
                    tot_hits += 1
                else:
                    current_cp.unhit_bins.append(b_name)
                    all_unhit.append(b_inst)

        # Calculate percentages
        for cg in cgs.values():
            for cp in cg.coverpoints.values():
                if cp.total_bins > 0:
                    cp.coverage_pct = round((cp.hit_bins / cp.total_bins) * 100.0, 2)
                cg.total_bins += cp.total_bins
                cg.hit_bins += cp.hit_bins
            if cg.total_bins > 0:
                cg.coverage_pct = round((cg.hit_bins / cg.total_bins) * 100.0, 2)

        overall_pct = round((tot_hits / max(tot_bins, 1)) * 100.0, 2)
        return SimulatorCoverageDB(
            source_path=filepath,
            simulator_format="Synopsys_vDB_URG",
            overall_coverage_pct=overall_pct,
            total_bins=tot_bins,
            hit_bins=tot_hits,
            unhit_bins_count=len(all_unhit),
            covergroups=cgs,
            unhit_bins_list=all_unhit,
        )

    def _parse_questa_ucdb(self, content: str, filepath: str) -> SimulatorCoverageDB:
        """Parse Siemens Questa / Mentor UCDB text report."""
        cgs: Dict[str, IngestedCovergroup] = {}
        all_unhit: List[IngestedBin] = []
        tot_bins = 0
        tot_hits = 0

        current_cg: Optional[IngestedCovergroup] = None
        current_cp: Optional[IngestedCoverpoint] = None

        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()

            # Covergroup header: "Covergroup /top/cg_alu"
            cg_m = re.match(r"(?:Covergroup|COVERGROUP)\s+([^\s:]+)", stripped)
            if cg_m:
                cg_raw = cg_m.group(1).rstrip("/").split("/")[-1]
                current_cg = IngestedCovergroup(name=cg_raw)
                cgs[cg_raw] = current_cg
                current_cp = None
                continue

            # Coverpoint header: "Coverpoint cp_opcode"
            cp_m = re.match(r"(?:Coverpoint|COVERPOINT)\s+([^\s:]+)", stripped)
            if cp_m:
                cp_raw = cp_m.group(1).rstrip("/").split("/")[-1]
                if not current_cg:
                    current_cg = IngestedCovergroup(name="cg_default")
                    cgs["cg_default"] = current_cg
                current_cp = IngestedCoverpoint(name=cp_raw, covergroup_name=current_cg.name)
                current_cg.coverpoints[cp_raw] = current_cp
                continue

            # Bin line: "bin_add : 120 hits" or "bin_overflow : 0 hits [UNCOVERED]"
            bin_m = re.match(r"([a-zA-Z_0-9\[\]:\$]+)\s*[:=]\s*(\d+)\s+hits?(.*)", stripped, re.IGNORECASE)
            if bin_m and current_cp and current_cg:
                b_name = bin_m.group(1)
                hits = int(bin_m.group(2))
                extra = bin_m.group(3).lower()
                is_hit = hits > 0 and "uncovered" not in extra

                b_inst = IngestedBin(
                    bin_name=b_name,
                    coverpoint_name=current_cp.name,
                    covergroup_name=current_cg.name,
                    hits=hits,
                    at_least=1,
                    is_hit=is_hit,
                )
                current_cp.bins[b_name] = b_inst
                current_cp.total_bins += 1
                tot_bins += 1
                if is_hit:
                    current_cp.hit_bins += 1
                    tot_hits += 1
                else:
                    current_cp.unhit_bins.append(b_name)
                    all_unhit.append(b_inst)

        for cg in cgs.values():
            for cp in cg.coverpoints.values():
                if cp.total_bins > 0:
                    cp.coverage_pct = round((cp.hit_bins / cp.total_bins) * 100.0, 2)
                cg.total_bins += cp.total_bins
                cg.hit_bins += cp.hit_bins
            if cg.total_bins > 0:
                cg.coverage_pct = round((cg.hit_bins / cg.total_bins) * 100.0, 2)

        overall_pct = round((tot_hits / max(tot_bins, 1)) * 100.0, 2)
        return SimulatorCoverageDB(
            source_path=filepath,
            simulator_format="Questa_UCDB",
            overall_coverage_pct=overall_pct,
            total_bins=tot_bins,
            hit_bins=tot_hits,
            unhit_bins_count=len(all_unhit),
            covergroups=cgs,
            unhit_bins_list=all_unhit,
        )

    def _parse_generic_coverage_text(self, content: str, filepath: str) -> SimulatorCoverageDB:
        """Fallback parser for generic simulator text tables."""
        cgs: Dict[str, IngestedCovergroup] = {}
        all_unhit: List[IngestedBin] = []
        tot_bins = 0
        tot_hits = 0

        current_cg = IngestedCovergroup(name="cg_simulation_closure")
        current_cp = IngestedCoverpoint(name="cp_general", covergroup_name="cg_simulation_closure")
        current_cg.coverpoints["cp_general"] = current_cp
        cgs["cg_simulation_closure"] = current_cg

        # Pattern: bin_name followed by hit count or UNCOVERED
        # e.g., bin_reset_toggle: 0 hits
        # e.g., bin_mode_fast 15 hits
        pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]?\s*(\d+)\s+hits?(?:\s*\[?(UNCOVERED|COVERED)?\]?)?",
            re.IGNORECASE
        )

        for match in pattern.finditer(content):
            b_name = match.group(1)
            hits = int(match.group(2))
            tag = (match.group(3) or "").upper()
            is_hit = hits > 0 and tag != "UNCOVERED"

            b_inst = IngestedBin(
                bin_name=b_name,
                coverpoint_name=current_cp.name,
                covergroup_name=current_cg.name,
                hits=hits,
                at_least=1,
                is_hit=is_hit,
            )
            current_cp.bins[b_name] = b_inst
            current_cp.total_bins += 1
            tot_bins += 1
            if is_hit:
                current_cp.hit_bins += 1
                tot_hits += 1
            else:
                current_cp.unhit_bins.append(b_name)
                all_unhit.append(b_inst)

        if current_cp.total_bins > 0:
            current_cp.coverage_pct = round((current_cp.hit_bins / current_cp.total_bins) * 100.0, 2)
            current_cg.total_bins = current_cp.total_bins
            current_cg.hit_bins = current_cp.hit_bins
            current_cg.coverage_pct = current_cp.coverage_pct

        overall_pct = round((tot_hits / max(tot_bins, 1)) * 100.0, 2)
        return SimulatorCoverageDB(
            source_path=filepath,
            simulator_format="Generic_EDA_Text",
            overall_coverage_pct=overall_pct,
            total_bins=tot_bins,
            hit_bins=tot_hits,
            unhit_bins_count=len(all_unhit),
            covergroups=cgs,
            unhit_bins_list=all_unhit,
        )
