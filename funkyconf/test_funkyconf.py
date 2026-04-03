"""
tests/test_funkyconf.py
~~~~~~~~~~~~~~~~~~~~~~~
Full test suite for funkyconf.
"""
import json
import os
import tempfile

import pytest

from funkyconf import (
    Node,
    Schema,
    Tree,
    ValidationError,
    attr,
    blueprint,
    build,
    export,
)


# ===========================================================================
# attr
# ===========================================================================

class TestAttr:
    def test_basic_creation(self):
        a = attr(x=1, y="hello")
        assert a.data == {"x": 1, "y": "hello"}

    def test_immutable_data_copy(self):
        a = attr(x=[1, 2, 3])
        d = a.data
        d["x"].append(99)
        assert a.data["x"] == [1, 2, 3]  # original unchanged

    def test_overlay_attrs(self):
        a = attr(x=1, y=2)
        b = attr(y=99, z=3)
        c = a + b
        assert c.data == {"x": 1, "y": 99, "z": 3}

    def test_overlay_does_not_mutate(self):
        a = attr(x=1)
        b = attr(x=2)
        _ = a + b
        assert a.data["x"] == 1


# ===========================================================================
# Node – basic
# ===========================================================================

class TestNodeBasic:
    def test_name(self):
        n = Node("service")
        assert n.name == "service"

    def test_inline_attrs(self):
        n = Node("service", restart="always")
        assert n.attributes["restart"] == "always"

    def test_immutable_attributes(self):
        n = Node("service", tags=["a", "b"])
        attrs = n.attributes
        attrs["tags"].append("c")
        assert n.attributes["tags"] == ["a", "b"]


# ===========================================================================
# Node – Overlay (+)
# ===========================================================================

class TestNodeOverlay:
    def test_node_plus_attr(self):
        n = Node("svc") + attr(image="nginx", port=80)
        assert n.attributes == {"image": "nginx", "port": 80}

    def test_node_plus_attr_immutable(self):
        n1 = Node("svc", image="nginx")
        n2 = n1 + attr(port=80)
        assert "port" not in n1.attributes
        assert n2.attributes["port"] == 80

    def test_node_plus_node_merges_attrs(self):
        a = Node("svc", x=1)
        b = Node("svc", y=2)
        c = a + b
        assert c.attributes == {"x": 1, "y": 2}

    def test_node_plus_node_appends_children(self):
        child = Node("child")
        a = Node("parent") >> child
        b = Node("parent") >> Node("extra")
        c = a + b
        assert len(c.children) == 2

    def test_radd_attr_node(self):
        a = attr(x=1)
        n = Node("svc", y=2)
        result = a + n  # _Attributes + Node not directly supported
        # attr + node goes through __add__ of _Attributes which returns NotImplemented
        # so Python falls back to Node.__radd__
        assert result.attributes["x"] == 1
        assert result.attributes["y"] == 2


# ===========================================================================
# Node – Nest (>>)
# ===========================================================================

class TestNodeNest:
    def test_single_child(self):
        parent = Node("parent") >> Node("child")
        assert len(parent.children) == 1
        assert parent.children[0].name == "child"

    def test_list_of_children(self):
        parent = Node("parent") >> [Node("c1"), Node("c2"), Node("c3")]
        assert len(parent.children) == 3

    def test_nest_is_immutable(self):
        parent = Node("parent")
        _ = parent >> Node("child")
        assert len(parent.children) == 0

    def test_invalid_child_type_raises(self):
        with pytest.raises(TypeError):
            _ = Node("parent") >> "not-a-node"

    def test_invalid_list_item_raises(self):
        with pytest.raises(TypeError):
            _ = Node("parent") >> [Node("ok"), "bad"]


# ===========================================================================
# Node – Callable (Blueprint pattern)
# ===========================================================================

class TestNodeCallable:
    def test_rename(self):
        base = Node("service")
        concrete = base(name="web")
        assert concrete.name == "web"
        assert base.name == "service"  # immutable

    def test_extra_kwargs(self):
        base = Node("service", restart="always")
        concrete = base(name="web", image="nginx")
        assert concrete.attributes["image"] == "nginx"
        assert concrete.attributes["restart"] == "always"

    def test_original_unmodified(self):
        base = Node("service", restart="always")
        _ = base(name="web", image="nginx")
        assert list(base.attributes.keys()) == ["restart"]


