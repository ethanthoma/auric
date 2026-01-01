"""Abstract Syntax Tree and Type definitions for Auric."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# ============================================================
# Type System: Shapes
# ============================================================


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


# ============================================================
# Type System: Types
# ============================================================


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
    effects: frozenset[str] = frozenset()  # Set of effect names


@dataclass(frozen=True)
class Forall:
    tv: str
    body: "Type"


@dataclass(frozen=True)
class TyApp:
    head: "Type"
    arg: "Type"


# ============================================================
# Dependent Types: Type-level Indices
# ============================================================


@dataclass(frozen=True)
class IdxVar:
    """Type-level variable: n in Vec[T, n]"""
    name: str


@dataclass(frozen=True)
class IdxZero:
    """Type-level zero"""
    pass


@dataclass(frozen=True)
class IdxSucc:
    """Type-level successor: succ(n)"""
    pred: "Index"


@dataclass(frozen=True)
class IdxUnknown:
    """Unknown index: _ for existential types"""
    pass


Index = IdxVar | IdxZero | IdxSucc | IdxUnknown


# ============================================================
# Dependent Type Application
# ============================================================


@dataclass(frozen=True)
class DepApp:
    """Dependent type application: Vec[T, n]

    Examples:
        Vec[Int, 5]    -> DepApp("Vec", [ShapeT(Int)], [IdxSucc(IdxSucc(...))])
        Vec[T, n]      -> DepApp("Vec", [TyVar("T")], [IdxVar("n")])
        Vec[Int, _]    -> DepApp("Vec", [ShapeT(Int)], [IdxUnknown()])
    """
    base: str                   # "Vec"
    type_args: List["Type"]     # Type parameters [T]
    index_args: List[Index]     # Index parameters [n]


@dataclass(frozen=True)
class ForallIdx:
    """Index quantification: forall n: Nat. Body

    Example:
        fn map[T, U, n](v: Vec[T, n], ...) -> ...
        Type: ForallIdx("n", "Nat", Arrow(...))
    """
    idx_var: str      # "n"
    idx_kind: str     # "Nat" (only Nat for now)
    body: "Type"


@dataclass(frozen=True)
class RecordT:
    """Record type: .{ x: Int, y: String } or .{ _0: Int, _1: String }

    Examples:
        .{ x: Int, y: String }  -> RecordT({"x": ShapeT(Base("Int")), "y": ShapeT(Base("String"))})
        .{ Int, String }        -> RecordT({"_0": ShapeT(Base("Int")), "_1": ShapeT(Base("String"))})
    """
    fields: Dict[str, "Type"]  # field_name -> field_type


Type = TyVar | ShapeT | RefT | Arrow | Forall | TyApp | DepApp | ForallIdx | RecordT
Env = Dict[str, any]


# ============================================================
# Region information (for memory management)
# ============================================================


@dataclass(frozen=True)
class Region:
    """Region identifier for value lifetimes.

    Regions represent scopes where values are allocated and deallocated.
    - "local": Stack-allocated in current scope (zero overhead)
    - "param": Borrowed from caller's region
    - "caller": Returned to caller's scope (destination passing)
    - "heap": Explicitly marked as RC-managed (escapes region)
    - "<var>": Polymorphic region bound to a type variable
    """

    name: str

    def is_local(self) -> bool:
        """Check if this is a local region (stack-allocated)."""
        return self.name == "local"

    def is_param(self) -> bool:
        """Check if this is a parameter region (borrowed)."""
        return self.name == "param"

    def is_caller(self) -> bool:
        """Check if this is returned to caller's region."""
        return self.name == "caller"

    def is_heap(self) -> bool:
        """Check if this is heap-allocated (RC-managed)."""
        return self.name == "heap"


# ============================================================
# Expression/AST nodes
# ============================================================


@dataclass
class Lam:
    params: List[str]  # Multiple parameters: (x, y, z) => body
    body: "Exp"


@dataclass
class Var:
    name: str


@dataclass
class App:
    fn: "Exp"
    args: List["Exp"]  # Multiple arguments: f(x, y, z)


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


@dataclass
class Perform:
    """Invoke an effect: Print("hello") or Read()"""

    effect_name: str
    args: "Exp"  # Argument to the effect


