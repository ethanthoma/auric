from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

TYPE_ID = re.compile(r"[A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*\Z")  # Float_Array
VAR_ID = re.compile(r"[a-z][a-z0-9_]*\Z")  # snake_case


@dataclass(frozen=True)
class Top: ...


@dataclass(frozen=True)
class Bot: ...


@dataclass(frozen=True)
class Base:
    name: str


@dataclass(frozen=True)
class Union:
    left: "Shape"
    right: "Shape"


@dataclass(frozen=True)
class Inter:
    left: "Shape"
    right: "Shape"


@dataclass(frozen=True)
class Diff:
    left: "Shape"
    minus: str


Shape = Top | Bot | Base | Union | Inter | Diff

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


def leqS(a: Shape, b: Shape) -> bool:
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


@dataclass(frozen=True)
class TyVar:
    name: str


@dataclass(frozen=True)
class ShapeT:
    shape: Shape


@dataclass(frozen=True)
class RefT:
    shape: Shape
    pred: str


@dataclass(frozen=True)
class Arrow:
    param: "Type"
    ret: "Type"


@dataclass(frozen=True)
class Forall:
    tv: str
    body: "Type"


@dataclass(frozen=True)
class TyApp:
    head: "Type"
    arg: "Type"


Type = TyVar | ShapeT | RefT | Arrow | Forall | TyApp


def implies(phi: str, psi: str) -> bool:
    return psi.strip() == "true" or phi.strip() == psi.strip()


def subst(ty: Type, tv: str, r: Type) -> Type:
    if isinstance(ty, TyVar):
        return r if ty.name == tv else ty
    if isinstance(ty, ShapeT) | isinstance(ty, RefT):
        return ty
    if isinstance(ty, Arrow):
        return Arrow(subst(ty.param, tv, r), subst(ty.ret, tv, r))
    if isinstance(ty, Forall):
        return ty if ty.tv == tv else Forall(ty.tv, subst(ty.body, tv, r))
    if isinstance(ty, TyApp):
        return TyApp(subst(ty.head, tv, r), subst(ty.arg, tv, r))
    raise TypeError


def leqT(a: Type, b: Type) -> bool:
    if isinstance(a, TyVar) & isinstance(b, TyVar):
        return a.name == b.name
    if isinstance(a, ShapeT) & isinstance(b, ShapeT):
        return leqS(a.shape, b.shape)
    if isinstance(a, ShapeT) & isinstance(b, RefT):
        return leqS(a.shape, b.shape) & implies("true", b.pred)
    if isinstance(a, RefT) & isinstance(b, RefT):
        return leqS(a.shape, b.shape) & implies(a.pred, b.pred)
    if isinstance(a, Arrow) & isinstance(b, Arrow):
        return leqT(b.param, a.param) & leqT(a.ret, b.ret)
    if isinstance(a, Forall) & isinstance(b, Forall):
        return a == b  # invariant
    if isinstance(a, TyApp) & isinstance(b, TyApp):
        return leqT(a.head, b.head) & leqT(a.arg, b.arg)
    return False


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
class TyAbs:
    tv: str
    body: "Exp"


@dataclass
class TyAppE:
    fn: "Exp"
    arg_ty: Type


@dataclass
class Case:
    scr: Exp
    alts: Dict[str, tuple[List[str], Exp]]

    @property
    def scrut(self) -> Exp:
        return self.scr


Exp = Lam | Var | App | TyAbs | TyAppE | Case
Env = Dict[str, Any]


def eval_exp(e: Exp, env: Env):
    if isinstance(e, Var):
        return env[e.name]
    if isinstance(e, Lam):
        return lambda v: eval_exp(e.body, {**env, e.arg: v})
    if isinstance(e, TyAbs):
        return lambda _ty: eval_exp(e.body, env)
    if isinstance(e, App):
        return eval_exp(e.fn, env)(eval_exp(e.arg, env))
    if isinstance(e, TyAppE):
        return eval_exp(e.fn, env)(e.arg_ty)
    if isinstance(e, Case):
        tag, *flds = eval_exp(e.scr, env)
        names, body = e.alts[tag]
        new = env.copy()
        for n, v in zip(names, flds):
            if n != "_":
                new[n] = v
        return eval_exp(body, new)
    raise TypeError


_sym = r"[∪∩\\(){}]|->|:|=|\[|\]|Λ|\.|,|∀"
_tok = re.compile(
    rf"""\s*(
    {_sym} |
    [_A-Za-z][_0-9A-Za-z]* |
    \n | .
)""",
    re.VERBOSE,
)


def lex(src: str) -> List[str]:
    return [m.group(1) for m in _tok.finditer(src) if m.group(1).strip() != ""]


