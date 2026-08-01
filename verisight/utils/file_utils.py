"""
File I/O utilities for VeriSight framework.

Provides file discovery, safe JSON I/O with Pydantic serialization,
and source file reading helpers.
"""

import json
from pathlib import Path
from typing import List, Optional, Union, Type, TypeVar

from pydantic import BaseModel

from verisight.utils.logger import get_logger

logger = get_logger("file_utils")

T = TypeVar("T", bound=BaseModel)

# File extensions for each input category
RTL_EXTENSIONS = {".sv", ".v", ".svh", ".vh"}
TB_EXTENSIONS = {".sv", ".svh", ".v", ".vh"}
LOG_EXTENSIONS = {".log", ".txt", ".rpt"}
SPEC_EXTENSIONS = {".md", ".txt", ".rst"}
COVERAGE_EXTENSIONS = {".rpt", ".txt", ".ucdb", ".xml"}


def discover_files(
    directory: Union[str, Path],
    extensions: set[str],
    recursive: bool = True,
) -> List[Path]:
    """
    Discover files in a directory matching given extensions.

    Args:
        directory: Directory to search.
        extensions: Set of file extensions to match (e.g., {'.sv', '.v'}).
        recursive: Whether to search recursively.

    Returns:
        Sorted list of matching file paths.
    """
    directory = Path(directory)
    if not directory.exists():
        logger.warning(f"Directory does not exist: {directory}")
        return []

    if not directory.is_dir():
        # Single file provided
        if directory.suffix in extensions:
            return [directory]
        return []

    pattern = "**/*" if recursive else "*"
    files = sorted(
        f for f in directory.glob(pattern)
        if f.is_file() and f.suffix.lower() in extensions
    )

    logger.info(f"Discovered {len(files)} files in {directory}")
    return files


def read_file(filepath: Union[str, Path]) -> str:
    """
    Read a text file and return its contents.

    Args:
        filepath: Path to the file.

    Returns:
        File contents as a string.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        return ""

    try:
        return filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return ""


def read_file_lines(filepath: Union[str, Path]) -> List[str]:
    """
    Read a text file and return its lines.

    Args:
        filepath: Path to the file.

    Returns:
        List of lines (with newlines stripped).
    """
    content = read_file(filepath)
    if not content:
        return []
    return content.splitlines()


def save_json(
    data: Union[BaseModel, dict, list],
    filepath: Union[str, Path],
    indent: int = 2,
) -> None:
    """
    Save data to a JSON file.

    Args:
        data: Pydantic model, dict, or list to serialize.
        filepath: Output file path.
        indent: JSON indentation level.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, BaseModel):
        json_str = data.model_dump_json(indent=indent)
    else:
        json_str = json.dumps(data, indent=indent, default=str)

    filepath.write_text(json_str, encoding="utf-8")
    logger.info(f"Saved JSON: {filepath}")


def load_json(
    filepath: Union[str, Path],
    model_class: Optional[Type[T]] = None,
) -> Union[T, dict, None]:
    """
    Load data from a JSON file, optionally parsing into a Pydantic model.

    Args:
        filepath: Path to JSON file.
        model_class: Optional Pydantic model class for validation.

    Returns:
        Parsed model instance or raw dict, or None on error.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        logger.error(f"JSON file not found: {filepath}")
        return None

    try:
        raw = json.loads(filepath.read_text(encoding="utf-8"))
        if model_class:
            return model_class.model_validate(raw)
        return raw
    except Exception as e:
        logger.error(f"Error loading JSON {filepath}: {e}")
        return None


def save_text(content: str, filepath: Union[str, Path]) -> None:
    """Save text content to a file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Saved: {filepath}")


def get_file_snippet(
    filepath: Union[str, Path],
    line_start: int,
    line_end: int,
    context: int = 3,
) -> str:
    """
    Extract a code snippet from a file with surrounding context.

    Args:
        filepath: Source file path.
        line_start: Start line (1-indexed).
        line_end: End line (1-indexed, inclusive).
        context: Number of context lines before/after.

    Returns:
        Formatted code snippet with line numbers.
    """
    lines = read_file_lines(filepath)
    if not lines:
        return ""

    start = max(0, line_start - 1 - context)
    end = min(len(lines), line_end + context)

    snippet_lines = []
    for i in range(start, end):
        marker = ">>>" if line_start - 1 <= i < line_end else "   "
        snippet_lines.append(f"{marker} {i + 1:4d} | {lines[i]}")

    return "\n".join(snippet_lines)