# ===========================================================================
# Node – Render
# ===========================================================================

class TestNodeRender:
    def test_render_dict_simple(self):
        n = Node("app", version="1.0")
        assert n.render() == {"app": {"version": "1.0"}}

    def test_render_nested(self):
        tree = Node("root") >> Node("child", x=1)
        result = tree.render()
        assert result == {"root": {"child": {"x": 1}}}

    def test_render_json(self):
        n = Node("cfg", key="val")
        raw = n.render(format="json")
        parsed = json.loads(raw)
        assert parsed == {"cfg": {"key": "val"}}

    def test_render_yaml(self):
        pytest.importorskip("yaml")
        import yaml
        n = Node("cfg", enabled=True)
        raw = n.render(format="yaml")
        parsed = yaml.safe_load(raw)
        assert parsed == {"cfg": {"enabled": True}}

    def test_render_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            Node("x").render(format="toml")

    def test_same_name_children_become_list(self):
        parent = Node("compose") >> [
            Node("service", name="web"),
            Node("service", name="db"),
        ]
        result = parent.render()
        services = result["compose"]["service"]
        assert isinstance(services, list)
        assert len(services) == 2

    def test_equality(self):
        a = Node("x", v=1)
        b = Node("x", v=1)
        assert a == b

    def test_inequality(self):
        a = Node("x", v=1)
        b = Node("x", v=2)
        assert a != b


# ===========================================================================
# Schema & Validation
# ===========================================================================

class TestSchema:
    def _service_schema(self):
        return (
            Schema("service")
            .require("image", str)
            .require("restart", str, choices=["always", "unless-stopped", "no"])
            .optional("ports", list)
        )

    def test_valid_node(self):
        n = Node("svc", image="nginx:1.25", restart="always", ports=[80])
        result = n.validate(self._service_schema())
        assert result.valid is True
        assert result.errors == []

    def test_missing_required(self):
        n = Node("svc", restart="always")
        result = n.validate(self._service_schema())
        assert not result.valid
        assert any("image" in e for e in result.errors)

    def test_wrong_type(self):
        n = Node("svc", image=42, restart="always")
        result = n.validate(self._service_schema())
        assert not result.valid
        assert any("image" in e for e in result.errors)

    def test_bad_choice(self):
        n = Node("svc", image="nginx", restart="maybe")
        result = n.validate(self._service_schema())
        assert not result.valid
        assert any("restart" in e for e in result.errors)

    def test_optional_missing_ok(self):
        n = Node("svc", image="nginx", restart="always")
        result = n.validate(self._service_schema())
        assert result.valid

    def test_raise_if_invalid(self):
        n = Node("svc")
        result = n.validate(self._service_schema())
        with pytest.raises(ValidationError):
            result.raise_if_invalid()

    def test_predicate(self):
        schema = Schema().require(
            "port",
            int,
            predicate=lambda v: 1 <= v <= 65535,
            predicate_message="must be a valid port number",
        )
        good = Node("svc", port=8080)
        bad = Node("svc", port=99999)
        assert good.validate(schema).valid
        assert not bad.validate(schema).valid

    def test_pattern(self):
        schema = Schema().require("tag", str, pattern=r"\d+\.\d+\.\d+")
        good = Node("img", tag="1.25.0")
        bad = Node("img", tag="latest")
        assert good.validate(schema).valid
        assert not bad.validate(schema).valid

    def test_custom_check(self):
        def no_root_image(node):
            if node.attributes.get("image", "").startswith("root/"):
                return "image must not start with 'root/'"

        schema = Schema().check(no_root_image)
        good = Node("svc", image="nginx")
        bad = Node("svc", image="root/evil")
        assert good.validate(schema).valid
        assert not bad.validate(schema).valid


# ===========================================================================
# Blueprint decorator
# ===========================================================================

