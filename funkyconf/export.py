"""
funkyconf.export
~~~~~~~~~~~~~~~~
Standalone export() function: takes a rendered Node (or Tree) and
writes it to disk in YAML or JSON format.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .node import Node
    from .tree import Tree


def export(
    source: Union["Node", "Tree"],
    filename: str,
    *,
    format: str = "auto",
    encoding: str = "utf-8",
) -> str:
    """
    Serialize *source* and write the output to *filename*.

    Parameters
    ----------
    source:
        A :class:`~funkyconf.node.Node` or :class:`~funkyconf.tree.Tree`.
    filename:
        Destination path.  Parent directories are created automatically.
    format:
        ``"auto"`` (default) infers from the file extension.
        Explicit values: ``"yaml"``, ``"json"``.
    encoding:
        File encoding (default ``"utf-8"``).

    Returns
    -------
    str
        The absolute path of the file that was written.
    """
    # Resolve actual Node from Tree wrapper
    from .tree import Tree
    if isinstance(source, Tree):
        node = source._root
    else:
        node = source  # type: ignore[assignment]

    # Infer format
    resolved_format = _resolve_format(filename, format)

    content = node.render(format=resolved_format)

    # Ensure parent directories exist
    parent = os.path.dirname(os.path.abspath(filename))
    os.makedirs(parent, exist_ok=True)

    with open(filename, "w", encoding=encoding) as fh:
        fh.write(content)

    return os.path.abspath(filename)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_format(filename: str, hint: str) -> str:
    if hint != "auto":
        _validate_format(hint)
        return hint

    ext = os.path.splitext(filename)[1].lower()
    if ext in {".yml", ".yaml"}:
        return "yaml"
    if ext == ".json":
        return "json"
    # Default to YAML for unknown extensions
    return "yaml"


def _validate_format(fmt: str) -> None:
    allowed = {"yaml", "json"}
    if fmt not in allowed:
        raise ValueError(f"format must be one of {sorted(allowed)!r}, got {fmt!r}")
