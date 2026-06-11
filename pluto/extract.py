"""Per-file extractors → `{nodes, edges}` dicts.

Confidence tags:
- `EXTRACTED` for literal facts (a `def foo` we saw in source).
- `INFERRED` for things we deduced (a `foo(...)` call that probably refers
  to that `def`, but we didn't resolve scopes).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PYTHON_BUILTINS = {
    "print", "len", "range", "list", "dict", "set", "tuple", "str", "int",
    "float", "bool", "type", "isinstance", "issubclass", "open", "input",
    "sorted", "sum", "min", "max", "abs", "round", "map", "filter", "zip",
    "enumerate", "any", "all", "iter", "next", "reversed", "hash", "id",
    "repr", "format", "getattr", "setattr", "hasattr", "delattr", "vars",
    "dir", "callable", "super", "object", "Exception", "ValueError",
    "TypeError", "KeyError", "IndexError", "AttributeError", "RuntimeError",
    "NotImplementedError", "StopIteration", "FileNotFoundError", "OSError",
    "globals", "locals", "exec", "eval", "staticmethod", "classmethod",
    "property", "bytes", "bytearray", "memoryview", "frozenset", "complex",
}


def _node_id(kind: str, path: str, name: str) -> str:
    return f"{kind}::{path}::{name}"


def _file_node(rel_path: str, kind: str) -> dict:
    return {
        "id": f"file::{rel_path}",
        "type": "file",
        "name": rel_path,
        "src": rel_path,
        "language": kind,
        "confidence": "EXTRACTED",
    }


# --- Python ---------------------------------------------------------------

def _extract_python(path: Path, rel: str, source: str) -> dict:
    nodes: list[dict] = [_file_node(rel, "python")]
    edges: list[dict] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"nodes": nodes, "edges": edges}

    file_id = nodes[0]["id"]
    defined_names: set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def _qual(self, name: str) -> str:
            return ".".join(self.scope + [name]) if self.scope else name

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                target_id = f"module::{alias.name}"
                if not any(n["id"] == target_id for n in nodes):
                    nodes.append({
                        "id": target_id,
                        "type": "module",
                        "name": alias.name,
                        "src": rel,
                        "confidence": "EXTRACTED",
                    })
                edges.append({
                    "source": file_id,
                    "target": target_id,
                    "type": "imports",
                    "src": rel,
                    "line": node.lineno,
                    "confidence": "EXTRACTED",
                })
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module_name = node.module or "."
            target_id = f"module::{module_name}"
            if not any(n["id"] == target_id for n in nodes):
                nodes.append({
                    "id": target_id,
                    "type": "module",
                    "name": module_name,
                    "src": rel,
                    "confidence": "EXTRACTED",
                })
            for alias in node.names:
                edges.append({
                    "source": file_id,
                    "target": target_id,
                    "type": "imports",
                    "symbol": alias.name,
                    "src": rel,
                    "line": node.lineno,
                    "confidence": "EXTRACTED",
                })
            self.generic_visit(node)

        def _add_function(self, node: ast.AST, name: str) -> str:
            qual = self._qual(name)
            nid = _node_id("function", rel, qual)
            nodes.append({
                "id": nid,
                "type": "function",
                "name": qual,
                "src": rel,
                "line": getattr(node, "lineno", None),
                "confidence": "EXTRACTED",
            })
            edges.append({
                "source": file_id,
                "target": nid,
                "type": "defines",
                "src": rel,
                "line": getattr(node, "lineno", None),
                "confidence": "EXTRACTED",
            })
            defined_names.add(name)
            defined_names.add(qual)
            return nid

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_func(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_func(node)

        def _visit_func(self, node) -> None:
            fid = self._add_function(node, node.name)
            self.scope.append(node.name)
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    callee = _call_name(child.func)
                    if callee and callee not in PYTHON_BUILTINS:
                        target = _node_id("symbol", "?", callee)
                        edges.append({
                            "source": fid,
                            "target": target,
                            "type": "calls",
                            "symbol": callee,
                            "src": rel,
                            "line": child.lineno,
                            "confidence": "INFERRED",
                        })
            self.scope.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qual = self._qual(node.name)
            cid = _node_id("class", rel, qual)
            nodes.append({
                "id": cid,
                "type": "class",
                "name": qual,
                "src": rel,
                "line": node.lineno,
                "confidence": "EXTRACTED",
            })
            edges.append({
                "source": file_id,
                "target": cid,
                "type": "defines",
                "src": rel,
                "line": node.lineno,
                "confidence": "EXTRACTED",
            })
            defined_names.add(node.name)
            defined_names.add(qual)
            for base in node.bases:
                base_name = _call_name(base)
                if base_name:
                    edges.append({
                        "source": cid,
                        "target": _node_id("symbol", "?", base_name),
                        "type": "inherits",
                        "symbol": base_name,
                        "src": rel,
                        "line": node.lineno,
                        "confidence": "INFERRED",
                    })
            self.scope.append(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_id = self._add_function(item, item.name)
                    edges.append({
                        "source": cid,
                        "target": method_id,
                        "type": "has-method",
                        "src": rel,
                        "line": item.lineno,
                        "confidence": "EXTRACTED",
                    })
                    self.scope.append(item.name)
                    for child in ast.walk(item):
                        if isinstance(child, ast.Call):
                            callee = _call_name(child.func)
                            if callee and callee not in PYTHON_BUILTINS:
                                edges.append({
                                    "source": method_id,
                                    "target": _node_id("symbol", "?", callee),
                                    "type": "calls",
                                    "symbol": callee,
                                    "src": rel,
                                    "line": child.lineno,
                                    "confidence": "INFERRED",
                                })
                    self.scope.pop()
                else:
                    self.visit(item)
            self.scope.pop()

    _Visitor().visit(tree)
    return {"nodes": nodes, "edges": edges}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
        return node.attr
    return None


# --- JavaScript / TypeScript ---------------------------------------------

_JS_IMPORT = re.compile(
    r"""^\s*(?:import\s+(?:[\w*{}\s,]+?\s+from\s+)?["']([^"']+)["']
        |const\s+[\w{}\s,]+?\s*=\s*require\(["']([^"']+)["']\)
        |export\s+(?:\*|\{[\w\s,]+\})\s+from\s+["']([^"']+)["'])""",
    re.VERBOSE | re.MULTILINE,
)
_JS_FUNC = re.compile(
    r"""^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)""",
    re.MULTILINE,
)
_JS_CONST_FN = re.compile(
    r"""^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|\w+)\s*=>""",
    re.MULTILINE,
)
_JS_CLASS = re.compile(
    r"""^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+([\w.]+))?""",
    re.MULTILINE,
)


def _extract_js_like(path: Path, rel: str, source: str, language: str) -> dict:
    nodes: list[dict] = [_file_node(rel, language)]
    edges: list[dict] = []
    file_id = nodes[0]["id"]

    for m in _JS_IMPORT.finditer(source):
        mod = next((g for g in m.groups() if g), None)
        if not mod:
            continue
        target_id = f"module::{mod}"
        if not any(n["id"] == target_id for n in nodes):
            nodes.append({
                "id": target_id,
                "type": "module",
                "name": mod,
                "src": rel,
                "confidence": "EXTRACTED",
            })
        edges.append({
            "source": file_id,
            "target": target_id,
            "type": "imports",
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })

    for m in _JS_FUNC.finditer(source):
        name = m.group(1)
        nid = _node_id("function", rel, name)
        nodes.append({
            "id": nid,
            "type": "function",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": nid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })

    for m in _JS_CONST_FN.finditer(source):
        name = m.group(1)
        nid = _node_id("function", rel, name)
        if any(n["id"] == nid for n in nodes):
            continue
        nodes.append({
            "id": nid,
            "type": "function",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": nid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })

    for m in _JS_CLASS.finditer(source):
        name = m.group(1)
        parent = m.group(2)
        cid = _node_id("class", rel, name)
        nodes.append({
            "id": cid,
            "type": "class",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": cid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })
        if parent:
            edges.append({
                "source": cid,
                "target": _node_id("symbol", "?", parent),
                "type": "inherits",
                "symbol": parent,
                "src": rel,
                "confidence": "INFERRED",
            })

    return {"nodes": nodes, "edges": edges}


# --- Go --------------------------------------------------------------------

_GO_IMPORT_BLOCK = re.compile(r"""import\s*\(([^)]*)\)""", re.DOTALL)
_GO_IMPORT_SINGLE = re.compile(r"""import\s+"([^"]+)" """, re.VERBOSE)
_GO_QUOTED = re.compile(r'"([^"]+)"')
_GO_FUNC = re.compile(
    r"""^\s*func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)""",
    re.MULTILINE,
)
_GO_TYPE = re.compile(
    r"""^\s*type\s+(\w+)\s+(?:struct|interface)""",
    re.MULTILINE,
)


