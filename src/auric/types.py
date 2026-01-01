"""Type system operations for Auric."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from auric.ast import (
    Arrow,
    Base,
    Bot,
    DepApp,
    Diff,
    Forall,
    ForallIdx,
    IdxSucc,
    IdxUnknown,
    IdxVar,
    IdxZero,
    Index,
    Inter,
    RecordT,
    RefT,
    Shape,
    ShapeT,
    Top,
    TyApp,
    TyVar,
    Type,
    Union,
)


# ============================================================
# Shape operations
# ============================================================

# Constructor mapping for built-in types
CTOR: dict[str, tuple[str, ...]] = {
    "@Nat": ("@zero", "@succ"),
    "@Bool": ("@true", "@false"),
    "List": ("nil", "cons"),
    # Vec is NOT a constructor-based type - it's a dependent record
}

# Primitive types (no constructors)
PRIMITIVES: set[str] = {
    # Unsigned integers
    "u8", "u16", "u32", "u64",
    # Signed integers
    "i8", "i16", "i32", "i64",
    # Floating point
    "f32", "f64",
    # Character (alias for u8)
    "char",
}


def ctors(s: Shape) -> set[str]:
    """Get all valid constructors for a shape."""
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


def is_subtype_shape(a: Shape, b: Shape) -> bool:
    """Check if shape a is a subtype of shape b."""
    if isinstance(a, Bot) or isinstance(b, Top):
        return True
    if isinstance(a, Top) or isinstance(b, Bot):
        return False
    if isinstance(a, Base) and isinstance(b, Base):
        return a.name == b.name
    if isinstance(a, Union):
        return is_subtype_shape(a.left, b) and is_subtype_shape(a.right, b)
    if isinstance(b, Inter):
        return is_subtype_shape(a, b.left) and is_subtype_shape(a, b.right)
    if isinstance(a, Inter):
        return is_subtype_shape(a.left, b) or is_subtype_shape(a.right, b)
    if isinstance(b, Union):
        return is_subtype_shape(a, b.left) or is_subtype_shape(a, b.right)
    return False


# ============================================================
# Type operations
# ============================================================


def normalize_type(t: Type) -> Type:
    """Normalize a type by expanding type-level macros (e.g., Vec to RecordT)."""
    from auric.macros import expand_type_macros
    return expand_type_macros(t)


def is_subtype(a: Type, b: Type) -> bool:
    """Check if type a is a subtype of type b."""
    # Normalize Vec types to RecordT
    a = normalize_type(a)
    b = normalize_type(b)

    if a == b:
        return True
    # Fresh type variables (starting with ?) are flexible
    if isinstance(b, TyVar) and b.name.startswith("?"):
        return True  # Any type can match a fresh tyvar
    if isinstance(a, TyVar) and a.name.startswith("?"):
        return True  # Fresh tyvar can match any type
    if isinstance(a, ShapeT) and isinstance(b, ShapeT):
        return is_subtype_shape(a.shape, b.shape)
    if isinstance(a, RefT) and isinstance(b, RefT):
        return is_subtype_shape(a.shape, b.shape)
    if isinstance(a, Arrow) and isinstance(b, Arrow):
        # Contravariant in parameter, covariant in return
        return is_subtype(b.param, a.param) and is_subtype(a.ret, b.ret)
    if isinstance(a, Forall) and isinstance(b, Forall):
        return a == b  # invariant
    if isinstance(a, TyApp) and isinstance(b, TyApp):
        return is_subtype(a.head, b.head) and is_subtype(a.arg, b.arg)
    if isinstance(a, DepApp) and isinstance(b, DepApp):
        # Vec[T, n] <: Vec[T, _] (forget length)
        # Vec[T, n] <: Vec[U, m] if T <: U and n = m
        if a.base != b.base:
            return False
        # Check type arguments
        if len(a.type_args) != len(b.type_args):
            return False
        if not all(is_subtype(ta, tb) for ta, tb in zip(a.type_args, b.type_args)):
            return False
        # Check index arguments (unknown matches anything)
        if len(a.index_args) != len(b.index_args):
            return False
        return all(index_equal(ia, ib) for ia, ib in zip(a.index_args, b.index_args))
    if isinstance(a, RecordT) and isinstance(b, RecordT):
        # Structural subtyping for records:
        # - Width: a can have more fields than b
        # - Depth: field types must be subtypes
        # a <: b if a has all fields of b with compatible types
        for field_name, field_type_b in b.fields.items():
            if field_name not in a.fields:
                return False  # Missing field
            if not is_subtype(a.fields[field_name], field_type_b):
                return False  # Incompatible field type
        return True
    return False


def subst(t: Type, tv: str, s: Type) -> Type:
    """Substitute type variable tv with type s in type t."""
    if isinstance(t, TyVar):
        return s if t.name == tv else t
    if isinstance(t, Arrow):
        return Arrow(subst(t.param, tv, s), subst(t.ret, tv, s), t.effects)
    if isinstance(t, Forall):
        # Shadowing: don't substitute in body if variable shadows
        return t if t.tv == tv else Forall(t.tv, subst(t.body, tv, s))
    if isinstance(t, ForallIdx):
        # Don't substitute type vars in index quantification
        return ForallIdx(t.idx_var, t.idx_kind, subst(t.body, tv, s))
    if isinstance(t, TyApp):
        return TyApp(subst(t.head, tv, s), subst(t.arg, tv, s))
    if isinstance(t, DepApp):
        return DepApp(
            t.base,
            [subst(ty, tv, s) for ty in t.type_args],
            t.index_args  # Index args unchanged by type substitution
        )
    if isinstance(t, RecordT):
        return RecordT({
            field_name: subst(field_ty, tv, s)
            for field_name, field_ty in t.fields.items()
        })
    return t  # ShapeT, RefT, etc. are unchanged


def shape_of(ty: Type) -> Optional[Shape]:
    """Return the top-level Shape constructor of a type, if any."""
    from auric.ast import DepApp

    if isinstance(ty, ShapeT):
        return ty.shape
    if isinstance(ty, TyApp):
        return shape_of(ty.head)
    if isinstance(ty, RefT):
        return ty.shape
    if isinstance(ty, DepApp):
        return Base(ty.base)
    return None


def split_app(t: Type) -> tuple[Shape, List[Type]] | None:
    """
    Decompose a fully-applied data type into (base_shape, [arg1, arg2, ...])

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


