"""
demo.py — Demostración completa de funkyconf
============================================
Ejecutar con:  python3 demo.py
"""
import sys
import json
import os
import tempfile

from funkyconf import Node, attr, Schema, Tree, ValidationError, blueprint, build, export

# ─── Colores para la terminal ────────────────────────────────────────────────
R  = "\033[91m"   # rojo
G  = "\033[92m"   # verde
Y  = "\033[93m"   # amarillo
B  = "\033[94m"   # azul
M  = "\033[95m"   # magenta
C  = "\033[96m"   # cyan
W  = "\033[97m"   # blanco brillante
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

def header(title):
    width = 60
    print(f"\n{B}{'━' * width}{RST}")
    print(f"{BOLD}{W}  {title}{RST}")
    print(f"{B}{'━' * width}{RST}")

def section(title):
    print(f"\n{C}{BOLD}▶ {title}{RST}")

def ok(msg):
    print(f"  {G}✓{RST}  {msg}")

def info(label, value):
    print(f"  {Y}{label:<20}{RST} {DIM}{value}{RST}")

def show(label, content):
    print(f"\n  {M}{BOLD}{label}:{RST}")
    for line in str(content).strip().splitlines():
        print(f"  {DIM}│{RST}  {line}")

def fail(msg):
    print(f"  {R}✗  {msg}{RST}")

ERRORS = []

def check(condition, msg):
    if condition:
        ok(msg)
    else:
        fail(msg)
        ERRORS.append(msg)


# ════════════════════════════════════════════════════════════════════════════
header("funkyconf — Demo completo")
print(f"\n  {DIM}Todos los conceptos del DSL ejecutados en vivo.{RST}")
# ════════════════════════════════════════════════════════════════════════════


# ────────────────────────────────────────────────────────────────────────────
header("1  · attr() — bolsas de atributos inmutables")
# ────────────────────────────────────────────────────────────────────────────

section("Creación básica")
creds = attr(user="admin", password="s3cr3t", port=5432)
info("creds.data", creds.data)
check(creds.data["user"] == "admin", "attr guarda el valor 'user' correctamente")
check(creds.data["port"] == 5432,    "attr guarda enteros")

section("Inmutabilidad — modificar .data no afecta el original")
d = creds.data
d["user"] = "HACKED"
check(creds.data["user"] == "admin", "original no mutado tras editar la copia")

section("Overlay: attr + attr")
extra  = attr(ssl=True, timeout=30)
merged = creds + extra
info("creds + extra", merged.data)
check(merged.data["ssl"] is True,          "+ fusiona claves nuevas")
check(merged.data["user"] == "admin",      "+ conserva claves existentes")
check(creds.data.get("ssl") is None,       "original sin ssl (no mutado)")


# ────────────────────────────────────────────────────────────────────────────
header("2  · Node — bloque de construcción inmutable")
# ────────────────────────────────────────────────────────────────────────────

section("Creación")
svc = Node("service", restart="always", replicas=2)
info("svc.name",       svc.name)
info("svc.attributes", svc.attributes)
check(svc.name == "service",            "Node.name es la clave YAML")
check(svc.attributes["replicas"] == 2, "atributos inline guardados")

section("Node + attr  (Overlay)")
nginx = svc + attr(image="nginx:1.25", ports=[80, 443])
info("nginx.attributes", nginx.attributes)
check("image" in nginx.attributes,      "+ agrega clave nueva")
check("restart" in nginx.attributes,    "+ conserva clave original")
check("image" not in svc.attributes,    "original svc no mutado")

section("Node + Node  (fusión de dos nodos)")
base_a = Node("cfg", debug=False, workers=4)
base_b = Node("cfg", workers=8, log_level="INFO")
merged = base_a + base_b
info("merged.attributes", merged.attributes)
check(merged.attributes["workers"] == 8,           "segundo nodo sobreescribe workers")
check(merged.attributes["debug"] is False,          "primera clave conservada")
check(merged.attributes["log_level"] == "INFO",     "nueva clave del segundo nodo")

