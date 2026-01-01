# Dependent Types Design for Auric

## Goals

1. Support `Vec[T, n]` where `n: Nat` is a compile-time or runtime length
2. Allow `_` for unknown length (existential types)
3. Preserve totality through structural recursion
4. Enable type-level reasoning about lengths

## Type System Extension

### Index Language (Type-level Values)

```auric
// Indices are Nat values at the type level
Index ::=
    | n              // Index variable
    | zero           // Zero
    | succ(Index)    // Successor
    | _              // Unknown (existential)
```

### Dependent Types

```auric
// Vec parameterized by type and index
type Vec[T, n: Nat | _] where
    | Empty: Vec[T, zero]
    | Cons(head: T, tail: Vec[T, n]): Vec[T, succ(n)]

// Examples:
Vec[Int, zero]           // Empty vector
Vec[Int, succ(succ(zero))]  // Vector of length 2
Vec[Int, n]              // Vector of length n (polymorphic)
Vec[Int, _]              // Vector of unknown length
```

### Quantification

```auric
// Functions quantify over indices
fn map[T: Type, U: Type, n: Nat](v: Vec[T, n], f: T -> U) -> Vec[U, n]

// Type:
forall T: Type.
forall U: Type.
forall n: Nat.
  Vec[T, n] -> (T -> U) -> Vec[U, n]
```

## AST Representation

### New AST Nodes

```python
# ast.py additions

# Indices
@dataclass(frozen=True)
class IdxVar:
    name: str

@dataclass(frozen=True)
class IdxZero:
    pass

@dataclass(frozen=True)
class IdxSucc:
    pred: "Index"

@dataclass(frozen=True)
class IdxUnknown:
    """The _ index for existential types"""
    pass

Index = IdxVar | IdxZero | IdxSucc | IdxUnknown

# Dependent type application
@dataclass(frozen=True)
class DepApp:
    """Vec[T, n]"""
    base: str                   # "Vec"
    type_args: List[Type]       # [T]
    index_args: List[Index]     # [n]

# Index quantification
@dataclass(frozen=True)
class ForallIdx:
    """forall n: Nat. Body"""
    idx_var: str      # "n"
    idx_kind: str     # "Nat"
    body: Type

# Update Type union
Type = TyVar | ShapeT | RefT | Arrow | Forall | TyApp | DepApp | ForallIdx
```

## Type Checking

### Subtyping Rules

```
Vec[T, n] <: Vec[T, _]           // Forget length
Vec[T, succ(n)] <: Vec[T, _]     // Forget length
Vec[T, zero] <: Vec[T, _]        // Forget length
```

### Index Equality

```python
def index_equal(a: Index, b: Index) -> bool:
    """Check if two indices are equal."""
    if isinstance(a, IdxZero) and isinstance(b, IdxZero):
        return True
    if isinstance(a, IdxSucc) and isinstance(b, IdxSucc):
        return index_equal(a.pred, b.pred)
    if isinstance(a, IdxVar) and isinstance(b, IdxVar):
        return a.name == b.name
    if isinstance(a, IdxUnknown) or isinstance(b, IdxUnknown):
        return True  # Unknown matches anything
    return False
```

### Type Checking Vec

```python
def synth_vec_cons(gamma: Context, head: Exp, tail: Exp) -> Type:
    """Type check Cons(head, tail)"""
    head_ty = synth(gamma, head)
    tail_ty = synth(gamma, tail)

    # tail must be Vec[T, n]
    if not isinstance(tail_ty, DepApp) or tail_ty.base != "Vec":
        raise TypeError(f"Cons tail must be Vec, got {tail_ty}")

    elem_ty = tail_ty.type_args[0]
    tail_len = tail_ty.index_args[0]

    # head must match elem_ty
    if not is_subtype(head_ty, elem_ty):
        raise TypeError(f"Cons head type mismatch: {head_ty} vs {elem_ty}")

    # Result is Vec[T, succ(n)]
    return DepApp("Vec", [elem_ty], [IdxSucc(tail_len)])
```

## Vec Operations (Structural Recursion)

```auric
// Index function (safe, returns Option)
fn index[T, n](v: Vec[T, n], i: Nat) -> Option[T] {
    match v {
        Empty -> None;
        Cons(h, t) -> match i {
            zero -> Some(h);
            succ(i') -> index(t, i');  // Structural recursion
        }
    }
}

// Map preserves length
fn map[T, U, n](v: Vec[T, n], f: T -> U) -> Vec[U, n] {
    match v {
        Empty -> Empty;
        Cons(h, t) -> Cons(f(h), map(t, f));
    }
}

// Fold
fn fold[T, R, n](v: Vec[T, n], init: R, f: (R, T) -> R) -> R {
    match v {
        Empty -> init;
        Cons(h, t) -> fold(t, f(init, h), f);
    }
}

// Append - length arithmetic!
fn append[T, n, m](v1: Vec[T, n], v2: Vec[T, m]) -> Vec[T, plus(n, m)] {
    match v1 {
        Empty -> v2;  // plus(zero, m) = m
        Cons(h, t) -> Cons(h, append(t, v2));  // plus(succ(n), m) = succ(plus(n, m))
    }
}
```

## Type-Level Arithmetic (Later)

```auric
// Plus at type level
type Plus[n: Nat, m: Nat]: Nat where
    | Plus[zero, m] = m
    | Plus[succ(n), m] = succ(Plus[n, m])

// Usage:
fn append[T, n, m](v1: Vec[T, n], v2: Vec[T, m]) -> Vec[T, Plus[n, m]]
```

## Parser Syntax

```auric
// Dependent type syntax
Vec[Int, 5]        // Concrete length
Vec[T, n]          // Variable length
Vec[Int, _]        // Unknown length (existential)

// Function syntax
fn map[T, U, n](v: Vec[T, n], f: T -> U) -> Vec[U, n] { ... }

// Type signature
const nums: Vec[Int, 5] = Cons(1, Cons(2, Cons(3, Cons(4, Cons(5, Empty)))))
```

## Implementation Plan

1. ✅ Design dependent type system (this doc)
2. Add Index and DepApp to ast.py
3. Extend parser to parse Vec[T, n] syntax
4. Implement type checking for DepApp
5. Add Vec as builtin inductive type
6. Implement structural recursion checking
7. Add Vec operations (index, map, fold)
8. Tests
