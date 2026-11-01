"""Lexical anchors: what an issue text names explicitly (files, symbols, traceback frames)."""
import re

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
BACKTICK = re.compile(r"`([^`\n]{1,200})`")
PYFILE = re.compile(r"[\w./-]+\.py\b")
TRACE = re.compile(r'File "([^"]+\.py)", line (\d+)')
CAMEL = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
# English words that are also common symbol names; matching them alone is not an anchor.
STOP = {"get", "set", "run", "add", "list", "dict", "str", "int", "type", "name", "data", "value", "self",
        "test", "main", "app", "request", "response", "error", "the", "and", "for", "with", "from",
        "import", "return", "true", "false", "none", "default", "update", "new", "fix", "use", "call",
        "init", "len", "repr", "path", "file", "text", "json", "item", "items", "keys", "values", "copy",
        "print", "render", "style", "client", "url", "headers", "body", "params", "content", "send"}


def tokens(text: str) -> list[str]:
    """Lowercased word pieces of an identifier-rich text (split on _ . and camelCase)."""
    out = []
    for w in re.findall(r"[A-Za-z0-9]+", text):
        out += [p.lower() for p in CAMEL.findall(w)] if not w.islower() else [w]
    return out


def mentioned_identifiers(text: str) -> set[str]:
    """Identifiers likely to refer to code: in backticks, dotted, snake_case, CamelCase, or call-like."""
    ids = set()
    for m in BACKTICK.findall(text):
        ids |= set(IDENT.findall(m))
    for m in IDENT.findall(text):
        if "." in m or "_" in m.strip("_") or re.search(r"[a-z][A-Z]", m) or re.match(r"[A-Z][a-z]+[A-Z]", m):
            ids.add(m)
    for m in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\(", text):
        ids.add(m)
    return {i for i in ids if len(i) > 2 and i.lower() not in STOP}


def file_anchors(text: str, py_files: list[str]) -> set[str]:
    """Repository .py files the text names by path suffix, basename, or traceback frame."""
    named = set(PYFILE.findall(text)) | {p for p, _ in TRACE.findall(text)}
    hits = set()
    for n in named:
        n = n.lstrip("./")
        base = n.rsplit("/", 1)[-1]
        for f in py_files:
            if f.endswith("/" + n) or f == n or (base not in ("__init__.py", "setup.py") and f.rsplit("/", 1)[-1] == base):
                hits.add(f)
    return hits


def symbol_anchors(text: str, node_names, node2file=None, files=()) -> set[str]:
    """Graph nodes whose name (last one or two dotted parts) matches an identifier in the text,
    plus every node defined in an anchored file."""
    ids = mentioned_identifiers(text)
    last = {}
    for n in node_names:
        parts = n.split(".")
        last.setdefault(parts[-1], []).append(n)
        if len(parts) > 1:
            last.setdefault(".".join(parts[-2:]), []).append(n)
    hits = set()
    for i in ids:
        cand = i.split(".")
        for k in (".".join(cand[-2:]), cand[-1]):
            if k in last and k.lower() not in STOP:
                hits |= set(last[k])
                break
    if node2file and files:
        hits |= {n for n, f in node2file.items() if f in files}
    return hits


if __name__ == "__main__":
    t = "Calling `Console.print_json()` fails in rich/console.py\n  File \"/x/rich/text.py\", line 3"
    assert "Console.print_json" in mentioned_identifiers(t)
    assert file_anchors(t, ["rich/console.py", "rich/text.py", "a.py"]) == {"rich/console.py", "rich/text.py"}
    assert symbol_anchors(t, ["rich.console.Console.print_json", "rich.json.JSON"]) == {"rich.console.Console.print_json"}
    assert tokens("parseHeader_value") == ["parse", "header", "value"]
    print("ok")