section("Node callable  (Blueprint de nombre)")
base_service = Node("service") + attr(restart="always", networks=["web"])
web = base_service(name="web_app") + attr(image="nginx:1.25")
db  = base_service(name="database") + attr(image="postgres:16")
info("web.name", web.name)
info("db.name",  db.name)
check(web.name == "web_app",                   "callable renombra el nodo")
check(db.name == "database",                   "callable renombra de forma independiente")
check(base_service.name == "service",          "original no mutado")
check("image" not in base_service.attributes,  "base sin image (inmutable)")


# ────────────────────────────────────────────────────────────────────────────
header("3  · Nest (>>) — jerarquía")
# ────────────────────────────────────────────────────────────────────────────

section("Hijo único")
parent = Node("root") >> Node("child", value=42)
check(len(parent.children) == 1,          "un hijo")
check(parent.children[0].name == "child", "nombre del hijo correcto")

section("Lista de hijos")
root = Node("cluster") >> [
    Node("node_a", role="master"),
    Node("node_b", role="worker"),
    Node("node_c", role="worker"),
]
check(len(root.children) == 3, "tres hijos")

section("Inmutabilidad del nest")
base = Node("parent")
with_child = base >> Node("child")
check(len(base.children) == 0,       "base sin hijos tras >>")
check(len(with_child.children) == 1, "with_child tiene un hijo")

section("Cadenas de jerarquía profunda")
deep = (
    Node("app")
    >> (Node("backend") >> Node("db", engine="postgres"))
)
rendered_deep = deep.render()
check("app" in rendered_deep,                          "nivel 1 presente")
check("backend" in rendered_deep["app"],               "nivel 2 presente")
check("db" in rendered_deep["app"]["backend"],         "nivel 3 presente")
check(rendered_deep["app"]["backend"]["db"]["engine"] == "postgres",
      "atributo en nivel 3 correcto")


# ────────────────────────────────────────────────────────────────────────────
header("4  · render() — dict / YAML / JSON")
# ────────────────────────────────────────────────────────────────────────────

section("Render a dict")
n = Node("server") + attr(host="localhost", port=8080)
d = n.render()
info("render('dict')", d)
check(d == {"server": {"host": "localhost", "port": 8080}}, "render dict correcto")

section("Render a JSON")
raw_json = n.render(format="json")
parsed   = json.loads(raw_json)
check(parsed["server"]["port"] == 8080, "JSON parseable y correcto")
show("JSON output", raw_json)

section("Render a YAML")
import yaml
raw_yaml = n.render(format="yaml")
parsed_y = yaml.safe_load(raw_yaml)
check(parsed_y["server"]["host"] == "localhost", "YAML parseable y correcto")
show("YAML output", raw_yaml)

section("Hijos con el mismo nombre → lista YAML")
compose = Node("docker-compose") >> [
    Node("service") + attr(svc="web",      image="nginx:1.25"),
    Node("service") + attr(svc="database", image="postgres:16"),
    Node("service") + attr(svc="cache",    image="redis:7"),
]
result = compose.render()
services = result["docker-compose"]["service"]
check(isinstance(services, list),  "hijos homónimos → lista")
check(len(services) == 3,          "tres servicios en la lista")
show("Compose render", yaml.dump(result, default_flow_style=False))


# ────────────────────────────────────────────────────────────────────────────
header("5  · @blueprint — fábricas puras")
# ────────────────────────────────────────────────────────────────────────────

@blueprint
def web_service(image: str, port: int = 80, replicas: int = 1) -> Node:
    return (
        Node("service")
        + attr(image=image, ports=[port], restart="always",
               deploy={"replicas": replicas})
    )

@blueprint
def db_service(engine: str, version: str, password: str) -> Node:
    image = f"{engine}:{version}"
    return (
        Node("service")
        + attr(image=image, restart="unless-stopped",
               environment={"DB_PASSWORD": password})
    )

section("Creación de instancias")
nginx_svc   = web_service(image="nginx:1.25", port=80,   replicas=3)
backend_svc = web_service(image="myapp:2.1",  port=8000, replicas=2)
postgres    = db_service(engine="postgres", version="16", password="s3cr3t")

