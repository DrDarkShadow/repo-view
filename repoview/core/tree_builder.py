"""Directory tree building utilities."""

from typing import Any, Dict, List


def build_tree(entries: List[Any]) -> str:
    """Build a visual directory tree from file entries."""
    node: Dict[str, Any] = {}
    for e in entries:
        parts = e.relative_path.rstrip("/").split("/")
        cur = node
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if not is_last or e.relative_path.endswith("/"):
                cur = cur.setdefault(part + "/", {})
            else:
                cur[part] = None

    def _render(n: dict, prefix: str = "") -> str:
        lines = []
        items = sorted(n.items())
        for i, (name, children) in enumerate(items):
            last = i == len(items) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}")
            if children is not None:
                lines.append(_render(children, prefix + ("    " if last else "│   ")))
        return "\n".join(filter(None, lines))

    return _render(node)
