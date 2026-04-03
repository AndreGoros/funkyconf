"""
funkyconf.node
~~~~~~~~~~~~~~
Core immutable Node and attr primitives.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Iterator, List, Optional, Union


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge *overlay* into *base*, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Attribute bag
# ---------------------------------------------------------------------------

class _Attributes:
    """
    An immutable mapping of keyword arguments attached to a Node.

    Created via the public ``attr(...)`` factory function.
    """

    __slots__ = ("_data",)

    def __init__(self, **kwargs: Any) -> None:
        self._data: Dict[str, Any] = dict(kwargs)

    # Allow + between two _Attributes objects
    def __add__(self, other: "_Attributes") -> "_Attributes":
        if not isinstance(other, _Attributes):
            return NotImplemented
        merged = _Attributes()
        merged._data = _deep_merge(self._data, other._data)
        return merged

    def __repr__(self) -> str:  # pragma: no cover
        return f"attr({', '.join(f'{k}={v!r}' for k, v in self._data.items())})"

    @property
    def data(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)


def attr(**kwargs: Any) -> _Attributes:
    """
    Create an immutable attribute bag.

    Example::

        db_creds = attr(user="admin", password="s3cr3t")
    """
    return _Attributes(**kwargs)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node:
    """
    An immutable configuration node.

    Parameters
    ----------
    name:
        The logical name / YAML key of this node.
    **attributes:
        Inline keyword attributes (equivalent to calling ``+ attr(...)``).
    """

    def __init__(self, name: str, **attributes: Any) -> None:
        # 'name' is intentionally a positional-only-style parameter.
        # To use "name" as an *attribute* key, use attr(name="...") instead.
        if "name" in attributes:
            raise TypeError(
                "Use attr(name=...) or node(name=...) to set a 'name' attribute. "
                "'name' is the Node's identifier, not an attribute key."
            )
        self._name: str = name
        self._attrs: Dict[str, Any] = dict(attributes)
        self._children: List["Node"] = []

    # ------------------------------------------------------------------
    # Internal copy helpers
    # ------------------------------------------------------------------

    def _clone(self) -> "Node":
        new = Node.__new__(Node)
        new._name = self._name
        new._attrs = copy.deepcopy(self._attrs)
        new._children = [child._clone() for child in self._children]
        return new

    # ------------------------------------------------------------------
    # Public read-only properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def attributes(self) -> Dict[str, Any]:
        return copy.deepcopy(self._attrs)

    @property
    def children(self) -> List["Node"]:
        return [child._clone() for child in self._children]

    # ------------------------------------------------------------------
    # Operator: Overlay  (Node + Node | Node + _Attributes)
    # ------------------------------------------------------------------

    def __add__(self, other: Union["Node", _Attributes]) -> "Node":
        """
        Merge attributes from *other* into a new Node without mutating either.

        ``Node + Node``       → merges attrs; children of *other* appended
        ``Node + attr(...)``  → merges the attr bag into this node's attrs
        """
        new = self._clone()

        if isinstance(other, _Attributes):
            new._attrs = _deep_merge(new._attrs, other._data)

        elif isinstance(other, Node):
            new._attrs = _deep_merge(new._attrs, other._attrs)
            new._children = new._children + [c._clone() for c in other._children]

        else:
            return NotImplemented

        return new

    def __radd__(self, other: Any) -> "Node":
        # Support:  attr_bag + Node  (uncommon but nice to have)
        if isinstance(other, _Attributes):
            new = self._clone()
            new._attrs = _deep_merge(other._data, new._attrs)
            return new
        return NotImplemented

    # ------------------------------------------------------------------
    # Operator: Nest  (Node >> child | Node >> [children])
    # ------------------------------------------------------------------

    def __rshift__(
        self, children: Union["Node", List["Node"]]
    ) -> "Node":
        """
        Add *children* under this node in a new immutable copy.

        ``Node >> Node``         → single child
        ``Node >> [Node, ...]``  → multiple children
        """
        new = self._clone()

        if isinstance(children, Node):
            new._children = new._children + [children._clone()]

        elif isinstance(children, list):
            for child in children:
                if not isinstance(child, Node):
                    raise TypeError(
                        f"All items in the child list must be Node instances, "
                        f"got {type(child).__name__!r}"
                    )
            new._children = new._children + [c._clone() for c in children]

        else:
            raise TypeError(
                f">> expects a Node or list[Node], got {type(children).__name__!r}"
            )

        return new

    # ------------------------------------------------------------------
    # Callable: makes Node act as a Blueprint factory
    # ------------------------------------------------------------------

    def __call__(self, name: Optional[str] = None, **kwargs: Any) -> "Node":
        """
        Return a new Node with an optional new name and extra attributes.

        This makes a bare Node work as a *Blueprint*::

            base_service = Node("service") + attr(restart="always")
            web = base_service(name="web_app") + attr(image="nginx:1.25")
        """
        new = self._clone()
        if name is not None:
            new._name = name
        if kwargs:
            new._attrs = _deep_merge(new._attrs, kwargs)
        return new

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, format: str = "dict") -> Any:
        """
        Recursively render this node to a Python dict, YAML string, or JSON string.

        Parameters
        ----------
        format:
            ``"dict"`` (default), ``"yaml"``, or ``"json"``.
        """
        raw = self._to_dict()

        if format == "dict":
            return raw

        if format == "yaml":
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "PyYAML is required for YAML rendering. "
                    "Install it with: pip install pyyaml"
                ) from exc
            return yaml.dump(raw, default_flow_style=False, allow_unicode=True)

        if format == "json":
            import json
            return json.dumps(raw, indent=2, ensure_ascii=False)

        raise ValueError(f"Unknown format {format!r}. Use 'dict', 'yaml', or 'json'.")

    def _to_dict(self) -> Dict[str, Any]:
        """Convert this node (and its subtree) to a plain dict."""
        body: Dict[str, Any] = copy.deepcopy(self._attrs)

        if self._children:
            # Each child._to_dict() returns {child.name: {...}}.
            # We want to merge {child.name: content} into body directly.
            child_map: Dict[str, Any] = {}
            for child in self._children:
                child_content = child._to_dict()[child.name]  # unwrap child's own name
                if child.name in child_map:
                    existing = child_map[child.name]
                    if isinstance(existing, list):
                        existing.append(child_content)
                    else:
                        child_map[child.name] = [existing, child_content]
                else:
                    child_map[child.name] = child_content

            body = _deep_merge(body, child_map)

        return {self._name: body} if self._name else body

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, schema: "Schema") -> "ValidationResult":
        """Validate this node against a *Schema*."""
        return schema.validate(self)

    # ------------------------------------------------------------------
    # Dunder utilities
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        child_names = [c.name for c in self._children]
        return (
            f"Node({self._name!r}, attrs={list(self._attrs.keys())}, "
            f"children={child_names})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self._to_dict() == other._to_dict()
