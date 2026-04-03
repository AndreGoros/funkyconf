"""
funkyconf._build
~~~~~~~~~~~~~~~~
Convenience build() function that wraps a root Node in a Tree.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node
    from .tree import Tree


def build(root: "Node") -> "Tree":
    """
    Wrap *root* in a :class:`~funkyconf.tree.Tree` for multi-format export.

    Example::

        from funkyconf import Node, build

        stack = Node("stack") >> Node("web")
        tree = build(stack)
        print(tree.to_yaml())
    """
    from .tree import Tree
    return Tree(root)
