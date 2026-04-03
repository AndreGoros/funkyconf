# Documento de diseño — `funkyconf`

## Problema

Los archivos de configuración manuales (YAML, JSON, TOML) son frágiles por naturaleza: se copian bloques enteros, se repiten valores, no existe composición real y cualquier refactor implica editar texto plano sin garantías de consistencia. El resultado es infraestructura difícil de razonar, imposible de testear unitariamente y propensa a errores silenciosos.

`funkyconf` elimina esa fragilidad reemplazando los archivos estáticos por un **lenguaje de dominio específico (DSL) inmutable** que permite construir configuraciones complejas como composición de funciones puras, exportando el resultado validado a YAML o JSON.

---

## Quantum

Construir una estructura de configuración arbitrariamente compleja mediante la **composición de bloques inmutables** y exportarla a un archivo YAML o JSON validado:

```python
stack = Node("docker-compose") >> [
    base_service(name="web")  + attr(image="nginx:1.25"),
    base_service(name="db")   + attr(image="postgres:16"),
]
export(stack, "deploy.yml")
```

---

## Vocabulario

### Sustantivos

| Sustantivo | En Python | Descripción |
|------------|-----------|-------------|
| Node | clase `Node` | Bloque de construcción básico e inmutable. Representa una sección del archivo de configuración. Su nombre se convierte en la clave YAML/JSON. |
| Attribute | función `attr(**kwargs)` | Bolsa inmutable de pares clave-valor que reside dentro de un `Node`. Se fusiona, nunca se muta. |
| Blueprint | `Node` callable o `@blueprint` | Función pura que recibe parámetros y retorna un `Node` preconfigurado y reutilizable. |
| Schema | clase `Schema` | Conjunto de reglas declarativas (tipos, choices, predicados, regex) que validan la estructura de un `Node`. |
| Tree | clase `Tree` | Envoltorio de conveniencia sobre el `Node` raíz que expone métodos `to_yaml()`, `to_json()`, `to_dict()` y `to_file()`. |
| ValidationResult | clase `ValidationResult` | Resultado de una validación: contiene `valid: bool` y `errors: list[str]`. Evaluable como booleano. |

### Verbos

| Verbo | En Python | Descripción |
|-------|-----------|-------------|
| Overlay | operador `+` (`__add__`) | Fusiona atributos de dos `Node` o de un `Node` y un `attr()` en una nueva instancia, sin mutar las originales. |
| Nest | operador `>>` (`__rshift__`) | Convierte un `Node` en hijo de otro, definiendo la jerarquía del árbol. Acepta un `Node` o una lista de `Node`. |
| Render | método `.render(format=)` | Recorre el árbol de forma recursiva y genera un `dict`, string YAML o string JSON. |
| Validate | método `.validate(schema)` | Evalúa si la composición actual del `Node` cumple con las reglas del `Schema`. Retorna un `ValidationResult`. |
| Export | función `export(node, filename)` | Toma el resultado del renderizado y lo escribe en disco. El formato se infiere de la extensión (`.yml`, `.json`). |
| Build | función `build(node)` | Envuelve el `Node` raíz en un `Tree` para acceso multi-formato. |
| Mostrar ayuda | help(topic=None) | Imprime el índice de todos los temas o el detalle de uno: Node, attr, +, >>, blueprint, Schema, validate, render, export, build, Tree. |

---

## Dream usage

```python
from funkyconf import Node, attr, Schema, blueprint, export

# ── 1. Definir reglas de validación ─────────────────────────────────────────
service_schema = (
    Schema("service")
    .require("image",   str)
    .require("restart", str, choices=["always", "unless-stopped", "no"])
    .optional("ports",  list)
    .check(lambda n: (
        "evita :latest en producción"
        if n.attributes.get("image", "").endswith(":latest")
        else None
    ))
)

# ── 2. Crear blueprints reutilizables ────────────────────────────────────────
@blueprint
def web_service(image: str, port: int = 80) -> Node:
    return (
        Node("service")
        + attr(image=image, ports=[port], restart="always", networks=["web"])
    )

@blueprint
def db_service(engine: str, version: str, password: str) -> Node:
    return (
        Node("service")
        + attr(
            image=f"{engine}:{version}",
            restart="unless-stopped",
            environment={"DB_PASSWORD": password},
        )
    )

# ── 3. Componer el stack con operadores ──────────────────────────────────────
stack = Node("docker-compose", version="3.9") >> [
    web_service(image="nginx:1.25", port=80),
    web_service(image="myapp:2.1",  port=8000),
    db_service(engine="postgres", version="16", password="s3cr3t"),
]

# ── 4. Validar antes de exportar ─────────────────────────────────────────────
for child in stack.children:
    child.validate(service_schema).raise_if_invalid()

# ── 5. Renderizar y exportar ─────────────────────────────────────────────────
print(stack.render(format="yaml"))
export(stack, filename="docker-compose.yml")

# ── 6.Consultas respecto al funcionamiento ─────────────────────────────────────────────────
help()          # índice de todos los temas
help("Node")    # detalle de Node
help(">>")      # operador Nest
help("export")  # función export
```

Salida generada:

```yaml
docker-compose:
  service:
  - image: nginx:1.25
    networks: [web]
    ports: [80]
    restart: always
  - image: myapp:2.1
    networks: [web]
    ports: [8000]
    restart: always
  - environment:
      DB_PASSWORD: s3cr3t
    image: postgres:16
    restart: unless-stopped
  version: '3.9'
```
