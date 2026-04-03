"""
funkyconf.help
~~~~~~~~~~~~~~
Función help() estilo bash: muestra qué hace cada pieza del DSL
con una descripción y un ejemplo mínimo ejecutable.
"""
from __future__ import annotations

# ── colores ANSI (se desactivan si la terminal no los soporta) ──────────────
import sys
import os

_USE_COLOR = (
    hasattr(sys.stdout, "isatty")
    and sys.stdout.isatty()
    and os.name != "nt"  # Windows CMD no soporta ANSI por defecto
    or os.environ.get("FORCE_COLOR")
)

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

BOLD  = lambda t: _c("1",    t)
DIM   = lambda t: _c("2",    t)
CYAN  = lambda t: _c("96",   t)
GREEN = lambda t: _c("92",   t)
YELLOW= lambda t: _c("93",   t)
BLUE  = lambda t: _c("94",   t)
MAG   = lambda t: _c("95",   t)
WHITE = lambda t: _c("97",   t)

# ── catálogo de ayuda ────────────────────────────────────────────────────────

_TOPICS: dict[str, dict] = {

    "Node": {
        "tipo": "clase",
        "firma": "Node(name, **attributes)",
        "desc": (
            "Bloque de construcción inmutable del DSL.\n"
            "  • name       → clave YAML/JSON del bloque (ej. 'service', 'database').\n"
            "  • **attributes → atributos inline (equivalente a + attr(...)).\n"
            "  Toda operación devuelve una NUEVA instancia; el original nunca muta."
        ),
        "ejemplo": """\
from funkyconf import Node, attr

svc = Node("service", restart="always")
web = svc + attr(image="nginx:1.25", ports=[80])

print(web.render(format="yaml"))
# service:
#   image: nginx:1.25
#   ports: [80]
#   restart: always""",
    },

    "attr": {
        "tipo": "función",
        "firma": "attr(**kwargs) → _Attributes",
        "desc": (
            "Crea una bolsa de atributos inmutable.\n"
            "  Se combina con Node mediante el operador +.\n"
            "  También puede combinarse con otra bolsa attr + attr."
        ),
        "ejemplo": """\
from funkyconf import attr

base = attr(restart="always", networks=["web"])
extra = attr(image="nginx:1.25", ports=[80])
merged = base + extra

print(merged.data)
# {'restart': 'always', 'networks': ['web'], 'image': 'nginx:1.25', 'ports': [80]}""",
    },

    "+": {
        "tipo": "operador  (Overlay)",
        "firma": "Node + attr(...)  |  Node + Node",
        "desc": (
            "Fusiona atributos en una nueva instancia sin mutar las originales.\n"
            "  Node + attr  → añade/sobreescribe atributos del attr en el nodo.\n"
            "  Node + Node  → fusiona atributos; los hijos del 2.° se agregan al 1.°."
        ),
        "ejemplo": """\
from funkyconf import Node, attr

base = Node("svc", restart="always")
web  = base + attr(image="nginx:1.25")   # base no cambia

print(base.attributes)   # {'restart': 'always'}
print(web.attributes)    # {'restart': 'always', 'image': 'nginx:1.25'}""",
    },

    ">>": {
        "tipo": "operador  (Nest)",
        "firma": "Node >> Node  |  Node >> [Node, ...]",
        "desc": (
            "Anida un hijo (o lista de hijos) bajo el nodo padre.\n"
            "  El padre original no se modifica.\n"
            "  Hijos con el mismo nombre se convierten en lista YAML automáticamente."
        ),
        "ejemplo": """\
from funkyconf import Node, attr

stack = Node("compose") >> [
    Node("service") + attr(image="nginx"),
    Node("service") + attr(image="postgres"),
]

print(stack.render(format="yaml"))
# compose:
#   service:
#   - image: nginx
#   - image: postgres""",
    },

    "blueprint": {
        "tipo": "decorador",
        "firma": "@blueprint",
        "desc": (
            "Marca una función como Blueprint: una fábrica pura que recibe\n"
            "  parámetros y devuelve un Node preconfigurado.\n"
            "  Añade el flag .is_blueprint = True a la función."
        ),
        "ejemplo": """\
from funkyconf import Node, attr, blueprint

@blueprint
def web_service(image: str, port: int = 80) -> Node:
    return Node("service") + attr(image=image, ports=[port], restart="always")

nginx = web_service(image="nginx:1.25", port=8080)
print(nginx.attributes)
# {'image': 'nginx:1.25', 'ports': [8080], 'restart': 'always'}""",
    },

    "Schema": {
        "tipo": "clase",
        "firma": "Schema(name=None)",
        "desc": (
            "Define reglas de validación para un Node. API fluida:\n"
            "  .require(key, type, *, choices, predicate, pattern)\n"
            "  .optional(key, type, *, choices, predicate, pattern)\n"
            "  .check(fn)  → fn(node) devuelve None si ok, o str de error."
        ),
        "ejemplo": """\
from funkyconf import Node, attr, Schema

schema = (
    Schema("service")
    .require("image",   str)
    .require("restart", str, choices=["always", "unless-stopped", "no"])
    .optional("ports",  list)
    .check(lambda n: "evita :latest" if ":latest" in n.attributes.get("image","") else None)
)

ok  = Node("svc") + attr(image="nginx:1.25", restart="always")
bad = Node("svc") + attr(restart="maybe")

print(ok.validate(schema).valid)      # True
result = bad.validate(schema)
print(result.valid)                   # False
print(result.errors)
# ["[svc] Missing required attribute: 'image'",
#  "[svc] Attribute 'restart' must be one of ..."]""",
    },

    "validate": {
        "tipo": "método",
        "firma": "node.validate(schema) → ValidationResult",
        "desc": (
            "Evalúa el Node contra un Schema.\n"
            "  Retorna ValidationResult con .valid (bool) y .errors (list[str]).\n"
            "  Llama .raise_if_invalid() para lanzar ValidationError si falla."
        ),
        "ejemplo": """\
from funkyconf import Node, attr, Schema, ValidationError

schema = Schema().require("image", str)
node   = Node("svc", image="nginx:1.25")

result = node.validate(schema)
print(result.valid)    # True
print(bool(result))    # True  (ValidationResult es truthy/falsy)

bad = Node("svc")
try:
    bad.validate(schema).raise_if_invalid()
except ValidationError as e:
    print(e)   # [svc] Missing required attribute: 'image'""",
    },

    "render": {
        "tipo": "método",
        "firma": 'node.render(format="dict") → dict | str',
        "desc": (
            "Recorre el árbol y genera la representación final.\n"
            '  format="dict"  → Python dict  (default)\n'
            '  format="yaml"  → string YAML  (requiere pyyaml)\n'
            '  format="json"  → string JSON'
        ),
        "ejemplo": """\
from funkyconf import Node, attr
import json

cfg = Node("server") + attr(host="localhost", port=8080)

print(cfg.render())                    # {'server': {'host': 'localhost', 'port': 8080}}
print(cfg.render(format="json"))       # {"server": {"host": "localhost", "port": 8080}}
print(cfg.render(format="yaml"))
# server:
#   host: localhost
#   port: 8080""",
    },

    "export": {
        "tipo": "función",
        "firma": "export(source, filename, *, format='auto', encoding='utf-8') → str",
        "desc": (
            "Serializa un Node o Tree y lo escribe en disco.\n"
            "  El formato se infiere de la extensión (.yml/.yaml → YAML, .json → JSON).\n"
            "  Crea directorios intermedios automáticamente.\n"
            "  Retorna la ruta absoluta del archivo escrito."
        ),
        "ejemplo": """\
from funkyconf import Node, attr, export

cfg = Node("app") + attr(debug=False, port=3000)

path = export(cfg, "config/app.yml")
print(path)   # /ruta/absoluta/config/app.yml
# config/app.yml contiene:
# app:
#   debug: false
#   port: 3000

export(cfg, "config/app.json")        # JSON por extensión
export(cfg, "out.txt", format="yaml") # formato explícito""",
    },

    "build": {
        "tipo": "función",
        "firma": "build(root) → Tree",
        "desc": (
            "Envuelve el Node raíz en un Tree para acceso multi-formato.\n"
            "  Tree expone: .to_dict(), .to_yaml(), .to_json(), .to_file(path).\n"
            "  str(tree) imprime el YAML del árbol completo."
        ),
        "ejemplo": """\
from funkyconf import Node, attr, build

root = Node("config") >> [
    Node("server",   host="0.0.0.0", port=8080),
    Node("database", host="db",      port=5432),
]

tree = build(root)
print(tree.to_yaml())
# config:
#   server:   {host: 0.0.0.0, port: 8080}
#   database: {host: db,      port: 5432}

tree.to_file("config.yml")   # escribe en disco""",
    },

    "Tree": {
        "tipo": "clase",
        "firma": "Tree(root)  —  normalmente obtenida via build()",
        "desc": (
            "Representación jerárquica final del árbol de Nodes.\n"
            "  .to_dict()       → Python dict\n"
            "  .to_yaml()       → string YAML\n"
            "  .to_json()       → string JSON\n"
            "  .to_file(path)   → escribe en disco (formato por extensión)"
        ),
        "ejemplo": """\
from funkyconf import Node, build

tree = build(Node("cfg", version="1.0", debug=False))

import json
data = json.loads(tree.to_json())
print(data)   # {'cfg': {'version': '1.0', 'debug': False}}

print(str(tree))
# cfg:
#   debug: false
#   version: '1.0'""",
    },
}

