"""
funkyconf.blueprint
~~~~~~~~~~~~~~~~~~~
The ``blueprint`` decorator turns any function that returns a Node
into a first-class Blueprint factory, adding introspection helpers.
"""
from __future__ import annotations

import functools
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node


def blueprint(fn: Callable[..., "Node"]) -> Callable[..., "Node"]:
    """
    Decorator that marks a function as a *Blueprint*.

    A Blueprint is a pure function that accepts parameters and returns
    a pre-configured :class:`~funkyconf.node.Node`.  The decorator is
    lightweight – it simply preserves metadata and adds a ``is_blueprint``
    flag for introspection.

    Example::

        from funkyconf import Node, attr, blueprint

        @blueprint
        def web_service(image: str, port: int = 80) -> Node:
            return (
                Node("service")
                + attr(image=image, ports=[port], restart="always")
            )

        nginx = web_service(image="nginx:1.25", port=8080)
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> "Node":
        result = fn(*args, **kwargs)
        # Duck-type check to catch accidental wrong return types early
        if not hasattr(result, "_to_dict"):
            raise TypeError(
                f"Blueprint {fn.__name__!r} must return a Node, "
                f"got {type(result).__name__!r}"
            )
        return result

    wrapper.is_blueprint = True  # type: ignore[attr-defined]
    return wrapper