info("nginx image",   nginx_svc.attributes["image"])
info("backend port",  nginx_svc.attributes["ports"])
info("db image",      postgres.attributes["image"])

check(nginx_svc.attributes["deploy"]["replicas"] == 3, "replicas en nginx=3")
check(backend_svc.attributes["deploy"]["replicas"] == 2, "replicas en backend=2")
check(postgres.attributes["environment"]["DB_PASSWORD"] == "s3cr3t", "password en db")
check(web_service.is_blueprint, "@blueprint marca is_blueprint=True")

section("Los blueprints son independientes")
check(
    nginx_svc.attributes["image"] != backend_svc.attributes["image"],
    "cada instancia tiene su propia imagen"
)


# ────────────────────────────────────────────────────────────────────────────
header("6  · Schema — validación declarativa")
# ────────────────────────────────────────────────────────────────────────────

service_schema = (
    Schema("service")
    .require("image",   str)
    .require("restart", str, choices=["always", "unless-stopped", "no"])
    .optional("ports",  list)
    .optional("replicas", int,
              predicate=lambda v: 1 <= v <= 100,
              predicate_message="debe estar entre 1 y 100")
    .check(lambda n: (
        "evita usar :latest en producción"
        if n.attributes.get("image", "").endswith(":latest")
        else None
    ))
)

section("Nodo válido")
valid_node = Node("service") + attr(image="nginx:1.25", restart="always", ports=[80])
result = valid_node.validate(service_schema)
check(result.valid,        "nodo válido → result.valid = True")
check(result.errors == [], "sin errores")

section("Nodo inválido — múltiples errores")
bad_node = Node("service") + attr(restart="maybe", replicas=999)
bad_result = bad_node.validate(service_schema)
check(not bad_result.valid,                         "nodo inválido detectado")
check(any("image"    in e for e in bad_result.errors), "error: image faltante")
check(any("restart"  in e for e in bad_result.errors), "error: restart inválido")
check(any("replicas" in e for e in bad_result.errors), "error: replicas fuera de rango")
show("Errores encontrados", "\n".join(bad_result.errors))

section("Predicado de imagen :latest")
latest_node = Node("service") + attr(image="nginx:latest", restart="always")
latest_result = latest_node.validate(service_schema)
check(not latest_result.valid,                      ":latest rechazado por check()")
check(any("latest" in e for e in latest_result.errors), "mensaje de error claro")

section("raise_if_invalid()")
try:
    bad_result.raise_if_invalid()
    check(False, "debería haber lanzado ValidationError")
except ValidationError as e:
    check(True, f"ValidationError lanzado con {len(e.errors)} errores")

section("Schema con pattern (regex)")
tag_schema = Schema().require("tag", str, pattern=r"\d+\.\d+\.\d+")
check(Node("img", tag="1.25.3").validate(tag_schema).valid,   "1.25.3 válido")
check(not Node("img", tag="latest").validate(tag_schema).valid, "'latest' inválido")


# ────────────────────────────────────────────────────────────────────────────
header("7  · Tree + build() — wrapper multi-formato")
# ────────────────────────────────────────────────────────────────────────────

root_node = Node("config") >> [
    Node("server",   host="0.0.0.0", port=8080),
    Node("database", host="db",      port=5432),
]
tree = build(root_node)

section("Tipos")
check(isinstance(tree, Tree), "build() retorna un Tree")

section("to_dict()")
d = tree.to_dict()
check("config" in d,                        "clave raíz presente")
check("server"   in d["config"],            "server presente")
check("database" in d["config"],            "database presente")

section("to_json()")
j = json.loads(tree.to_json())
check(j["config"]["server"]["port"] == 8080, "JSON port server correcto")

section("to_yaml()")
y = yaml.safe_load(tree.to_yaml())
check(y["config"]["database"]["host"] == "db", "YAML host database correcto")

section("__str__ imprime YAML")
as_str = str(tree)
check("config" in as_str, "__str__ contiene 'config'")
show("tree.__str__()", as_str)


