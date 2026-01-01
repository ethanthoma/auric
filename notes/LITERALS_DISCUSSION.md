# Literals: Primitive or Not?

**Question:** Are IntLit, FloatLit, CharLit truly primitive?

**Short answer:** No! They could be encoded or provided as builtins. But we keep them for practicality.

---

## What Are Literals?

**Currently in the AST:**
```python
@dataclass
class IntLit:
    value: int          # 42
    type_suffix: str    # "i64", "u32", etc.

@dataclass
class FloatLit:
    value: float        # 3.14
    type_suffix: str    # "f64", "f32"

@dataclass
class CharLit:
    value: char         # 'a'
```

These represent **constant values** that appear in source code:
```auric
42         // IntLit(42, "i64")
3.14       // FloatLit(3.14, "f64")
'a'        // CharLit('a')
```

---

## Are They Actually Primitive?

### Option 1: True Primitives (Current)

**Pros:**
- ✅ Direct compilation to machine code
- ✅ Efficient (no overhead)
- ✅ Natural for systems programming

**Cons:**
- ❌ Not minimal (adds 3 AST nodes)
- ❌ Special-cased in type checker
- ❌ More complex core

**Philosophy:** Pragmatic - optimize for systems programming

---

### Option 2: Church Encoding (Ultra-Minimal)

**Pure lambda calculus approach:**

```auric
// Encode numbers as functions:
zero = (f) => (x) => x
one = (f) => (x) => f(x)
two = (f) => (x) => f(f(x))
three = (f) => (x) => f(f(f(x)))

// Then:
42 = (f) => (x) => f(f(f(...f(x)...)))  // Apply f 42 times!

// Arithmetic:
add = (m) => (n) => (f) => (x) => m(f)(n(f)(x))
mul = (m) => (n) => (f) => m(n(f))
```

**Pros:**
- ✅ Minimal (no special cases)
- ✅ Theoretically pure

**Cons:**
- ❌ **Terrible performance** (42 is 42 nested function calls!)
- ❌ **Massive memory usage** (each number is a closure)
- ❌ **Not practical for systems programming**
- ❌ Can't compile to efficient machine code

**Verdict:** Academic interest only, not for Auric

---

### Option 3: Builtins (Not AST Nodes)

**Literals provided by compiler, not part of AST:**

```auric
// Instead of AST node IntLit(42, "i64"):
// Treat as builtin constant:

type Expr =
    | Var(name)
    | Lam(params, body)
    | App(fn, args)
    // ... no IntLit!

// Then:
42  →  Var("42")  // Special variable
// Compiler knows "42" is integer constant
```

**Pros:**
- ✅ Minimal AST (no literal nodes)
- ✅ Still efficient (compiler handles it)

**Cons:**
- ❌ Confusing (is "42" a variable or constant?)
- ❌ Type checking more complex
- ❌ Less clear in AST

**Verdict:** Possible but awkward

---

### Option 4: Generic Constant Node (Better)

**Instead of IntLit, FloatLit, CharLit - one Const node:**

```python
@dataclass
class Const:
    value: Any    # Python int, float, char
    type: Type    # i64, f64, u8

type Expr =
    | Var(name)
    | Lam(params, body)
    | App(fn, args)
    | Const(value, type)  // One node for all constants
    // ...
```

**Examples:**
```auric
42     →  Const(42, i64)
3.14   →  Const(3.14, f64)
'a'    →  Const('a', u8)
true   →  Const(True, bool)
```

**Pros:**
- ✅ More minimal (1 node instead of 3)
- ✅ Extensible (add new constant types easily)
- ✅ Still efficient

**Cons:**
- ❌ Slightly less type-safe (Any type)

**Verdict:** Good compromise!

---

## Recommendation: Generic Const Node

### Refactor to Single Constant Type

```python
@dataclass
class Const:
    """Constant value literal"""
    value: Any       # The actual value
    type: Type       # Its type

type Expr =
    | Var(name)
    | Lam(params, body)
    | App(fn, args)
    | Record(fields)
    | FieldAccess(record, field)
    | Case(scrutinee, alts)
    | TyAbs(tv, body)
    | TyApp(fn, ty)
    | Const(value, type)  // <-- One node for all constants
    | Perform(effect, arg)
    | Handle(body, handlers)
```

**Now only 10 primitives instead of 13!**

---

## Even More Minimal: 8 Primitives

**If we're ruthless, we can go further:**

```python
type Expr =
    // Core lambda calculus (3):
    | Var(name)
    | Lam(params, body)
    | App(fn, args)

    // Data structures (2):
    | Record(fields)
    | FieldAccess(record, field)

    // Pattern matching (1):
    | Case(scrutinee, alts)

    // Polymorphism (2):
    | TyAbs(tv, body)
    | TyApp(fn, ty)
```

**Where did constants go?**

