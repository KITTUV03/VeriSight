"""
Pydantic schema for parser diagnostics and status.

Shared by the pyslang-backed SystemVerilog frontend (``sv_frontend``) and the
RTL/UVM knowledge builders. Every structured diagnostic carries a category,
severity, and source location so downstream consumers can distinguish genuine
syntax errors from missing dependencies, elaboration/semantic errors, and
style warnings — instead of collapsing everything into "parse failed".
"""

from typing import List
from pydantic import BaseModel, Field


# ─── Diagnostic categories ──────────────────────────────────────────────
# Kept as plain string constants (not an Enum) so they serialize cleanly to
# JSON and remain forward-compatible if new categories are added.
CATEGORY_SYNTAX = "syntax"                  # genuine grammar/syntax error
CATEGORY_MISSING_DEPENDENCY = "missing_dependency"  # unknown module/class/pkg/macro/include
CATEGORY_ELABORATION = "elaboration"        # error found only during elaboration
CATEGORY_SEMANTIC = "semantic"              # type/semantic error (resolved scope)
CATEGORY_STYLE = "style"                    # lint-style warning
CATEGORY_UNSUPPORTED = "unsupported"        # construct the frontend cannot represent
CATEGORY_TOOL = "tool"                      # frontend/tool failure (not the source's fault)

# ─── Severities (mirror slang DiagnosticSeverity) ───────────────────────
SEVERITY_FATAL = "fatal"
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_NOTE = "note"


class ParserDiagnostic(BaseModel):
    """A single structured diagnostic from the SystemVerilog frontend."""
    severity: str = Field(description="fatal/error/warning/note")
    category: str = Field(
        description="syntax/missing_dependency/elaboration/semantic/style/unsupported/tool"
    )
    message: str = Field(description="Human-readable, actionable message")
    file: str = Field(default="", description="Source file path")
    line: int = Field(default=0, description="1-based line number")
    column: int = Field(default=0, description="1-based column number")
    code: str = Field(default="", description="Frontend diagnostic code name (e.g. ExpectedToken)")
    stage: str = Field(default="", description="Stage that produced it: syntax/elaboration")

    def is_error(self) -> bool:
        return self.severity in (SEVERITY_ERROR, SEVERITY_FATAL)

    def location_str(self) -> str:
        if self.file:
            return f"{self.file}:{self.line}:{self.column}"
        return f"line {self.line}:{self.column}"


class ParserStatus(BaseModel):
    """
    Status block attached to parsed knowledge so downstream consumers never
    mistake degraded/partial analysis for a complete AST.
    """
    backend: str = Field(
        default="pyslang",
        description="Parser backend actually used: pyslang / regex-fallback / none"
    )
    backend_version: str = Field(default="", description="Backend version string")
    degraded: bool = Field(
        default=False,
        description="True if analysis is partial/approximate (fallback used or "
                    "elaboration incomplete due to missing dependencies)"
    )
    elaborated: bool = Field(
        default=False,
        description="True if semantic elaboration (symbol/type resolution) succeeded"
    )
    syntax_ok: bool = Field(
        default=True,
        description="True if no genuine syntax errors were found"
    )
    diagnostics: List[ParserDiagnostic] = Field(
        default_factory=list,
        description="All structured diagnostics (syntax, missing-dep, semantic, style)"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Free-form notes about degradation / limitations"
    )

    def errors(self) -> List[ParserDiagnostic]:
        return [d for d in self.diagnostics if d.is_error()]

    def by_category(self, category: str) -> List[ParserDiagnostic]:
        return [d for d in self.diagnostics if d.category == category]