# ── función pública ──────────────────────────────────────────────────────────

def help(topic: str | None = None) -> None:  # noqa: A001  (sombrea builtin intencionalmente)
    """
    Muestra ayuda sobre funkyconf, estilo man-page / bash help.

    Uso::

        from funkyconf import help
        help()           # índice de todos los temas
        help("Node")     # ayuda detallada de Node
        help(">>")       # operador Nest
        help("export")   # función export
    """
    if topic is None:
        _print_index()
    else:
        key = _resolve(topic)
        if key is None:
            available = ", ".join(sorted(_TOPICS))
            print(f"\n  Tema {topic!r} no encontrado. Disponibles: {available}\n")
        else:
            _print_topic(key, _TOPICS[key])


def _resolve(topic: str) -> str | None:
    """Búsqueda case-insensitive y con alias."""
    if topic in _TOPICS:
        return topic
    lower = topic.lower()
    for key in _TOPICS:
        if key.lower() == lower:
            return key
    return None


def _print_index() -> None:
    W = 60
    print()
    print(BOLD(WHITE("─" * W)))
    print(BOLD(WHITE(f"  funkyconf {_version()}  — referencia rápida")))
    print(BOLD(WHITE("─" * W)))
    print(f"\n  {DIM('Uso:')}  help(\"<tema>\")   ej. help(\"Node\"), help(\">>\")\n")

    groups = [
        ("Bloques principales",  ["Node", "attr"]),
        ("Operadores",           ["+", ">>"]),
        ("Blueprints",           ["blueprint"]),
        ("Validación",           ["Schema", "validate"]),
        ("Salida",               ["render", "export", "build", "Tree"]),
    ]

    for group_name, keys in groups:
        print(f"  {CYAN(BOLD(group_name))}")
        for key in keys:
            info = _TOPICS[key]
            tipo = DIM(f"[{info['tipo']}]")
            firma = YELLOW(info["firma"])
            print(f"    {GREEN(key):<18} {tipo:<22} {firma}")
        print()

    print(BOLD(WHITE("─" * W)))
    print()


def _print_topic(key: str, info: dict) -> None:
    W = 64
    print()
    print(BOLD(WHITE("─" * W)))
    print(f"  {BOLD(GREEN(key))}  {DIM('[' + info['tipo'] + ']')}")
    print(BOLD(WHITE("─" * W)))

    print(f"\n  {CYAN(BOLD('Firma'))}")
    print(f"    {YELLOW(info['firma'])}")

    print(f"\n  {CYAN(BOLD('Descripción'))}")
    for line in info["desc"].splitlines():
        print(f"    {line}")

    print(f"\n  {CYAN(BOLD('Ejemplo'))}")
    for line in info["ejemplo"].splitlines():
        if line.startswith("#"):
            print(f"    {DIM(line)}")
        else:
            print(f"    {MAG(line)}" if line.startswith("from ") or line.startswith("import ") else f"    {line}")

    print()
    print(BOLD(WHITE("─" * W)))
    print()


def _version() -> str:
    try:
        from funkyconf import __version__
        return f"v{__version__}"
    except Exception:
        return ""