Treat them as **special variables** that the compiler recognizes:
- `42` → `Var("42")` (compiler knows it's an int constant)
- `3.14` → `Var("3.14")` (compiler knows it's a float constant)
- `'a'` → `Var("'a'")` (compiler knows it's a char constant)

The **type checker** handles these specially:
```python
def type_of(expr, env):
    match expr:
        case Var(name):
            # Check if it's a constant:
            if is_int_literal(name):
                return Int64
            elif is_float_literal(name):
                return Float64
            elif is_char_literal(name):
                return UInt8
            # Otherwise lookup in environment:
            else:
                return env[name]
```

**Pros:**
- ✅ Absolutely minimal AST (8 nodes!)
- ✅ Still efficient (compiler optimizes)

**Cons:**
- ❌ Less clear (constants look like variables)
- ❌ Type checker more complex

---

## What About Effects?

**Perform and Handle:**

```python
| Perform(effect, arg)
| Handle(body, handlers)
```

**Are these primitive?**

**Option A: Primitive (for algebraic effects)**
- Needed if we want first-class effects
- Can't be encoded as normal functions

**Option B: Not needed**
- Use monads or similar instead
- Or implement with exceptions (primitive in runtime)

**If we skip effects:** Down to **8 primitives!**

---

## Comparison: Minimalism Levels

### Level 1: Current (13 primitives)
```
Var, Lam, App,
Record, FieldAccess, Case,
TyAbs, TyApp,
IntLit, FloatLit, CharLit,
Perform, Handle
```

### Level 2: Refactored (10 primitives)
```
Var, Lam, App,
Record, FieldAccess, Case,
TyAbs, TyApp,
Const,           // Combined literals
Perform, Handle
```

### Level 3: No effects (8 primitives)
```
Var, Lam, App,
Record, FieldAccess, Case,
TyAbs, TyApp
```

### Level 4: Constants as vars (8 primitives still)
```
Var, Lam, App,
Record, FieldAccess, Case,
TyAbs, TyApp
// Constants are special Vars
```

### Level 5: Church encoding (3 primitives)
```
Var, Lam, App
// Everything else encoded!
```

**Level 5 is theoretically pure but practically useless.**

---

## Real-World Examples

### Scheme
```scheme
; Only 5 special forms:
; lambda, if, define, quote, set!
; Numbers are primitive in implementation, not in semantics
```

Scheme treats numbers as **primitive values**, but not primitive **syntax**.

### Haskell
```haskell
-- Literals are syntactic sugar:
42 :: Int    -- Desugars to: fromInteger 42
3.14 :: Double  -- Desugars to: fromRational 3.14
```

Haskell has **no literal AST nodes** - they desugar to function calls!

### Rust
```rust
// Literals are AST nodes:
Literal { kind: Int, value: 42, suffix: I64 }
```

Rust keeps literals explicit for efficiency.

---

## Recommendation for Auric

### Option: Hybrid Approach

**For the core language:**
- **8 primitives** (no literal nodes, no effects)
- Constants handled by type checker
- Effects as library (monads or similar)

**For practical implementation:**
- Add `Const` node for optimization
- Add effects if needed later

**This gives us:**
```python
type Expr =
    // Lambda calculus:
    | Var(name)
    | Lam(params, body)
    | App(fn, args)

    // Data:
    | Record(fields)
    | FieldAccess(record, field)
    | Case(scrutinee, alts)

    // Types:
    | TyAbs(tv, body)
    | TyApp(fn, ty)

    // Optimization (optional):
    | Const(value, type)  // For efficient constants
```

**9 nodes if we include Const, 8 without.**

---

## Summary

**Are literals primitive?**

**Theoretically:** No
- Can be encoded (Church numerals)
- Can be special variables
- Can be desugared to function calls

**Practically:** Yes (or at least useful)
- Direct compilation to machine code
- Zero overhead
- Natural for systems programming

**Best approach:**
- **Minimal core:** 8 primitives (constants as special vars)
- **Practical:** Add `Const` node → 9 primitives
- **With effects:** Add `Perform`/`Handle` → 11 primitives

**For Auric, I recommend:**

1. Start with **8 primitives** (no Const, no effects)
2. Add `Const` when optimizing (→ 9 primitives)
3. Add effects if needed later (→ 11 primitives)

**This keeps the core minimal while allowing practical efficiency.**

---

## Code Example

### Minimal Core (8 nodes)

```python
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class Var:
    name: str

@dataclass(frozen=True)
class Lam:
    params: List[str]
    body: 'Expr'

@dataclass(frozen=True)
class App:
    fn: 'Expr'
    args: List['Expr']

@dataclass(frozen=True)
class Record:
    fields: Dict[str, 'Expr']

@dataclass(frozen=True)
class FieldAccess:
    record: 'Expr'
    field: str

@dataclass(frozen=True)
class Case:
    scrutinee: 'Expr'
    alts: Dict[str, tuple[List[str], 'Expr']]

@dataclass(frozen=True)
class TyAbs:
    tv: str
    body: 'Expr'

@dataclass(frozen=True)
class TyApp:
    fn: 'Expr'
    arg_ty: 'Type'

Expr = Var | Lam | App | Record | FieldAccess | Case | TyAbs | TyApp
```

**That's it! 8 primitives.**

Constants like `42` are just `Var("42")` that the type checker recognizes.

---

## Questions for You

1. **How minimal should we go?**
   - 13 primitives (explicit literals + effects)?
   - 9 primitives (generic Const)?
   - 8 primitives (constants as special vars)?

2. **Do we need algebraic effects?**
   - If yes: add Perform/Handle
   - If no: use monads or exceptions

3. **Performance vs minimalism?**
   - Explicit literal nodes → faster compilation
   - Special variable treatment → simpler AST

My vote: **Start with 8, add Const for optimization, add effects later if needed.**
