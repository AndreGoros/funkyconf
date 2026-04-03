"""
funkyconf.tree
~~~~~~~~~~~~~~
Tree: a thin wrapper around the root Node that adds
pretty-printing and multi-format export convenience.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .node import Node


class Tree:
    """
    The rendered, hierarchical view of a :class:`~funkyconf.node.Node` tree.

    You don't normally create a ``Tree`` directly – it is returned by
    :func:`funkyconf.build`.

    Example::

        from funkyconf import build

        tree = build(root_node)
        print(tree.to_yaml())
        tree.to_file("deploy.yml")
    """

    def __init__(self, root: "Node") -> None:
        self._root = root

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return the full structure as a plain Python dict."""
        return self._root.render(format="dict")

    def to_yaml(self) -> str:
        """Return a YAML string of the full tree."""
        return self._root.render(format="yaml")

    def to_json(self) -> str:
        """Return a JSON string of the full tree."""
        return self._root.render(format="json")

    # ------------------------------------------------------------------
    # File export
    # ------------------------------------------------------------------

    def to_file(self, filename: str) -> None:
        """
        Write the tree to *filename*.

        The format is inferred from the file extension:

        * ``*.yml`` / ``*.yaml`` → YAML
        * ``*.json`` → JSON
        * anything else → YAML (default)
        """
        from .export import export as _export
        _export(self._root, filename=filename)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return f"Tree(root={self._root.name!r})"

    def __str__(self) -> str:
        return self.to_yaml()
