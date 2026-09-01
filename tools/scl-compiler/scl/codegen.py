"""Python dict/list -> Lua table-literal text, matching the hand-written
style of etc/sas-ied.cfg.example / etc/sas-scada.cfg.example (bare table
literal, no `return`, read via serialization.unserialize -- see that
file's own header comment). `--check`/tests wrap it in `return ...` to
syntax-check with `luac5.3 -p`, same as any other .cfg file in this repo.
"""

_LUA_KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while",
}

_BARE_KEY_RE_FIRST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_BARE_KEY_RE_REST = _BARE_KEY_RE_FIRST + "0123456789"


def _is_bare_key(key):
    if not isinstance(key, str) or not key:
        return False
    if key in _LUA_KEYWORDS:
        return False
    if key[0] not in _BARE_KEY_RE_FIRST:
        return False
    return all(c in _BARE_KEY_RE_REST for c in key[1:])


def _encode_string(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"%s"' % escaped


def _encode_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return repr(value)
        return repr(value)
    if isinstance(value, str):
        return _encode_string(value)
    raise TypeError("not a scalar: %r" % (value,))


def encode(value, indent=0):
    """Render `value` (dict/list/str/bool/int/float/None) as a Lua
    table-literal fragment. Dict keys that are valid Lua identifiers are
    emitted bare (`key = ...`); everything else uses `["key"] = ...`.
    Lists become sequence-style tables (`{ ... }`, no keys).
    """
    pad = "  " * indent
    inner_pad = "  " * (indent + 1)

    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for k, v in value.items():
            key_text = k if _is_bare_key(k) else "[%s]" % _encode_string(str(k))
            lines.append("%s%s = %s," % (inner_pad, key_text, encode(v, indent + 1)))
        lines.append(pad + "}")
        return "\n".join(lines)

    if isinstance(value, (list, tuple)):
        if not value:
            return "{}"
        lines = ["{"]
        for item in value:
            lines.append("%s%s," % (inner_pad, encode(item, indent + 1)))
        lines.append(pad + "}")
        return "\n".join(lines)

    return _encode_scalar(value)


def encode_top_level(value, header_comment=""):
    """A full .cfg file's text: optional header comment block, then the
    bare table literal (matching etc/*.cfg.example's convention -- no
    `return` prefix; serialization.unserialize expects a bare expression).
    """
    parts = []
    if header_comment:
        for line in header_comment.rstrip("\n").split("\n"):
            parts.append(("-- " + line).rstrip() if line else "--")
        parts.append("")
    parts.append(encode(value, 0))
    parts.append("")
    return "\n".join(parts)