class Buf:
    def __init__(self, ts):
        self.ts, self.i = ts, 0

    def peek(self):
        return self.ts[self.i] if self.i < len(self.ts) else None

    def pop(self):
        if self.i >= len(self.ts):
            raise SyntaxError("unexpected <eof>")
        t = self.ts[self.i]
        self.i += 1
        return t


def parse_type(src: str) -> Type:
    b = Buf(lex(src))
    t = _ty(b)
    if b.peek() is not None:
        raise SyntaxError("junk in type")
    return t


def _ty(b: Buf, minp=0) -> Type:
    lhs = _ty_atom(b)
    # collect postfix type-application  (left-assoc)
    while True:
        nxt = b.peek()
        if nxt is None or nxt in {")", "]", "->", ",", "|", "}"}:
            break
        arg = _ty_atom(b)
        lhs = TyApp(lhs, arg)
    # right-assoc, lowest prec
    while b.peek() == "->" and minp <= 1:
        b.pop()
        rhs = _ty(b, 1)
        lhs = Arrow(lhs, rhs)
    return lhs


def _shape_expr(b: Buf, minp=0) -> Shape:
    lhs = _shape_atom(b)
    prec = lambda op: 1 if op == "∪" else 2 if op == "∩" else 0
    while b.peek() in {"∪", "∩"} and prec(b.peek()) >= minp:
        op = b.pop()
        rhs = _shape_expr(b, prec(op) + 1)
        lhs = Union(lhs, rhs) if op == "∪" else Inter(lhs, rhs)
    return lhs


def shape_of(ty: Type) -> Optional[Shape]:
    """Return the top-level Shape constructor of a type, if any."""
    if isinstance(ty, ShapeT):
        return ty.shape
    if isinstance(ty, TyApp):
        return shape_of(ty.head)
    if isinstance(ty, RefT):
        return ty.shape
    return None


def _shape_atom(b: Buf) -> Shape:
    t = b.pop()
    if t == "⊤":
        return Top()
    if t == "⊥":
        return Bot()
    if t == "(":
        s = _shape_expr(b)
        b.pop()
        return s
    if b.peek() == "\\":
        b.pop()
        return Diff(Base(t), b.pop())
    if TYPE_ID.match(t):
        return Base(t)
    raise SyntaxError("bad shape token " + t)


def split_app(t: Type) -> tuple[Shape, List[Type]] | None:
    """
    Decompose a fully-applied data type into

        (base_shape, [arg1, arg2, …])

    e.g.   List a       →  (Base("List"), [TyVar("a")])
           Map k v      →  (Base("Map"),  [k, v])
    """
    args: List[Type] = []
    while isinstance(t, TyApp):
        args.append(t.arg)
        t = t.head
    if isinstance(t, ShapeT):
        return (t.shape, list(reversed(args)))
    return None


def _ty_atom(b: Buf) -> Type:
    t = b.pop()
    if t in {"∀", "Lambda"}:
        tv = b.pop()
        if not VAR_ID.match(tv):
            raise SyntaxError("type var lower-case")
        if b.pop() != ".":
            raise SyntaxError("need '.' after ∀")
        return Forall(tv, _ty(b))
    if t == "(":
        inner = _ty(b)
        b.pop()
        return inner
    if t == "{":
        shp = _shape_expr(b)
        b.pop()
        pred = []
        while b.peek() != "}":
            pred.append(b.pop())
        b.pop()
        return RefT(shp, " ".join(pred))
    if TYPE_ID.match(t):
        return ShapeT(Base(t))
    if VAR_ID.match(t):
        return TyVar(t)
    raise SyntaxError("bad type token " + t)


def parse_expr(src: str) -> Exp:
    return _expr(Buf(lex(src)))


def _expr(b: Buf) -> Exp:
    lhs = _atom(b)
    while True:
        nxt = b.peek()
        if nxt and nxt not in {")", "]", "->", "of", "\n"} and nxt != "}":
            lhs = App(lhs, _atom(b))
            continue
        if nxt == "[":
            b.pop()
            tokens = []
            depth = 1
            while depth:
                tok = b.pop()
                if tok == "[":
                    depth += 1
                elif tok == "]":
                    depth -= 1
                if depth:
                    tokens.append(tok)
            lhs = TyAppE(lhs, parse_type(" ".join(tokens)))
            continue
        break
    return lhs


def _atom(b: Buf) -> Exp:
    t = b.pop()
    if t == "(":
        e = _expr(b)
        b.pop()
        return e
    if t == "Λ":
        tv = b.pop()
        b.pop()
        return TyAbs(tv, _expr(b))
    if t == "case":
        scr = _expr(b)
        b.pop()
        alts = {}
        while True:
            while b.peek() == "\n":
                b.pop()
            if b.peek() is None:
                break
            tag = b.pop()
            binds = []
            while b.peek() != "->":
                binds.append(b.pop())
            b.pop()
            rhs = []
            while b.peek() not in {None, "\n"}:
                rhs.append(b.pop())
            if b.peek() == "\n":
                b.pop()
            alts[tag] = (binds, _expr(Buf(rhs)))
            if b.peek() is None:
                break
        return Case(scr, alts)
    if not VAR_ID.match(t):
        raise SyntaxError("term ids snake_case")
    return Var(t)


