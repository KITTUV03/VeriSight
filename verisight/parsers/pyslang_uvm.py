"""
pyslang-backed UVM testbench knowledge builder.

Class-based UVM code cannot be *fully elaborated* without the UVM library
(uvm_pkg) and its macros (uvm_macros.svh). But it *parses* cleanly, so this
builder uses the pyslang **syntax tree** to authoritatively discover classes,
interfaces and packages — replacing the fragile class-finding regex of the old
parser — and then reuses the existing per-class body extractors for the parts
that are driven by UVM macros / library types (config_db, factory overrides,
TLM connections, analysis ports), which no frontend can resolve standalone.

The result is explicitly flagged ``degraded`` when UVM dependencies are
unresolved, with the pyslang diagnostics preserved, so downstream consumers
never mistake partial UVM analysis for a fully elaborated testbench.
"""

from __future__ import annotations

from typing import Any, List, Set

from verisight.schemas.tb_schema import TBKnowledge, UVMComponentInfo
from verisight.parsers.sv_frontend import CompileResult
from verisight.utils.file_utils import read_file
from verisight.utils.logger import get_logger

logger = get_logger("pyslang_uvm")


def _kind(node: Any) -> str:
    return str(getattr(node, "kind", "")).split(".")[-1]


def _find_nodes(root: Any, kinds: Set[str]) -> List[Any]:
    """Depth-first collect all syntax nodes of the given kinds."""
    out: List[Any] = []

    def walk(n):
        if _kind(n) in kinds:
            out.append(n)
        try:
            for ch in n:
                walk(ch)
        except TypeError:
            pass

    walk(root)
    return out


def _file_of(sm: Any, node: Any) -> str:
    try:
        return sm.getFileName(node.getFirstToken().location)
    except Exception:
        return ""


def _class_body_text(class_node: Any) -> str:
    """Member text of a class (excludes the `class ... ;` header)."""
    try:
        return "".join(str(i) for i in class_node.items)
    except Exception:
        # fall back to everything after the first ';'
        txt = str(class_node)
        idx = txt.find(";")
        return txt[idx + 1:] if idx >= 0 else txt


def _parent_raw(class_node: Any) -> str:
    ec = getattr(class_node, "extendsClause", None)
    if ec is None:
        return ""
    try:
        base = getattr(ec, "baseName", None)
        if base is not None:
            return str(base).strip()
        return str(ec).replace("extends", "", 1).strip()
    except Exception:
        return ""


def build_tb_knowledge(result: CompileResult, file_list: List[str]) -> TBKnowledge:
    """Build TBKnowledge from a pyslang CompileResult (syntax-tree based)."""
    # Reuse the battle-tested per-class / per-file extractors from the legacy
    # parser (imported lazily to avoid an import cycle).
    from verisight.parsers import uvm_parser as up

    sm = result.source_manager
    tb = TBKnowledge()
    tb.file_list = file_list

    seen_classes: Set[str] = set()
    seen_interfaces: Set[str] = set()

    # ─── Classes (authoritative discovery via pyslang syntax tree) ─────
    class_nodes: List[Any] = []
    for tree in result.syntax_trees:
        try:
            class_nodes.extend(_find_nodes(tree.root, {"ClassDeclaration"}))
        except Exception:
            continue

    for cnode in class_nodes:
        try:
            name = str(cnode.name).strip()
        except Exception:
            continue
        if not name or name in seen_classes:
            continue
        seen_classes.add(name)

        parent_raw = _parent_raw(cnode)
        body = _class_body_text(cnode)
        file = _file_of(sm, cnode)

        base = up._get_base_class(parent_raw)
        comp_type = up.UVM_COMPONENT_TYPES.get(base, "") or up._infer_component_type(name)

        if comp_type == "transaction":
            tb.transactions.append(up._parse_transaction(name, file, parent_raw, body))
        elif comp_type == "sequence":
            tb.sequences.append(up._parse_sequence(name, file, parent_raw, body))
        elif comp_type == "driver":
            tb.drivers.append(up._parse_driver(name, file, parent_raw, body))
        elif comp_type == "monitor":
            tb.monitors.append(up._parse_monitor(name, file, parent_raw, body))
        elif comp_type == "scoreboard":
            tb.scoreboards.append(up._parse_scoreboard(name, file, parent_raw, body))
        else:
            tb.components.append(UVMComponentInfo(
                name=name,
                component_type=comp_type or "component",
                file=file,
                parent_class=parent_raw,
                phase_methods=up._extract_phase_methods(body),
            ))

        tb.factory_overrides.extend(up._extract_factory_overrides(body))
        tb.config_db_entries.extend(up._extract_config_db(body, name))
        tb.tlm_connections.extend(up._extract_tlm_connections(body, name))

    # ─── Interfaces (authoritative via pyslang) ────────────────────────
    from verisight.utils.sv_lexer import strip_comments
    for tree in result.syntax_trees:
        for inode in _find_nodes(tree.root, {"InterfaceDeclaration"}):
            file = _file_of(sm, inode)
            # Name from the pyslang header (comments in trivia would fool a
            # regex, e.g. "// ... interface with ..." → "with").
            iname = ""
            try:
                header = getattr(inode, "header", None)
                if header is not None and getattr(header, "name", None) is not None:
                    iname = str(header.name).strip()
            except Exception:
                iname = ""
            # Details (signals/clocking/modports) from the comment-stripped body.
            info = up._parse_interface(file, strip_comments(str(inode)))
            if iname:
                info.name = iname
            if info.name and info.name not in seen_interfaces:
                seen_interfaces.add(info.name)
                tb.interfaces.append(info)

    # ─── Packages (authoritative via pyslang) ──────────────────────────
    pkg_names: Set[str] = set()
    for tree in result.syntax_trees:
        for pnode in _find_nodes(tree.root, {"PackageDeclaration"}):
            pname = ""
            try:
                # package/module/program share a header carrying the name
                header = getattr(pnode, "header", None)
                if header is not None and getattr(header, "name", None) is not None:
                    pname = str(header.name).strip()
                elif getattr(pnode, "name", None) is not None:
                    pname = str(pnode.name).strip()
            except Exception:
                pname = ""
            if pname:
                pkg_names.add(pname)
    tb.packages = sorted(pkg_names)

    # ─── Coverage & assertions (per-file raw text, matching legacy) ─────
    seen_cov: Set[str] = set()
    for f in file_list:
        content = read_file(f)
        if not content:
            continue
        for cov in up._extract_coverage(f, content):
            if cov.name not in seen_cov:
                seen_cov.add(cov.name)
                tb.coverage.append(cov)
        tb.assertions.extend(up._extract_assertions(f, content))

    tb.parser_status = result.status
    return tb
