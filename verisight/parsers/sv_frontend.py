"""
Centralized SystemVerilog frontend for VeriSight, backed by pyslang (the
Python bindings for the Slang SystemVerilog compiler frontend).

This module is the single place where SystemVerilog source is turned into a
structurally meaningful representation. It replaces the previous regex-only
approach that could not parse modern SystemVerilog / UVM. All downstream
consumers (RTL parser, UVM parser, X-Tracer, pre-commit validator) go through
here.

Design principles (per the migration requirements):
  * Real parsing + optional elaboration via Slang (IEEE 1800), not tokenization.
  * Structured, categorized diagnostics with file/line/column and severity.
  * Multi-file compilation with include directories, macro defines, and
    single/multi compilation-unit control.
  * Explicit, labelled failure handling. Parsing never silently degrades to
    regex: callers ask for a fallback explicitly, and any degraded result is
    flagged (``ParserStatus.degraded``) with the original diagnostics preserved.
  * Distinguishes genuine syntax errors from missing includes / unresolved
    dependencies / semantic errors.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Sequence

from verisight.schemas.parser_schema import (
    ParserDiagnostic, ParserStatus,
    CATEGORY_SYNTAX, CATEGORY_MISSING_DEPENDENCY, CATEGORY_ELABORATION,
    CATEGORY_SEMANTIC, CATEGORY_STYLE, CATEGORY_TOOL,
    SEVERITY_ERROR, SEVERITY_FATAL, SEVERITY_WARNING, SEVERITY_NOTE,
)
from verisight.utils.logger import get_logger

logger = get_logger("sv_frontend")


# ─── pyslang availability (detected once, never fatal) ──────────────────
try:
    import pyslang
    from pyslang import driver as _slang_driver
    from pyslang import syntax as _slang_syntax
    from pyslang import ast as _slang_ast
    from pyslang import SourceManager as _SourceManager
    from pyslang import DiagnosticEngine as _DiagnosticEngine

    PYSLANG_AVAILABLE = True
    PYSLANG_VERSION = getattr(pyslang, "__version__", "unknown")
    _PYSLANG_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - only when pyslang truly absent
    PYSLANG_AVAILABLE = False
    PYSLANG_VERSION = ""
    _PYSLANG_IMPORT_ERROR = repr(exc)


# ─── Diagnostic code classification ─────────────────────────────────────
# Code names (slang DiagCode) that mean "a referenced thing could not be found"
# — i.e. a missing include / package / macro / unresolved dependency, NOT a
# genuine grammar error. These are the key to telling "your file is broken"
# apart from "you didn't give me the library it depends on".
_MISSING_DEP_CODES = {
    "UnknownModule", "UnknownInterface", "UnknownProgram", "UnknownPackage",
    "UnknownClass", "UnknownClassOrPackage", "UnknownMember", "UnknownPackageMember",
    "UndeclaredIdentifier", "UnknownDirective", "UnknownSystemName",
    "UnknownSystemMethod", "UnknownSystemTimingCheck", "UnknownFormatSpecifier",
    "CouldNotResolveHierarchicalPath", "UnresolvedForwardTypedef",
    "UnknownPackageName", "UndeclaredButFoundPackage", "ImportNameCollision",
    "UnknownBindTarget", "TypoIdentifier", "RecursivePackage",
    "UnknownPrimitive", "UnknownUserDefinedNetType",
}

# Warning codes that are really "no roots / nothing to elaborate" — benign for a
# single UVM/class file parsed in isolation.
_BENIGN_ELAB_WARNINGS = {"NoTopModules", "UnusedDefinition"}

_MISSING_DEP_MESSAGE = re.compile(
    r"\bunknown (module|interface|program|class|package|member|macro|net|type|system)\b"
    r"|could not (find|resolve)"
    r"|cannot find"
    r"|unknown macro or compiler directive"
    r"|use of undeclared identifier"
    r"|unknown class or package",
    re.IGNORECASE,
)

_SYNTAX_CODE_PREFIXES = ("Expected",)
_SYNTAX_CODE_NAMES = {
    "ExpectedToken", "ExpectedExpression", "ExpectedStatement", "ExpectedMember",
    "ExpectedIdentifier", "ExpectedDeclarator", "MisplacedTrailingSeparator",
    "ExtraTosk", "ExpectedEndKeyword", "SplitBlockCommentInDirective",
    "UnbalancedMacroArgDims", "ExpectedIntegerLiteral",
}


def _severity_str(sev: Any) -> str:
    name = str(sev).split(".")[-1].lower()
    if name == "fatal":
        return SEVERITY_FATAL
    if name == "warning":
        return SEVERITY_WARNING
    if name == "note":
        return SEVERITY_NOTE
    return SEVERITY_ERROR


def _code_name(code: Any) -> str:
    # str(code) -> "DiagCode(ExpectedToken)"
    raw = str(code)
    m = re.search(r"DiagCode\(([^)]*)\)", raw)
    return m.group(1) if m else raw


def _classify(code_name: str, message: str, stage: str, severity: str) -> str:
    """Map a slang diagnostic to a VeriSight diagnostic category."""
    if code_name in _MISSING_DEP_CODES or _MISSING_DEP_MESSAGE.search(message or ""):
        return CATEGORY_MISSING_DEPENDENCY
    if (
        code_name in _SYNTAX_CODE_NAMES
        or code_name.startswith(_SYNTAX_CODE_PREFIXES)
    ):
        return CATEGORY_SYNTAX
    if severity in (SEVERITY_WARNING, SEVERITY_NOTE):
        return CATEGORY_STYLE
    # Error that survived scope resolution and isn't a missing dep → semantic;
    # if it only appeared during elaboration, mark it elaboration.
    return CATEGORY_ELABORATION if stage == "elaboration" else CATEGORY_SEMANTIC


@dataclass
class CompileResult:
    """
    Result of compiling one or more SystemVerilog sources.

    Carries both the structured status (diagnostics, backend, degraded flag)
    and live pyslang handles for builders that want to walk the AST.
    """
    status: ParserStatus
    compilation: Any = None            # pyslang.ast.Compilation or None
    syntax_trees: List[Any] = field(default_factory=list)
    source_manager: Any = None
    files: List[str] = field(default_factory=list)

    @property
    def diagnostics(self) -> List[ParserDiagnostic]:
        return self.status.diagnostics

    @property
    def syntax_ok(self) -> bool:
        return self.status.syntax_ok

    @property
    def degraded(self) -> bool:
        return self.status.degraded

    def top_instances(self) -> List[Any]:
        """Elaborated top-level module instances (empty if not elaborated)."""
        if self.compilation is None:
            return []
        try:
            return list(self.compilation.getRoot().topInstances)
        except Exception:
            return []


def is_available() -> bool:
    """Whether the pyslang frontend can be used."""
    return PYSLANG_AVAILABLE


def unavailable_reason() -> str:
    return _PYSLANG_IMPORT_ERROR or "pyslang is not installed"


# ─── Diagnostic collection ──────────────────────────────────────────────
def _collect_diagnostics(
    compilation: Any,
    syntax_trees: Sequence[Any],
    source_manager: Any,
) -> List[ParserDiagnostic]:
    """Turn a compilation's diagnostics into structured ParserDiagnostics."""
    # Identify which diagnostics came from the pure syntax (parse) stage so we
    # can tag their stage accurately. Keyed by (offset, code-name).
    syntax_keys = set()
    for tree in syntax_trees:
        try:
            for d in tree.diagnostics:
                syntax_keys.add((d.location.offset, _code_name(d.code)))
        except Exception:
            continue

    engine = _DiagnosticEngine(source_manager)
    out: List[ParserDiagnostic] = []

    try:
        all_diags = compilation.getAllDiagnostics()
    except Exception as exc:
        return [ParserDiagnostic(
            severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
            message=f"Failed to collect diagnostics: {exc!r}",
            code="DiagnosticCollection",
        )]

    for d in all_diags:
        code_name = _code_name(d.code)
        try:
            severity = _severity_str(engine.getSeverity(d.code, d.location))
        except Exception:
            severity = SEVERITY_ERROR if getattr(d, "isError", False) else SEVERITY_WARNING
        try:
            message = engine.formatMessage(d)
        except Exception:
            message = code_name
        try:
            loc = d.location
            file = source_manager.getFileName(loc)
            line = source_manager.getLineNumber(loc)
            column = source_manager.getColumnNumber(loc)
        except Exception:
            file, line, column = "", 0, 0

        stage = "syntax" if (getattr(d.location, "offset", -1), code_name) in syntax_keys else "elaboration"
        category = _classify(code_name, message, stage, severity)

        out.append(ParserDiagnostic(
            severity=severity,
            category=category,
            message=message,
            file=file,
            line=line,
            column=column,
            code=code_name,
            stage=stage,
        ))

    return out


