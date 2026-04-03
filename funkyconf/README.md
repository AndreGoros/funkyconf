# funkyconf 🎛️

> Build complex YAML/JSON configs as **pure-function compositions** — no more fragile manual files.

```python
from funkyconf import Node, attr, export

base_service = Node("service") + attr(restart="always", networks=["frontend"])
db_creds     = attr(user="admin", password="safe_password_123")

stack = Node("docker-compose") >> [
    base_service + attr(svc="web_app",  image="nginx:1.25",  ports=[80]),
    base_service + db_creds + attr(svc="database", image="postgres:16"),
]

print(stack.render(format="yaml"))
export(stack, filename="deploy.yml")
```

Output:

```yaml
docker-compose:
  service:
  - image: nginx:1.25
    networks:
    - frontend
    ports:
    - 80
    restart: always
    svc: web_app
  - image: postgres:16
    networks:
    - frontend
    password: safe_password_123
    restart: always
    svc: database
    user: admin
```

---

## Why funkyconf?

| Pain point | funkyconf solution |
|---|---|
| Copy-paste YAML blocks | Reusable `Node` blueprints |
| Mutation bugs in big configs | 100% immutable operations |
| No type safety | `Schema` validation with predicates |
| Verbose merge logic | `+` and `>>` operators |
| Untested config logic | Pure functions → unit-testable |

---

## Installation

```bash
# Minimal (JSON only, no extra deps)
pip install funkyconf

# With YAML support
pip install "funkyconf[yaml]"

# Development (tests + YAML)
pip install "funkyconf[dev]"
```

---

## Core concepts

### `Node` — the immutable building block

```python
from funkyconf import Node, attr

service = Node("service", restart="always")
```

> **Important:** `Node("key")` sets the **YAML key** of the block, not an attribute.
> To store a value under the attribute key `"name"`, use `attr(name=...)`.

Every operation returns a **new** Node — originals are never mutated.

### `attr(...)` — lightweight attribute bags

```python
creds = attr(user="admin", password="secret")
```

### `+` Overlay — merge attributes

```python
base  = Node("service") + attr(restart="always")
nginx = base + attr(image="nginx:1.25", ports=[80])
# `base` is unchanged ✓
```

### `>>` Nest — build hierarchies

```python
compose = Node("docker-compose") >> [
    Node("web")      + attr(image="nginx"),
    Node("database") + attr(image="postgres"),
]
```

Children with the **same node name** are automatically collected into a YAML list.

### Blueprints — parametric factories

**Style A — callable Node** (`node(name="new_key")` renames the YAML key):

```python
base_service = Node("service") + attr(restart="always")
web = base_service(name="web_app") + attr(image="nginx:1.25")
# Produces:  web_app: {restart: always, image: nginx:1.25}
```

**Style B — `@blueprint` decorator:**

```python
from funkyconf import blueprint

@blueprint
def web_service(image: str, port: int = 80) -> Node:
    return Node("service") + attr(image=image, ports=[port], restart="always")

nginx = web_service(image="nginx:1.25", port=8080)
```

### `Schema` — declarative validation

```python
from funkyconf import Schema

svc_schema = (
    Schema("service")
    .require("image",   str)
    .require("restart", str, choices=["always", "unless-stopped", "no"])
    .optional("ports",  list)
    .check(lambda n: (
        "avoid :latest in production!"
        if ":latest" in n.attributes.get("image", "")
        else None
    ))
)

result = nginx.validate(svc_schema)
result.raise_if_invalid()   # raises ValidationError listing all problems
```

### `render()` — export to dict / YAML / JSON

```python
stack.render()              # → Python dict
stack.render(format="yaml") # → YAML string
stack.render(format="json") # → JSON string
```

### `export()` — write to disk

```python
from funkyconf import export

export(stack, filename="deploy.yml")            # format from extension
export(stack, filename="out.json")
export(stack, filename="cfg.txt", format="yaml") # explicit format
```

### `Tree` + `build()` — convenience wrapper

```python
from funkyconf import build

tree = build(stack)
tree.to_yaml()           # YAML string
tree.to_json()           # JSON string
tree.to_dict()           # Python dict
tree.to_file("cfg.yml")  # write to disk
print(tree)              # prints YAML
```

---

## Full Docker Compose example

```python
from funkyconf import Node, attr, Schema, blueprint, export

# ── Schemas ─────────────────────────────────────────────────────────────────
service_schema = (
    Schema("service")
    .require("image",   str)
    .require("restart", str, choices=["always", "unless-stopped", "no"])
    .optional("ports",  list)
    .optional("environment", dict)
    .check(lambda n: (
        "avoid :latest in production!"
        if n.attributes.get("image", "").endswith(":latest")
        else None
    ))
)

# ── Blueprints ───────────────────────────────────────────────────────────────
@blueprint
def web_service(image: str, port: int = 80) -> Node:
    return (
        Node("service")
        + attr(image=image, ports=[port], restart="always", networks=["frontend"])
    )

@blueprint
def db_service(image: str, env: dict) -> Node:
    return (
        Node("service")
        + attr(image=image, restart="unless-stopped",
               networks=["backend"], environment=env)
    )

# ── Composition ──────────────────────────────────────────────────────────────
stack = Node("docker-compose", version="3.9") >> [
    web_service(image="nginx:1.25",  port=80),
    web_service(image="myapp:2.0.1", port=8000),
    db_service(
        image="postgres:16",
        env={"POSTGRES_USER": "admin", "POSTGRES_PASSWORD": "s3cr3t"},
    ),
]

# ── Validate every service ───────────────────────────────────────────────────
for child in stack.children:
    child.validate(service_schema).raise_if_invalid()

# ── Export ───────────────────────────────────────────────────────────────────
export(stack, "docker-compose.yml")
print(stack.render(format="yaml"))
```

---

## Key design decisions

| Decision | Rationale |
|---|---|
| `Node("key")` is the YAML key, not a value | Maps 1-to-1 to YAML structure; no magic |
| All ops return new instances | Blueprints safe to share across scopes |
| `+` merges attrs, `>>` nests | Two orthogonal axes of composition |
| `Schema` is a separate object | Validation is optional and composable |
| Zero hard dependencies | JSON works out of the box; YAML is opt-in |

---

## Running the tests

```bash
pip install "funkyconf[dev]"
pytest
```

---

## License

MIT
