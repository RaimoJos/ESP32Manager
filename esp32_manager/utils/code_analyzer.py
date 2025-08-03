"""Utilities for analyzing project source code for MicroPython compatibility.

This module provides simple static checks to help ensure that a project does
not rely on features that are commonly missing from MicroPython. The checks
are intentionally lightweight and are not meant to be a full linter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List
import ast

EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "build",
    "dist",
    "__pycache__",
    ".git",
    ".hg",
}

# Modules that are known to be unavailable or only partially supported in
# MicroPython. Importing them is likely to cause runtime failures on the
# device, so we flag them here.
FORBIDDEN_IMPORTS = {
    "asyncio",
    "multiprocessing",
    "subprocess",
    "threading",
}

# Maximum allowed line length. MicroPython targets often have limited screen
# real estate, so we keep this conservative.
MAX_LINE_LENGTH = 88

def _analyze_file(path: Path) -> List[str]:
    """Analyze a single Python file and return a list of warnings.

    Parameters
    ----------
    path:
        The path to the file being analyzed.
    """

    warnings: List[str] = []

    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        # Skip files that cannot be decoded as UTF-8 or read for any reason.
        return warnings

    # Line length check
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(line) > MAX_LINE_LENGTH:
            warnings.append(
                f"{path}:{lineno} Line too long ({len(line)} > {MAX_LINE_LENGTH})"
            )

        # Parse AST to inspect imports
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            warnings.append(f"{path}:{exc.lineno} SyntaxError: {exc.msg}")
            return warnings

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules: Iterable[str] = (alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or "").split(".")[0]]
            else:
                continue

            for module in modules:
                if module in FORBIDDEN_IMPORTS:
                    warnings.append(
                        f"{path}:{node.lineno} Forbidden import '{module}'"
                    )

        return warnings

def analyze_project(path: Path) -> List[str]:
    """Analyze all Python files under ``path`` for MicroPython compatibility.

    Parameters
    ----------
    path:
        Root directory of the project to analyze.

    Returns
    -------
    List[str]
        A list of warning strings describing potential issues.
    """

    results: List[str] = []
    for file_path in path.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in file_path.parts):
            continue
        results.extend(_analyze_file(file_path))
    return results

__all__ = ["analyze_project"]