def _finalize_status(
    diagnostics: List[ParserDiagnostic],
    backend: str,
    elaborated: bool,
) -> ParserStatus:
    syntax_errors = [
        d for d in diagnostics
        if d.category == CATEGORY_SYNTAX and d.is_error()
    ]
    missing_deps = [d for d in diagnostics if d.category == CATEGORY_MISSING_DEPENDENCY]

    status = ParserStatus(
        backend=backend,
        backend_version=PYSLANG_VERSION,
        elaborated=elaborated,
        diagnostics=diagnostics,
    )
    status.syntax_ok = len(syntax_errors) == 0

    # Degraded when: elaboration found unresolved dependencies, OR syntax errors
    # coexist with missing dependencies (the syntax errors are likely spurious,
    # caused by the missing macros/packages — we cannot fully trust the tree).
    if missing_deps:
        status.degraded = True
        status.notes.append(
            f"{len(missing_deps)} unresolved dependency diagnostic(s) "
            "(missing include/package/macro). Analysis is partial; supply "
            "include dirs / defines / dependent packages for full resolution."
        )
    return status


# ─── Public entry points ────────────────────────────────────────────────
def compile_files(
    files: Sequence[str],
    include_dirs: Sequence[str] = (),
    defines: Sequence[str] = (),
    single_unit: bool = True,
    extra_args: Sequence[str] = (),
) -> CompileResult:
    """
    Parse (and elaborate) one or more SystemVerilog files with pyslang.

    Args:
        files: Source file paths (.sv/.svh/.v/.vh).
        include_dirs: Directories searched for `include files.
        defines: Macro defines, each "NAME" or "NAME=value".
        single_unit: Compile all files as one compilation unit so packages,
            macros and typedefs defined in one file are visible to the others
            (recommended for UVM / package-based designs).
        extra_args: Additional raw slang driver arguments.

    Returns:
        CompileResult with structured status + live pyslang handles.
    """
    if not PYSLANG_AVAILABLE:
        status = ParserStatus(
            backend="none", degraded=True, elaborated=False, syntax_ok=False,
            diagnostics=[ParserDiagnostic(
                severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
                message=f"pyslang frontend unavailable: {unavailable_reason()}",
                code="PyslangUnavailable",
            )],
            notes=["pyslang not importable; no SystemVerilog frontend available."],
        )
        return CompileResult(status=status, files=list(files))

    existing = [str(f) for f in files if Path(f).exists()]
    missing = [str(f) for f in files if not Path(f).exists()]

    diagnostics: List[ParserDiagnostic] = []
    for mf in missing:
        diagnostics.append(ParserDiagnostic(
            severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
            message=f"Source file not found: {mf}", file=mf, code="FileNotFound",
        ))

    if not existing:
        status = ParserStatus(
            backend="pyslang", backend_version=PYSLANG_VERSION,
            degraded=True, elaborated=False, syntax_ok=False,
            diagnostics=diagnostics or [ParserDiagnostic(
                severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
                message="No input files provided.", code="NoInputFiles",
            )],
        )
        return CompileResult(status=status, files=list(files))

    # Build slang-driver command line.
    argv: List[str] = ["slang"]
    if single_unit:
        argv.append("--single-unit")
    for inc in include_dirs:
        argv += ["-I", str(inc)]
    for d in defines:
        argv += ["-D", str(d)]
    argv += list(extra_args)
    argv += existing
    cmd = " ".join(shlex.quote(a) for a in argv)

    try:
        drv = _slang_driver.Driver()
        drv.addStandardArgs()
        if not drv.parseCommandLine(cmd):
            raise RuntimeError("slang driver rejected command line")
        if not drv.processOptions():
            raise RuntimeError("slang driver failed to process options")
        drv.parseAllSources()
        compilation = drv.createCompilation()
        trees = list(drv.syntaxTrees)
        sm = drv.sourceManager
    except Exception as exc:
        diagnostics.append(ParserDiagnostic(
            severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
            message=f"pyslang frontend error: {exc!r}", code="FrontendError",
        ))
        status = ParserStatus(
            backend="pyslang", backend_version=PYSLANG_VERSION,
            degraded=True, elaborated=False, syntax_ok=False,
            diagnostics=diagnostics,
        )
        return CompileResult(status=status, files=list(files))

    diagnostics += _collect_diagnostics(compilation, trees, sm)
    status = _finalize_status(diagnostics, backend="pyslang", elaborated=True)
    # elaboration "succeeded" structurally even if it surfaced missing deps;
    # mark not-elaborated only on hard tool failure (handled above).
    return CompileResult(
        status=status,
        compilation=compilation,
        syntax_trees=trees,
        source_manager=sm,
        files=existing,
    )


