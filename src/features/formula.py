"""A small tokenizer and parser for Seeq Formula expressions, written to audit the walkthroughs.

It does not evaluate anything. It finds what an expression *uses*:
  * references   $flow, $pumpRunning
  * calls        method calls ($x.valueSearch(...)) and plain function calls (isGreaterThan(...))
  * literals     numbers (with an optional unit, 0.5 m^3/h), durations (5min, 1day), strings ('Production')

Each call gets a *shape*: its name and the kind of each top-level argument, e.g.
    $flow.valueSearch(1day, isGreaterThan(0.5 m^3/h))  ->  valueSearch(dur,call)  and  isGreaterThan(num)
The label audit compares shapes, not exact text, so the same syntax used on different signals is recognised.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DURATION_UNITS = ("ms", "s", "sec", "min", "h", "hr", "hour", "hours", "d", "day", "days", "wk", "week", "weeks",
                  "mo", "month", "months", "y", "yr", "year", "years")
_TOKEN = re.compile(r"""
    (?P<str>'[^']*'|"[^"]*")
  | (?P<ref>\$[A-Za-z_][A-Za-z0-9_]*)
  | (?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>\*\*|==|!=|<=|>=|&&|\|\||[-+*/^%<>!(),.\[\]{}:=?])
  | (?P<ws>\s+)
""", re.X)


class ParseError(ValueError):
    pass


@dataclass
class Call:
    name: str
    method: bool                 # True for $x.name(...), False for name(...)
    args: list = field(default_factory=list)   # kinds of the top-level arguments

    @property
    def shape(self) -> str:
        return f"{self.name}({','.join(self.args)})"


@dataclass
class Parsed:
    expression: str
    refs: list
    calls: list
    numbers: list                # numeric literals that are not durations
    durations: list
    strings: list
    is_formula: bool = True      # False when the text is not Seeq Formula (e.g. Python SDK code)

    @property
    def shapes(self) -> list:
        return sorted({c.shape for c in self.calls})


def tokenize(text: str) -> list:
    toks, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ParseError(f"unexpected character {text[pos]!r} at {pos}")
        kind = m.lastgroup
        if kind != "ws":
            toks.append((kind, m.group()))
        pos = m.end()
    # merge "<number> <duration unit>" and "<number><unit>" into one duration token, and number + engineering unit
    out, i = [], 0
    while i < len(toks):
        k, v = toks[i]
        if k == "num" and i + 1 < len(toks) and toks[i + 1][0] == "name" and toks[i + 1][1] in DURATION_UNITS:
            out.append(("dur", v + toks[i + 1][1]))
            i += 2
            continue
        if k == "num" and i + 1 < len(toks) and toks[i + 1][0] == "name" and toks[i + 1][1] not in DURATION_UNITS \
                and (i + 2 >= len(toks) or toks[i + 2][1] != "("):
            # engineering unit such as 0.5 m^3/h or 4.5 mm/s: swallow unit tokens up to the next , or )
            j = i + 1
            while j < len(toks) and toks[j][1] not in (",", ")"):
                j += 1
            out.append(("num", v))
            i = j
            continue
        out.append((k, v))
        i += 1
    return out


def _arg_kind(arg: list) -> str:
    """Kind of one top-level argument, from its tokens."""
    if not arg:
        return "empty"
    kinds = [k for k, _ in arg]
    if len(arg) == 1:
        return {"dur": "dur", "num": "num", "str": "str", "ref": "ref", "name": "name"}.get(kinds[0], "expr")
    if kinds[0] == "op" and arg[0][1] == "-" and len(arg) == 2 and kinds[1] in ("num", "dur"):
        return kinds[1]
    if kinds[0] == "name" and len(arg) > 1 and arg[1][1] == "(" and arg[-1][1] == ")":
        depth = 0
        for k, v in arg[1:]:
            depth += v == "(" and k == "op"
            depth -= v == ")" and k == "op"
        if depth == 0:
            return "call"
    return "expr"


def parse(expression: str) -> Parsed:
    text = (expression or "").strip()
    if not text:
        return Parsed(text, [], [], [], [], [], is_formula=False)
    if re.match(r"^\s*(spy\.|import |from |SELECT |def )", text):
        return Parsed(text, [], [], [], [], [], is_formula=False)
    toks = tokenize(text)
    if any(k == "op" and v in ("{", "}", ":") for k, v in toks):
        return Parsed(text, [], [], [], [], [], is_formula=False)
    calls = []
    for i, (k, v) in enumerate(toks):
        if k == "name" and i + 1 < len(toks) and toks[i + 1] == ("op", "("):
            method = i > 0 and toks[i - 1] == ("op", ".")
            # collect top-level args
            depth, args, cur, j = 0, [], [], i + 1
            while j < len(toks):
                tk = toks[j]
                if tk == ("op", "("):
                    depth += 1
                    if depth == 1:
                        j += 1
                        continue
                elif tk == ("op", ")"):
                    depth -= 1
                    if depth == 0:
                        break
                if depth == 1 and tk == ("op", ","):
                    args.append(cur)
                    cur = []
                else:
                    cur.append(tk)
                j += 1
            if depth != 0:
                raise ParseError(f"unbalanced parentheses after {v}")
            if cur or args:
                args.append(cur)
            calls.append(Call(v, method, [_arg_kind(a) for a in args]))
    return Parsed(text, sorted({v for k, v in toks if k == "ref"}), calls,
                  [float(v) for k, v in toks if k == "num"], [v for k, v in toks if k == "dur"],
                  [v for k, v in toks if k == "str"])
