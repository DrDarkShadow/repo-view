"""Code summarization utilities."""

import ast
import os
import re
from typing import Optional

from repoview.config import (
    MAX_CHARS_TEXT_PREVIEW,
    MAX_LINES_FALLBACK,
    MAX_SIGNATURES_SUMMARY,
)
from repoview.core.token_counter import count_tokens


def code_summary(full_text: Optional[str], relative_path: str, tokens_full: int) -> str:
    """Generate a code summary for a file."""
    if not full_text:
        return "[empty]"
    
    if relative_path.endswith(".py"):
        try:
            return _python_summary(full_text, relative_path, tokens_full)
        except Exception:
            pass
    
    return _basic_code_summary(full_text, relative_path, tokens_full)


def _python_summary(full_text: str, relative_path: str, tokens_full: int) -> str:
    """Generate Python-specific summary using AST."""
    tree = ast.parse(full_text)
    parts = [f"[Python summary: {os.path.basename(relative_path)}]"]
    imports: set = set()
    sigs: list = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name:
                    imports.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ast.unparse(node.args) if hasattr(ast, "unparse") else "..."
            sig = f"  def {node.name}({args})"
            if node.returns and hasattr(ast, "unparse"):
                sig += f" -> {ast.unparse(node.returns)}"
            sigs.append(sig)
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
            sig = f"  class {node.name}" + (f"({', '.join(bases)})" if bases else "")
            sigs.append(sig)
    
    if imports:
        parts.append(f"  imports: {', '.join(sorted(imports))}")
    parts.extend(sigs[:MAX_SIGNATURES_SUMMARY])
    if len(sigs) > MAX_SIGNATURES_SUMMARY:
        parts.append(f"  … +{len(sigs)-MAX_SIGNATURES_SUMMARY} more")
    parts.append(f"  [{tokens_full} tokens full]")
    return "\n".join(parts)


def _basic_code_summary(full_text: str, relative_path: str, tokens_full: int) -> str:
    """Generate basic code summary using regex patterns."""
    if not full_text:
        return "[empty]"
    
    parts = [f"[Code summary: {os.path.basename(relative_path)}]"]
    pattern = (
        r"^\s*(?:(?:async\s+)?(?:public\s+|private\s+|protected\s+|static\s+)*"
        r"\b(?:class|interface|struct|enum|function|def|fn|func|module|type)\b"
        r"\s+\w+.*?[:({])"
    )
    lines = full_text.splitlines()
    sigs = []
    
    for i, line in enumerate(lines):
        if len(sigs) >= MAX_SIGNATURES_SUMMARY:
            break
        if re.search(pattern, line, re.IGNORECASE):
            sigs.append(f"  L{i+1}: {line.strip()}")
    
    if sigs:
        parts.extend(sigs)
    else:
        parts.extend(
            f"  {l.strip()}"
            for l in lines[:MAX_LINES_FALLBACK]
            if l.strip()
        )
    parts.append(f"  [{tokens_full} tokens full]")
    return "\n".join(parts)


def text_preview(full_text: Optional[str], relative_path: str, tokens_full: int) -> str:
    """Generate a text preview for non-code files."""
    if not full_text:
        return "[empty]"
    
    preview = full_text[:MAX_CHARS_TEXT_PREVIEW]
    suffix = f"\n  … [{tokens_full} tokens full]" if len(full_text) > MAX_CHARS_TEXT_PREVIEW else ""
    return f"[Preview: {os.path.basename(relative_path)}]\n{preview}{suffix}"