def compile_text(
    text: str,
    name: str = "source",
    path: str = "",
) -> CompileResult:
    """
    Parse (and elaborate) an in-memory SystemVerilog snippet. Used by the
    fix-generator's syntax pre-check, where we validate generated code without
    writing a file.
    """
    if not PYSLANG_AVAILABLE:
        status = ParserStatus(
            backend="none", degraded=True, elaborated=False, syntax_ok=False,
            diagnostics=[ParserDiagnostic(
                severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
                message=f"pyslang frontend unavailable: {unavailable_reason()}",
                code="PyslangUnavailable",
            )],
        )
        return CompileResult(status=status)

    try:
        sm = _SourceManager()
        tree = _slang_syntax.SyntaxTree.fromText(text, sm, name, path)
        compilation = _slang_ast.Compilation()
        compilation.addSyntaxTree(tree)
        diagnostics = _collect_diagnostics(compilation, [tree], sm)
    except Exception as exc:
        status = ParserStatus(
            backend="pyslang", backend_version=PYSLANG_VERSION,
            degraded=True, elaborated=False, syntax_ok=False,
            diagnostics=[ParserDiagnostic(
                severity=SEVERITY_ERROR, category=CATEGORY_TOOL,
                message=f"pyslang frontend error: {exc!r}", code="FrontendError",
            )],
        )
        return CompileResult(status=status)

    status = _finalize_status(diagnostics, backend="pyslang", elaborated=True)
    return CompileResult(
        status=status, compilation=compilation,
        syntax_trees=[tree], source_manager=sm,
    )


def format_diagnostics(diags: Sequence[ParserDiagnostic], limit: int = 0) -> str:
    """Render diagnostics as a compact, actionable multi-line string."""
    items = list(diags)
    if limit:
        items = items[:limit]
    lines = []
    for d in items:
        lines.append(
            f"[{d.severity}/{d.category}] {d.location_str()}: {d.message}"
            + (f" ({d.code})" if d.code else "")
        )
    return "\n".join(lines)