def parse(src: str) -> tuple[Dict[str, Type], Dict[str, Exp]]:
    """
    Collects:
        - optional signatures   name : Type
        - exactly one definition per name (but the RHS may span many lines)

    A definition head may be
        foo[a, b] x y =
    which means:
        generic parameters  [a, b]   then   value parameters x y
    """
    sigs: Dict[str, Type] = {}
    defs: Dict[str, Exp] = {}

    lines = src.strip("\n").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if ":" in line and "=" not in line:
            name, ty_src = map(str.strip, line.split(":", 1))
            sigs[name] = parse_type(ty_src)
            i += 1
            continue

        if "=" in line:
            lhs, rhs0 = map(str.strip, line.split("=", 1))

            head_parts = lhs.split()
            head_tok = head_parts[0]

            m = re.fullmatch(r"([a-z][a-z0-9_]*)(?:\[(.*)\])?", head_tok)
            if not m:
                raise SyntaxError(f"invalid definition head: {head_tok}")

            name = m.group(1)
            gen_params = (
                [p.strip() for p in m.group(2).split(",")] if m.group(2) else []
            )
            val_params = head_parts[1:]

            rhs_lines: List[str] = [rhs0] if rhs0 else []
            i += 1
            while i < len(lines) and lines[i][:1] in " \t":
                rhs_lines.append(lines[i].lstrip())
                i += 1
            body_src = "\n".join(rhs_lines)

            body: Exp = parse_expr(body_src)
            for vp in reversed(val_params):
                body = Lam(vp, body)
            for gp in reversed(gen_params):
                body = TyAbs(gp, body)

            defs[name] = body
            continue

        raise SyntaxError(f"unrecognised top-level line: {line}")

    return sigs, defs


def check(g: Dict[str, Type], e: Exp, t: Type) -> None:
    if isinstance(e, Lam) and isinstance(t, Arrow):
        check({**g, e.arg: t.param}, e.body, t.ret)
        return
    if isinstance(e, TyAbs) and isinstance(t, Forall):
        check(g, e.body, t.body)
        return
    actual = synth(g, e)
    if not leqT(actual, t):
        raise TypeError(f"wanted {t}, got {actual}")


def synth(g: Dict[str, Type], e: Exp) -> Type:
    if isinstance(e, Var):
        return g[e.name]

    if isinstance(e, App):
        fn_ty = synth(g, e.fn)
        if not isinstance(fn_ty, Arrow):
            raise TypeError("apply non-function")
        check(g, e.arg, fn_ty.param)
        return fn_ty.ret

    if isinstance(e, TyAppE):
        fn_ty = synth(g, e.fn)
        if not isinstance(fn_ty, Forall):
            raise TypeError("type-apply non-generic value")
        return subst(fn_ty.body, fn_ty.tv, e.arg_ty)

    if isinstance(e, Case):
        scr_ty = synth(g, e.scrut)
        scr_shape = shape_of(scr_ty)
        if scr_shape is None:
            raise TypeError("case scrutinee must have a data-constructor shape")

        res_ty: Optional[Type] = None
        for tag, (binds, rhs) in e.alts.items():
            if tag not in ctors(scr_shape):
                raise TypeError(f"constructor {tag} not in {scr_shape}")

            loc = g.copy()
            if tag == "cons":
                base, *rest = binds
                shape_info = split_app(scr_ty)
                if shape_info:
                    base_shape, [elem_ty] = shape_info
                    if isinstance(base_shape, Base) and base_shape.name == "List":
                        if base != "_":
                            loc[base] = elem_ty
                        if rest and rest[0] != "_":
                            loc[rest[0]] = scr_ty

            for n in binds:
                loc.setdefault(n, ShapeT(Top()))

            branch_ty = synth(loc, rhs)

            if res_ty is None:
                res_ty = branch_ty
            elif branch_ty != res_ty:
                raise TypeError("branch result types differ")

        assert res_ty is not None
        return res_ty

    raise TypeError("need annotation")


def elaborate(src: str) -> Dict[str, Exp]:
    return parse(src)[1]


def type_of(src: str, _env: Env) -> Dict[str, Type]:
    sigs, defs = parse(src)
    gamma = sigs.copy()
    for n, e in defs.items():
        if n in sigs:
            check(gamma, e, sigs[n])
            gamma[n] = sigs[n]
        else:
            gamma[n] = synth(gamma, e)
    return {k: gamma[k] for k in defs}


def evaluate(core: Dict[str, Exp], env: Env) -> Dict[str, Any]:
    return {k: eval_exp(v, env) for k, v in core.items()}