# ────────────────────────────────────────────────────────────────────────────
header("8  · export() — escritura en disco")
# ────────────────────────────────────────────────────────────────────────────

with tempfile.TemporaryDirectory() as tmpdir:

    section("Export a YAML (.yml)")
    yml_path = os.path.join(tmpdir, "out.yml")
    export(root_node, filename=yml_path)
    with open(yml_path) as f:
        loaded = yaml.safe_load(f)
    check(os.path.exists(yml_path),              "archivo .yml creado")
    check(loaded["config"]["server"]["port"] == 8080, "contenido YAML correcto")
    info("ruta", yml_path)

    section("Export a JSON (.json)")
    json_path = os.path.join(tmpdir, "out.json")
    export(root_node, filename=json_path)
    with open(json_path) as f:
        loaded_j = json.load(f)
    check(os.path.exists(json_path),             "archivo .json creado")
    check(loaded_j["config"]["database"]["host"] == "db", "contenido JSON correcto")

    section("Export desde un Tree")
    tree_path = os.path.join(tmpdir, "from_tree.yml")
    export(tree, filename=tree_path)
    check(os.path.exists(tree_path), "export acepta Tree además de Node")

    section("Export crea directorios intermedios automáticamente")
    deep_path = os.path.join(tmpdir, "a", "b", "c", "deep.yml")
    export(root_node, filename=deep_path)
    check(os.path.exists(deep_path), "directorios creados automáticamente")

    section("Format explícito sobreescribe extensión")
    txt_path = os.path.join(tmpdir, "out.txt")
    export(root_node, filename=txt_path, format="json")
    with open(txt_path) as f:
        loaded_t = json.load(f)
    check(loaded_t["config"]["server"]["host"] == "0.0.0.0",
          "formato explícito json funciona en .txt")

    section("Format inválido lanza ValueError")
    try:
        export(root_node, filename=os.path.join(tmpdir, "x.yml"), format="toml")
        check(False, "debería lanzar ValueError")
    except ValueError:
        check(True, "ValueError en formato desconocido")


# ────────────────────────────────────────────────────────────────────────────
header("9  · Caso real — Stack Docker Compose completo")
# ────────────────────────────────────────────────────────────────────────────

section("Definición de blueprints")

@blueprint
def frontend(image: str, port: int = 80) -> Node:
    return Node("service") + attr(
        image=image, ports=[port],
        restart="always", networks=["public", "internal"],
        deploy={"replicas": 2, "update_config": {"parallelism": 1}},
    )

@blueprint
def backend(image: str, port: int = 3000, env: dict | None = None) -> Node:
    base = Node("service") + attr(
        image=image, ports=[port],
        restart="always", networks=["internal"],
        deploy={"replicas": 3},
    )
    return base + attr(environment=env) if env else base

@blueprint
def database(engine: str, version: str, env: dict) -> Node:
    return Node("service") + attr(
        image=f"{engine}:{version}",
        restart="unless-stopped",
        networks=["internal"],
        volumes=[f"{engine}_data:/var/lib/{engine}"],
        environment=env,
    )

section("Composición del stack")

stack = Node("docker-compose", version="3.9") >> [
    frontend(image="nginx:1.25", port=80),
    backend(
        image="myapp:2.3.1",
        port=3000,
        env={"NODE_ENV": "production", "PORT": "3000", "LOG_LEVEL": "info"},
    ),
    database(
        engine="postgres",
        version="16",
        env={"POSTGRES_DB": "myapp", "POSTGRES_USER": "app",
             "POSTGRES_PASSWORD": "ultrasecret"},
    ),
    database(
        engine="redis",
        version="7-alpine",
        env={"REDIS_PASSWORD": "cachesecret"},
    ),
]

check(len(stack.children) == 4, "stack tiene 4 servicios")

section("Validación de todos los servicios")

