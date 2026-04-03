"""
funkyconf
~~~~~~~~~

A composable, immutable DSL for building complex configuration files
(YAML/JSON) as pure-function compositions — no more fragile manual configs.

Basic usage::

    from funkyconf import Node, attr, export

    # Node("key") → YAML key.  Use attr() for attribute values.
    base_service = Node("service") + attr(restart="always", networks=["frontend"])
    db_creds = attr(user="admin", password="safe_password_123")

    stack = Node("docker-compose") >> [
        base_service + attr(svc="web_app", image="nginx:1.25",  ports=[80]),
        base_service + db_creds + attr(svc="database", image="postgres:16"),
    ]

    print(stack.render(format="yaml"))
    export(stack, filename="deploy.yml")
"""

from .node import Node, attr
from .schema import Schema, ValidationResult, ValidationError
from .tree import Tree
from .export import export
from .blueprint import blueprint
from ._build import build
from .help import help  # noqa: A001

__all__ = [
    "Node",
    "attr",
    "Schema",
    "ValidationResult",
    "ValidationError",
    "Tree",
    "export",
    "blueprint",
    "build",
    "help",
]

__version__ = "0.1.0"
__author__ = "funkyconf contributors"