class TestBlueprint:
    def test_basic(self):
        @blueprint
        def web_service(image: str, port: int = 80) -> Node:
            return Node("service") + attr(image=image, ports=[port])

        n = web_service(image="nginx:1.25", port=8080)
        assert n.attributes["image"] == "nginx:1.25"

    def test_is_blueprint_flag(self):
        @blueprint
        def svc() -> Node:
            return Node("svc")

        assert svc.is_blueprint is True

    def test_wrong_return_type(self):
        @blueprint
        def bad():
            return {"not": "a node"}

        with pytest.raises(TypeError):
            bad()


# ===========================================================================
# Tree & build()
# ===========================================================================

class TestTree:
    def test_build_returns_tree(self):
        t = build(Node("root"))
        assert isinstance(t, Tree)

    def test_to_dict(self):
        t = build(Node("root", x=1))
        assert t.to_dict() == {"root": {"x": 1}}

    def test_to_yaml(self):
        pytest.importorskip("yaml")
        t = build(Node("root", x=1))
        assert "root" in t.to_yaml()

    def test_to_json(self):
        t = build(Node("root", x=1))
        parsed = json.loads(t.to_json())
        assert parsed == {"root": {"x": 1}}

    def test_str(self):
        pytest.importorskip("yaml")
        t = build(Node("root"))
        assert "root" in str(t)


# ===========================================================================
# Export
# ===========================================================================

class TestExport:
    def test_yaml_export(self, tmp_path):
        pytest.importorskip("yaml")
        import yaml
        n = Node("cfg", key="value")
        out = str(tmp_path / "out.yml")
        export(n, filename=out)
        with open(out) as f:
            parsed = yaml.safe_load(f)
        assert parsed == {"cfg": {"key": "value"}}

    def test_json_export(self, tmp_path):
        n = Node("cfg", key="value")
        out = str(tmp_path / "out.json")
        export(n, filename=out)
        with open(out) as f:
            parsed = json.load(f)
        assert parsed == {"cfg": {"key": "value"}}

    def test_export_creates_parent_dirs(self, tmp_path):
        pytest.importorskip("yaml")
        n = Node("cfg")
        out = str(tmp_path / "deep" / "nested" / "out.yml")
        export(n, filename=out)
        assert os.path.exists(out)

    def test_export_tree(self, tmp_path):
        pytest.importorskip("yaml")
        import yaml
        t = build(Node("cfg", v=42))
        out = str(tmp_path / "tree.yml")
        export(t, filename=out)
        with open(out) as f:
            parsed = yaml.safe_load(f)
        assert parsed["cfg"]["v"] == 42

    def test_explicit_json_format(self, tmp_path):
        n = Node("cfg", x=1)
        out = str(tmp_path / "out.txt")  # non-standard ext
        export(n, filename=out, format="json")
        with open(out) as f:
            parsed = json.load(f)
        assert parsed == {"cfg": {"x": 1}}

    def test_invalid_format_raises(self, tmp_path):
        with pytest.raises(ValueError):
            export(Node("x"), filename=str(tmp_path / "f.yml"), format="toml")


# ===========================================================================
# Dream usage (integration)
# ===========================================================================

class TestDreamUsage:
    def test_dream_usage(self):
        pytest.importorskip("yaml")
        import yaml

        base_service = Node("service") + attr(restart="always", networks=["frontend"])
        db_creds = attr(user="admin", password="safe_password_123")

        stack = Node("docker-compose") >> [
            base_service(name="web_app") + attr(image="nginx:1.25", ports=[80]),
            base_service(name="database") + db_creds + attr(image="postgres:16"),
        ]

        rendered = stack.render(format="yaml")
        parsed = yaml.safe_load(rendered)

        assert "docker-compose" in parsed
        services = parsed["docker-compose"]["service"]
        assert isinstance(services, list)

        names = {s["name"] for s in services}
        assert "web_app" in names
        assert "database" in names

        db = next(s for s in services if s["name"] == "database")
        assert db["user"] == "admin"
        assert db["image"] == "postgres:16"

    def test_base_service_is_reusable(self):
        base = Node("service") + attr(restart="always")
        web = base(name="web") + attr(image="nginx")
        db = base(name="db") + attr(image="postgres")

        assert web.name == "web"
        assert db.name == "db"
        assert web.attributes["image"] == "nginx"
        assert db.attributes["image"] == "postgres"
        # base unchanged
        assert base.name == "service"
        assert "image" not in base.attributes
