from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Shape: ...


@dataclass(frozen=True)
class Top(Shape): ...


@dataclass(frozen=True)
class Bot(Shape): ...


@dataclass(frozen=True)
class Base(Shape):
    name: str


@dataclass(frozen=True)
class Union(Shape):
    left: Shape
    right: Shape


@dataclass(frozen=True)
class Inter(Shape):
    left: Shape
    right: Shape


@dataclass(frozen=True)
class Diff(Shape):
    left: Shape
    minus: str  # left \ constructor


@dataclass(frozen=True)
class Type: ...


@dataclass(frozen=True)
class ShapeT(Type):
    shape: Shape


@dataclass(frozen=True)
class RefT(Type):
    shape: Shape
    pred: str


CTOR: dict[str, tuple[str, ...]] = {
    "Nat": ("zero", "succ"),
    "Bool": ("true", "false"),
    "List": ("nil", "cons"),
}


def ctors(s: Shape) -> set[str]:
    if isinstance(s, Base):
        return set(CTOR.get(s.name, ()))
    if isinstance(s, Union):
        return ctors(s.left) | ctors(s.right)
    if isinstance(s, Inter):
        return ctors(s.left) & ctors(s.right)
    if isinstance(s, Diff):
        c = ctors(s.left)
        c.discard(s.minus)
        return c
    return set()


def leqS(a, b) -> bool:
    if isinstance(a, Bot) or isinstance(b, Top):
        return True
    if isinstance(a, Top) or isinstance(b, Bot):
        return False
    if isinstance(a, Base) and isinstance(b, Base):
        return a.name == b.name
    if isinstance(a, Union):
        return leqS(a.left, b) and leqS(a.right, b)
    if isinstance(b, Inter):
        return leqS(a, b.left) and leqS(a, b.right)
    if isinstance(b, Union):
        return leqS(a, b.left) or leqS(a, b.right)
    if isinstance(a, Inter):
        return leqS(a.left, b) or leqS(a.right, b)
    if isinstance(a, Diff):
        return leqS(a.left, b)
    return False


def implies(phi: str, psi: str) -> bool:
    return psi.strip() == "true" or phi.strip() == psi.strip()


def leqT(a: Type, b: Type) -> bool:
    if not leqS(a.shape, b.shape):
        return False
    if isinstance(a, RefT) and isinstance(b, RefT):
        return implies(a.pred, b.pred)
    if isinstance(a, ShapeT) and isinstance(b, RefT):
        return implies("true", b.pred)
    return True


@dataclass
class Lam:
    arg: str
    body: "Exp"


@dataclass
class Var:
    name: str


@dataclass
class App:
    fn: "Exp"
    arg: "Exp"


@dataclass
class Case:
    scrut: "Exp"
    alts: Dict[str, tuple[List[str], "Exp"]]  # tag → (bound names, body)


Exp = Lam | Var | App | Case
Env = Dict[str, Any]


def eval_exp(e: Exp, env: Env):
    if isinstance(e, Var):
        return env[e.name]

    if isinstance(e, Lam):
        return lambda v: eval_exp(e.body, {**env, e.arg: v})

    if isinstance(e, App):
        return eval_exp(e.fn, env)(eval_exp(e.arg, env))

    if isinstance(e, Case):
        scr_val = eval_exp(e.scrut, env)  # ("cons", h, t)
        tag, *fields = scr_val
        arg_names, body = e.alts[tag]
        newenv = env.copy()
        for n, v in zip(arg_names, fields):
            if n != "_":  # ignore wildcard
                newenv[n] = v
        return eval_exp(body, newenv)


_tok = re.compile(
    r"""\s*(
        -> | \(|\) |
        case | of |
        [_A-Za-z][_0-9A-Za-z]* |
        \n |
        .          # catch-all for error msg
    )""",
    re.VERBOSE,
)


def _lex(src: str) -> list[str]:
    ts = [m.group(1) for m in _tok.finditer(src)]
    return [t for t in ts if t.strip() != ""]


class _Buf:
    def __init__(self, ts: list[str]):
        self.ts, self.i = ts, 0

    def peek(self) -> Optional[str]:
        return self.ts[self.i] if self.i < len(self.ts) else None

    def pop(self) -> str:
        t = self.peek()
        if t is None:
            raise SyntaxError("unexpected <eof>")
        self.i += 1
        return t


def _expr(b: _Buf) -> Exp:
    lhs = _atom(b)
    while True:
        nxt = b.peek()
        if nxt is None or nxt in {")", "\n", "of", "->"}:
            break
        rhs = _atom(b)
        lhs = App(lhs, rhs)
    return lhs


def _atom(b: _Buf) -> Exp:
    t = b.pop()
    if t == "(":
        e = _expr(b)
        assert b.pop() == ")", "missing ')'"
        return e

    if t == "case":
        scr = _expr(b)
        assert b.pop() == "of"
        alts: Dict[str, tuple[List[str], Exp]] = {}
        while True:
            while b.peek() == "\n":
                b.pop()
            if b.peek() is None:
                break
            tag = b.pop()  # constructor
            names: list[str] = []
            while b.peek() not in {"->"}:
                names.append(b.pop())
            b.pop()  # ->
            rhs_tokens: list[str] = []
            while b.peek() not in {None, "\n"}:
                rhs_tokens.append(b.pop())
            if b.peek() == "\n":
                b.pop()
            rhs_expr = _expr(_Buf(rhs_tokens)) if rhs_tokens else Var("()")
            alts[tag] = (names, rhs_expr)
            if b.peek() is None:
                break
        return Case(scr, alts)

    # identifier
    return Var(t)


def parse_expr(src: str) -> Exp:
    return _expr(_Buf(_lex(src)))


def _finish_def(lhs: str, rhs_lines: List[str], fns: Dict[str, Exp]) -> None:
    name, *args = lhs.split()
    body_src = "\n".join(rhs_lines).strip()
    body = parse_expr(body_src)
    e: Exp = body
    for a in reversed(args):
        e = Lam(a, e)
    fns[name] = e


def parse(src: str) -> Dict[str, Exp]:
    fns: Dict[str, Exp] = {}
    lhs: Optional[str] = None
    rhs_acc: List[str] = []

    lines = src.strip("\n").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():  # blank
            i += 1
            continue

        if "=" in line and line.lstrip() == line:  # new def
            if lhs is not None:
                _finish_def(lhs, rhs_acc, fns)
            lhs, rhs_start = map(str.strip, line.split("=", 1))
            rhs_acc = [rhs_start] if rhs_start else []
            i += 1
            while i < len(lines) and lines[i][:1] in " \t":
                rhs_acc.append(lines[i].lstrip())
                i += 1
        else:
            raise SyntaxError(f"unexpected line without '=': {line}")

    if lhs is not None:
        _finish_def(lhs, rhs_acc, fns)
    return fns


def type_of(src: str, _: Env) -> Dict[str, Type]:
    return {n: ShapeT(Top()) for n in parse(src)}


def elaborate(src: str):
    return parse(src)


def evaluate(core: Dict[str, Exp], env: Env):
    return {k: eval_exp(v, env) for k, v in core.items()}
