"""
Pre-commit SystemVerilog syntax validator for VeriSight.

Validates SystemVerilog / Verilog files with the pyslang frontend and reports
genuine syntax errors with actionable source locations. It is designed to be
used as a git pre-commit hook or a CI gate.

Key behaviours (per the migration requirements):
  * Validates modern SystemVerilog — does NOT reject constructs that the old
    PyVerilog/Verilog-2005 path could not parse (interfaces, always_ff,
    structs, SVA, packages, classes, ...).
  * Distinguishes GENUINE SYNTAX errors from missing includes / unresolved
    dependencies / semantic / elaboration errors. By default only syntax
    errors fail the check; missing-dependency and semantic issues are reported
    as warnings (a pre-commit hook rarely has the full UVM library on hand).
  * Returns a non-zero exit status for genuine syntax failures.
  * Never silently passes because the parser crashed: a frontend/tool failure
    is itself a non-zero exit.
  * Supports a syntax-only mode (default) and a stricter mode that also fails
    on semantic/elaboration errors (``--strict``), for projects that compile
    full designs.

Exit codes:
  0  all files OK (no genuine syntax errors; or, in --strict, no errors at all)
  1  one or more files had genuine syntax errors (or errors in --strict)
  2  tool/usage error (pyslang unavailable, no files, frontend crash)

Usage:
  python -m verisight.tools.sv_validate [options] FILE [FILE ...]
  python -m verisight.tools.sv_validate -I inc_dir -D UVM_NO_DPI file.sv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence

from verisight.parsers import sv_frontend
from verisight.schemas.parser_schema import (
    CATEGORY_SYNTAX, CATEGORY_MISSING_DEPENDENCY, CATEGORY_TOOL,
)

EXIT_OK = 0
EXIT_SYNTAX_FAIL = 1
EXIT_TOOL_ERROR = 2

_RTL_EXTS = {".sv", ".svh", ".v", ".vh"}


def _expand(paths: Sequence[str]) -> List[str]:
    """Expand directories to their SV/Verilog files; keep files as-is."""
    out: List[str] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            out.extend(
                str(f) for f in sorted(path.rglob("*"))
                if f.suffix.lower() in _RTL_EXTS
            )
        else:
            out.append(str(path))
    return out


def validate(
    files: Sequence[str],
    include_dirs: Sequence[str] = (),
    defines: Sequence[str] = (),
    strict: bool = False,
    per_file: bool = True,
) -> int:
    """
    Validate files and print a report. Returns a process exit code.

    Args:
        files: files/dirs to validate.
        include_dirs / defines: passed to the frontend.
        strict: if True, semantic/elaboration errors also fail (not just syntax).
        per_file: compile each file independently (better syntax isolation for a
            pre-commit hook). When False, all files compile together (needed for
            cross-file package/define resolution).
    """
    if not sv_frontend.is_available():
        print(
            f"error: pyslang frontend unavailable ({sv_frontend.unavailable_reason()}). "
            "Install it with: pip install pyslang",
            file=sys.stderr,
        )
        return EXIT_TOOL_ERROR

    expanded = _expand(files)
    if not expanded:
        print("error: no SystemVerilog/Verilog files to validate.", file=sys.stderr)
        return EXIT_TOOL_ERROR

    targets = [[f] for f in expanded] if per_file else [expanded]

    total_syntax = 0
    total_missing = 0
    total_semantic = 0
    tool_failures = 0
    failed_files: List[str] = []

    for group in targets:
        try:
            result = sv_frontend.compile_files(
                group, include_dirs=include_dirs, defines=defines,
                single_unit=not per_file,
            )
        except Exception as exc:  # frontend must never silently pass
            tool_failures += 1
            print(f"error: frontend crashed on {group}: {exc!r}", file=sys.stderr)
            continue

        diags = result.diagnostics
        syntax_errs = [d for d in diags if d.category == CATEGORY_SYNTAX and d.is_error()]
        missing = [d for d in diags if d.category == CATEGORY_MISSING_DEPENDENCY]
        tool_errs = [d for d in diags if d.category == CATEGORY_TOOL and d.is_error()]
        semantic_errs = [
            d for d in diags
            if d.is_error()
            and d.category not in (CATEGORY_SYNTAX, CATEGORY_MISSING_DEPENDENCY, CATEGORY_TOOL)
        ]

        # When syntax errors coexist with missing dependencies, the syntax
        # errors are very likely SPURIOUS — a downstream consequence of
        # unexpanded macros / missing packages (e.g. `uvm_component_utils not
        # defined breaks the following statement). In syntax-only mode we do NOT
        # fail on these; we report the file as UNVERIFIED and ask the user to
        # supply -I/-D so a definitive check can run. --strict still fails.
        spurious_syntax = bool(syntax_errs) and bool(missing) and not strict
        genuine_syntax = [] if spurious_syntax else syntax_errs

        total_syntax += len(genuine_syntax)
        total_missing += len(missing)
        total_semantic += len(semantic_errs)
        tool_failures += len(tool_errs)

        label = ", ".join(group)
        group_failed = (
            bool(genuine_syntax) or bool(tool_errs) or (strict and (semantic_errs or missing))
        )

        if group_failed:
            failed_files.extend(group)
            print(f"FAIL  {label}")
        elif spurious_syntax:
            print(f"UNVERIFIED  {label}  (syntax masked by missing dependencies)")
        elif missing or semantic_errs:
            print(f"OK (with warnings)  {label}")
        else:
            print(f"OK  {label}")

        for d in genuine_syntax:
            print(f"    syntax error:  {d.location_str()}: {d.message} ({d.code})")
        if spurious_syntax:
            for d in syntax_errs:
                print(f"    syntax (likely spurious, missing deps): "
                      f"{d.location_str()}: {d.message} ({d.code})")
        for d in tool_errs:
            print(f"    tool error:    {d.location_str()}: {d.message} ({d.code})")
        sem_prefix = "semantic error:" if strict else "semantic warn: "
        for d in semantic_errs:
            print(f"    {sem_prefix}{d.location_str()}: {d.message} ({d.code})")
        for d in missing:
            print(f"    missing dep:   {d.location_str()}: {d.message} ({d.code})")

    # ─── Summary ───────────────────────────────────────────────────────
    print()
    print(
        f"Summary: {total_syntax} syntax error(s), "
        f"{total_semantic} semantic error(s), "
        f"{total_missing} missing-dependency diagnostic(s), "
        f"{tool_failures} tool failure(s)."
    )
    if total_missing and not strict:
        print(
            "Note: missing-dependency diagnostics are NOT failures in syntax-only "
            "mode (supply -I/-D or the dependent packages for full resolution)."
        )

    if tool_failures:
        print(f"Validation TOOL-ERROR for: {', '.join(sorted(set(failed_files)))}")
        return EXIT_TOOL_ERROR
    if failed_files:
        print(f"Validation FAILED for: {', '.join(sorted(set(failed_files)))}")
        return EXIT_SYNTAX_FAIL
    return EXIT_OK


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verisight-sv-validate",
        description="Validate SystemVerilog/Verilog syntax with the pyslang frontend.",
    )
    parser.add_argument("files", nargs="+", help="Files or directories to validate")
    parser.add_argument(
        "-I", "--include", action="append", default=[], metavar="DIR",
        help="`include search directory (repeatable)",
    )
    parser.add_argument(
        "-D", "--define", action="append", default=[], metavar="NAME[=VALUE]",
        help="Macro define (repeatable)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Also fail on semantic/elaboration errors (needs full design context)",
    )
    parser.add_argument(
        "--single-unit", action="store_true",
        help="Compile all files together instead of one-by-one",
    )
    args = parser.parse_args(argv)

    return validate(
        args.files,
        include_dirs=args.include,
        defines=args.define,
        strict=args.strict,
        per_file=not args.single_unit,
    )


if __name__ == "__main__":
    sys.exit(main())