# ============================================================
# Dependent Types: Index Operations
# ============================================================


def index_equal(a: Index, b: Index) -> bool:
    """Check if two indices are equal.

    Unknown (_) matches anything.
    """
    if isinstance(a, IdxUnknown) or isinstance(b, IdxUnknown):
        return True  # Unknown matches anything
    if isinstance(a, IdxZero) and isinstance(b, IdxZero):
        return True
    if isinstance(a, IdxSucc) and isinstance(b, IdxSucc):
        return index_equal(a.pred, b.pred)
    if isinstance(a, IdxVar) and isinstance(b, IdxVar):
        return a.name == b.name
    return False


def index_to_nat(idx: Index) -> int | None:
    """Convert concrete index to natural number, if possible."""
    if isinstance(idx, IdxZero):
        return 0
    if isinstance(idx, IdxSucc):
        pred_val = index_to_nat(idx.pred)
        return None if pred_val is None else pred_val + 1
    return None  # Variable or unknown


def nat_to_index(n: int) -> Index:
    """Convert natural number to index."""
    idx: Index = IdxZero()
    for _ in range(n):
        idx = IdxSucc(idx)
    return idx


def subst_index(idx: Index, var: str, replacement: Index) -> Index:
    """Substitute index variable with another index."""
    if isinstance(idx, IdxVar):
        return replacement if idx.name == var else idx
    if isinstance(idx, IdxSucc):
        return IdxSucc(subst_index(idx.pred, var, replacement))
    return idx  # Zero or Unknown unchanged