def _extract_go(path: Path, rel: str, source: str) -> dict:
    nodes: list[dict] = [_file_node(rel, "go")]
    edges: list[dict] = []
    file_id = nodes[0]["id"]

    def _add_import(mod: str, line: int) -> None:
        target_id = f"module::{mod}"
        if not any(n["id"] == target_id for n in nodes):
            nodes.append({
                "id": target_id,
                "type": "module",
                "name": mod,
                "src": rel,
                "confidence": "EXTRACTED",
            })
        edges.append({
            "source": file_id,
            "target": target_id,
            "type": "imports",
            "src": rel,
            "line": line,
            "confidence": "EXTRACTED",
        })

    for m in _GO_IMPORT_BLOCK.finditer(source):
        block = m.group(1)
        base_line = source[:m.start()].count("\n") + 1
        for q in _GO_QUOTED.finditer(block):
            _add_import(q.group(1), base_line)
    for m in _GO_IMPORT_SINGLE.finditer(source):
        _add_import(m.group(1), source[:m.start()].count("\n") + 1)

    for m in _GO_FUNC.finditer(source):
        name = m.group(1)
        nid = _node_id("function", rel, name)
        nodes.append({
            "id": nid,
            "type": "function",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": nid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })
    for m in _GO_TYPE.finditer(source):
        name = m.group(1)
        cid = _node_id("class", rel, name)
        nodes.append({
            "id": cid,
            "type": "class",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": cid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })

    return {"nodes": nodes, "edges": edges}


# --- Rust -----------------------------------------------------------------

_RUST_USE = re.compile(r"""^\s*use\s+([^\s;{]+)""", re.MULTILINE)
_RUST_FN = re.compile(
    r"""^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)""",
    re.MULTILINE,
)
_RUST_STRUCT = re.compile(
    r"""^\s*(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)""",
    re.MULTILINE,
)


def _extract_rust(path: Path, rel: str, source: str) -> dict:
    nodes: list[dict] = [_file_node(rel, "rust")]
    edges: list[dict] = []
    file_id = nodes[0]["id"]

    for m in _RUST_USE.finditer(source):
        mod = m.group(1)
        target_id = f"module::{mod}"
        if not any(n["id"] == target_id for n in nodes):
            nodes.append({
                "id": target_id,
                "type": "module",
                "name": mod,
                "src": rel,
                "confidence": "EXTRACTED",
            })
        edges.append({
            "source": file_id,
            "target": target_id,
            "type": "imports",
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })

    for m in _RUST_FN.finditer(source):
        name = m.group(1)
        nid = _node_id("function", rel, name)
        nodes.append({
            "id": nid,
            "type": "function",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": nid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })
    for m in _RUST_STRUCT.finditer(source):
        name = m.group(1)
        cid = _node_id("class", rel, name)
        nodes.append({
            "id": cid,
            "type": "class",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": cid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })

    return {"nodes": nodes, "edges": edges}


# --- Java -----------------------------------------------------------------

_JAVA_IMPORT = re.compile(r"""^\s*import\s+(?:static\s+)?([\w.]+\*?);""", re.MULTILINE)
_JAVA_CLASS = re.compile(
    r"""^\s*(?:public\s+|private\s+|protected\s+|abstract\s+|final\s+|static\s+)*
        (?:class|interface|enum)\s+(\w+)
        (?:\s+extends\s+([\w.]+))?""",
    re.MULTILINE | re.VERBOSE,
)
_JAVA_METHOD = re.compile(
    r"""^\s*(?:public\s+|private\s+|protected\s+|static\s+|final\s+|abstract\s+|synchronized\s+)+
        [\w<>\[\],\s.?]+?\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w.,\s]+)?\s*\{""",
    re.MULTILINE | re.VERBOSE,
)


def _extract_java(path: Path, rel: str, source: str) -> dict:
    nodes: list[dict] = [_file_node(rel, "java")]
    edges: list[dict] = []
    file_id = nodes[0]["id"]

    for m in _JAVA_IMPORT.finditer(source):
        mod = m.group(1)
        target_id = f"module::{mod}"
        if not any(n["id"] == target_id for n in nodes):
            nodes.append({
                "id": target_id,
                "type": "module",
                "name": mod,
                "src": rel,
                "confidence": "EXTRACTED",
            })
        edges.append({
            "source": file_id,
            "target": target_id,
            "type": "imports",
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })

    for m in _JAVA_CLASS.finditer(source):
        name = m.group(1)
        parent = m.group(2)
        cid = _node_id("class", rel, name)
        nodes.append({
            "id": cid,
            "type": "class",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": cid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })
        if parent:
            edges.append({
                "source": cid,
                "target": _node_id("symbol", "?", parent),
                "type": "inherits",
                "symbol": parent,
                "src": rel,
                "confidence": "INFERRED",
            })

    for m in _JAVA_METHOD.finditer(source):
        name = m.group(1)
        if name in {"if", "for", "while", "switch", "catch", "synchronized", "return"}:
            continue
        nid = _node_id("function", rel, name)
        if any(n["id"] == nid for n in nodes):
            continue
        nodes.append({
            "id": nid,
            "type": "function",
            "name": name,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": nid,
            "type": "defines",
            "src": rel,
            "confidence": "EXTRACTED",
        })

    return {"nodes": nodes, "edges": edges}


# --- Markdown --------------------------------------------------------------

_MD_HEADING = re.compile(r"""^(#{1,6})\s+(.+?)\s*$""", re.MULTILINE)
_MD_LINK = re.compile(r"""\[([^\]]+)\]\(([^)]+)\)""")


def _extract_markdown(path: Path, rel: str, source: str) -> dict:
    nodes: list[dict] = [_file_node(rel, "markdown")]
    edges: list[dict] = []
    file_id = nodes[0]["id"]
    last_heading_id = file_id

    for m in _MD_HEADING.finditer(source):
        level = len(m.group(1))
        title = m.group(2).strip()
        hid = _node_id("heading", rel, f"h{level}-{title}")
        nodes.append({
            "id": hid,
            "type": "heading",
            "name": title,
            "level": level,
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })
        edges.append({
            "source": file_id,
            "target": hid,
            "type": "contains",
            "src": rel,
            "confidence": "EXTRACTED",
        })
        last_heading_id = hid

    for m in _MD_LINK.finditer(source):
        target = m.group(2)
        if target.startswith("#") or target.startswith("mailto:"):
            continue
        target_id = f"link::{target}"
        if not any(n["id"] == target_id for n in nodes):
            nodes.append({
                "id": target_id,
                "type": "link",
                "name": target,
                "src": rel,
                "confidence": "EXTRACTED",
            })
        edges.append({
            "source": last_heading_id,
            "target": target_id,
            "type": "links",
            "src": rel,
            "line": source[:m.start()].count("\n") + 1,
            "confidence": "EXTRACTED",
        })

    return {"nodes": nodes, "edges": edges}


# --- Dispatch -------------------------------------------------------------

def extract(path: Path, root: Path) -> dict:
    """Extract `{nodes, edges}` from `path`. Empty dict on read failure."""
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        rel = path.name
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"nodes": [], "edges": []}

    suffix = path.suffix.lower()
    if suffix == ".py":
        return _extract_python(path, rel, source)
    if suffix in {".js", ".mjs", ".cjs", ".jsx"}:
        return _extract_js_like(path, rel, source, "javascript")
    if suffix in {".ts", ".tsx"}:
        return _extract_js_like(path, rel, source, "typescript")
    if suffix == ".go":
        return _extract_go(path, rel, source)
    if suffix == ".rs":
        return _extract_rust(path, rel, source)
    if suffix == ".java":
        return _extract_java(path, rel, source)
    if suffix in {".md", ".markdown"}:
        return _extract_markdown(path, rel, source)
    return {"nodes": [_file_node(rel, "text")], "edges": []}