@dataclass
class Handle:
    """Handle effects: handle expr { Effect(p) -> body; ... resume() }"""

    body: "Exp"  # Expression that may perform effects
    handlers: Dict[str, tuple[List[str], Exp]]  # effect_name -> (patterns, handler_body)


@dataclass
class Record:
    """Record literal: .{ x = 1, y = 2 } or .{ 1, 2 }

    Examples:
        .{ x = 1, y = 2 }  -> Record({"x": Var("1"), "y": Var("2")})
        .{ 1, 2 }          -> Record({"_0": Var("1"), "_1": Var("2")})
    """
    fields: Dict[str, "Exp"]  # field_name -> field_value


@dataclass
class Spread:
    """Spread operator for record merging (comptime-only): ..record

    Used to merge records at compile-time. For indexed fields (_0, _1, ...),
    fields are automatically reindexed.

    Examples:
        { x = 1, ..rest }              -> Merge named fields
        { _0 = 'a', ..({ _0 = 'b' }) } -> Reindex: { _0 = 'a', _1 = 'b' }

    Runtime restriction: Spread only works at comptime (in macros).
    At runtime, all record fields must be explicit to preserve totality.
    """
    record: "Exp"  # Expression that evaluates to a record


@dataclass
class FieldAccess:
    """Field access: record.field

    Examples:
        rec.x      -> FieldAccess(Var("rec"), "x")
        rec._0     -> FieldAccess(Var("rec"), "_0")
    """
    record: "Exp"
    field: str


@dataclass
class MacroInvocation:
    """Macro invocation to be expanded before type checking

    Examples:
        vec[0]           -> MacroInvocation("index", [Var("vec"), Var("0")])
        "hello"          -> MacroInvocation("string", [StringLit("hello")])
        [1, 2, 3]        -> MacroInvocation("list", [Var("1"), Var("2"), Var("3")])
    """
    macro_name: str
    args: List["Exp"]


@dataclass
class For:
    """For loop: for i = ..expr { body }

    Examples:
        for i = ..myList { print(i) }
        for x = ..items { x.process() }
    """
    binding: str        # Variable name bound to each element (e.g., "i")
    iterable: "Exp"     # Expression to iterate over (e.g., myList)
    body: "Exp"         # Body expression executed for each element


@dataclass
class Const:
    """Constant literal: 42, 3.14, 'a', @true

    Replaces: IntLit, FloatLit, CharLit, BoolLit
    Unifies all constant values under one node with explicit type.

    Examples:
        42         -> Const(42, ShapeT(Base("i64")))
        42u8       -> Const(42, ShapeT(Base("u8")))
        3.14       -> Const(3.14, ShapeT(Base("f64")))
        3.14f32    -> Const(3.14, ShapeT(Base("f32")))
        'a'        -> Const('a', ShapeT(Base("u8")))
        @true      -> Const(True, ShapeT(Base("bool")))
        @false     -> Const(False, ShapeT(Base("bool")))
    """
    value: any          # Python int, float, str (single char), or bool
    ty: Type            # Explicit type: ShapeT(Base("i64")), etc.


@dataclass
class If:
    """If expression (legacy - now implemented as macro that desugars to Case)

    Modern syntax uses the if macro from std/builtins:
        if(x > 0, 1, -1)

    This desugars to Case with @true/@false patterns.
    """
    cond: "Exp"
    then_branch: "Exp"
    else_branch: "Exp"


@dataclass
class Seq:
    """Sequence of expressions: { expr1; expr2; expr3 }

    Examples:
        { print("a"); print("b"); 42 }
    """
    exprs: List["Exp"]


@dataclass
class MacroDef:
    """Macro definition: macro name = (params) => body

    Examples:
        macro unless = (cond, body) => if(not(cond), body, ())
    """
    name: str
    params: List[str]
    body: "Exp"


@dataclass
class Let:
    """Let binding: let name = value; body

    All let bindings are recursive by default - the value can reference the name.
    Totality (termination) must be ensured by the programmer.

    Examples:
        let x = 42; x + 1
        let factorial = (n) => n => {
          zero -> succ(zero);
          succ(m) -> mul(n, factorial(m));
        };
        factorial(5)
    """
    name: str
    value: "Exp"
    body: "Exp"


Exp = Lam | Var | App | TyAbs | TyAppE | Case | Perform | Handle | Record | Spread | FieldAccess | MacroInvocation | For | Const | If | Seq | MacroDef | Let