compose_schema = (
    Schema("service")
    .require("image",   str)
    .require("restart", str, choices=["always", "unless-stopped", "no"])
    .optional("ports",  list)
    .optional("networks", list)
    .optional("environment", dict)
    .optional("volumes", list)
    .optional("deploy", dict)
    .check(lambda n: (
        "evita :latest en producción"
        if n.attributes.get("image","").endswith(":latest")
        else None
    ))
)

all_valid = True
for child in stack.children:
    r = child.validate(compose_schema)
    if not r.valid:
        all_valid = False
        for e in r.errors:
            fail(e)
    else:
        ok(f"'{child.name}' con imagen '{child.attributes.get('image')}' ✓")

check(all_valid, "todos los servicios pasan validación")

section("Render YAML final del stack")
final_yaml = stack.render(format="yaml")
parsed_stack = yaml.safe_load(final_yaml)
show("docker-compose.yml generado", final_yaml)

check("docker-compose" in parsed_stack, "clave raíz docker-compose presente")
services = parsed_stack["docker-compose"]["service"]
check(isinstance(services, list), "servicios como lista YAML")
check(len(services) == 4,         "4 servicios en el YAML")

section("Export a archivo final")
with tempfile.TemporaryDirectory() as d:
    path = export(stack, filename=os.path.join(d, "docker-compose.yml"))
    check(os.path.exists(path), f"archivo exportado: {os.path.basename(path)}")
    with open(path) as f:
        content = f.read()
    check("docker-compose" in content, "contenido del archivo correcto")


# ────────────────────────────────────────────────────────────────────────────
header("10  · Edge cases y robustez")
# ────────────────────────────────────────────────────────────────────────────

section("Operador >> rechaza tipos incorrectos")
try:
    _ = Node("x") >> "no-soy-un-nodo"
    check(False, "debería haber lanzado TypeError")
except TypeError:
    check(True, ">> lanza TypeError con no-Node")

section(">> rechaza listas con items inválidos")
try:
    _ = Node("x") >> [Node("ok"), 42]
    check(False, "debería haber lanzado TypeError")
except TypeError:
    check(True, ">> lanza TypeError en lista mixta")

section("Node.__init__ rechaza 'name' como kwarg")
try:
    _ = Node("service", name="web")
    check(False, "debería haber lanzado TypeError")
except TypeError as e:
    check(True, f"TypeError claro: {e}")

section("render() lanza ValueError en formato desconocido")
try:
    Node("x").render(format="xml")
    check(False, "debería haber lanzado ValueError")
except ValueError:
    check(True, "ValueError con formato 'xml'")

section("Igualdad estructural de nodos")
a = Node("cfg") + attr(x=1, y=[1, 2])
b = Node("cfg") + attr(x=1, y=[1, 2])
c = Node("cfg") + attr(x=1, y=[1, 3])
check(a == b, "nodos estructuralmente iguales son ==")
check(a != c, "nodos diferentes son !=")

section("Deep merge recursivo en atributos anidados")
n1 = Node("cfg") + attr(db={"host": "localhost", "port": 5432})
n2 = n1 + attr(db={"port": 5433, "ssl": True})
merged = n2.render()["cfg"]["db"]
check(merged["host"] == "localhost", "deep merge: clave original conservada")
check(merged["port"] == 5433,        "deep merge: clave sobreescrita")
check(merged["ssl"] is True,         "deep merge: nueva clave añadida")

section("Nodo sin nombre (name='') para raíces desnudas")
naked = Node("") + attr(version="3.9")
d = naked.render()
check("version" in d, "nodo sin nombre no añade clave envolvente")


# ════════════════════════════════════════════════════════════════════════════
# Resultado final
# ════════════════════════════════════════════════════════════════════════════

total = len(ERRORS)
print(f"\n{B}{'━' * 60}{RST}")
if total == 0:
    print(f"\n  {G}{BOLD}🎉  Todo correcto — funkyconf funciona perfectamente.{RST}\n")
else:
    print(f"\n  {R}{BOLD}💥  {total} verificación(es) fallaron:{RST}")
    for e in ERRORS:
        print(f"      {R}• {e}{RST}")
    print()
print(f"{B}{'━' * 60}{RST}\n")
sys.exit(0 if total == 0 else 1)
