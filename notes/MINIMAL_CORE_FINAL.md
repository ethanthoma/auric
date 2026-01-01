# Auric Minimal Core: Final Specification

**Decision:** Generic Const node (Option 2)

**Total primitives:** 9 core + 2 optional effects = **9-11 primitives**

---

## The Final Core (9 Primitives)

```python
from dataclasses import dataclass
from typing import Any, Dict, List

# ============================================================
# Core Language: 9 Primitives
# ============================================================

@dataclass(frozen=True)
class Var:
    """Variable reference: x"""
    name: str

@dataclass(frozen=True)
class Lam:
    """Lambda abstraction: (x, y) => body"""
    params: List[str]
    body: 'Expr'

@dataclass(frozen=True)
class App:
    """Function application: f(x, y)"""
    fn: 'Expr'
    args: List['Expr']

@dataclass(frozen=True)
class Record:
    """Record literal: { x = 1, y = 2 }"""
    fields: Dict[str, 'Expr']

@dataclass(frozen=True)
class FieldAccess:
    """Field access: record.field"""
    record: 'Expr'
    field: str

@dataclass(frozen=True)
class Case:
    """Pattern matching: x => { pattern -> result }"""
    scrutinee: 'Expr'
    alts: Dict[str, tuple[List[str], 'Expr']]

@dataclass(frozen=True)
class TyAbs:
    """Type abstraction: Λα. body"""
    tv: str
    body: 'Expr'

@dataclass(frozen=True)
class TyApp:
    """Type application: f[Int]"""
    fn: 'Expr'
    arg_ty: 'Type'

@dataclass(frozen=True)
class Const:
    """Constant literal: 42, 3.14, 'a', true

    Replaces: IntLit, FloatLit, CharLit, BoolLit
    """
    value: Any    # Python int, float, str (single char), bool
    ty: 'Type'    # i64, f64, u8, bool, etc.

# Union type
Expr = Var | Lam | App | Record | FieldAccess | Case | TyAbs | TyApp | Const
```

---

## Optional: Effects (2 more primitives)

**If we want algebraic effects:**

```python
@dataclass(frozen=True)
class Perform:
    """Effect invocation: perform(Print, "hello")"""
    effect: str
    arg: 'Expr'

@dataclass(frozen=True)
class Handle:
    """Effect handler: handle body { Effect(p) -> handler }"""
    body: 'Expr'
    handlers: Dict[str, tuple[List[str], 'Expr']]
```

**Total with effects: 11 primitives**

**Without effects: 9 primitives**

---

## Const Node Details

### Supported Constant Types

```python
# Integer types (8):
i8, i16, i32, i64      # Signed
u8, u16, u32, u64      # Unsigned

# Float types (2):
f32, f64               # IEEE 754

# Character (1):
u8  # ASCII characters (alias: char)

# Boolean (1):
bool  # true, false

# Total: 12 primitive types
```

### Examples

```python
# Integers:
Const(42, i64)          # 42
Const(255, u8)          # 255u8
Const(-100, i32)        # -100i32

# Floats:
Const(3.14, f64)        # 3.14
Const(2.5, f32)         # 2.5f32

# Characters:
Const('a', u8)          # 'a'
Const('\n', u8)         # '\n'

# Booleans:
Const(True, bool)       # @true
Const(False, bool)      # @false
```

### Type Suffixes in Source

```auric
// Integer literals:
42         // Const(42, i64) - default
42u8       // Const(42, u8)
42i32      // Const(42, i32)
255u32     // Const(255, u32)

// Float literals:
3.14       // Const(3.14, f64) - default
3.14f32    // Const(3.14, f32)
2.5e10     // Const(2.5e10, f64)

// Character literals:
'a'        // Const('a', u8)
'Z'        // Const('Z', u8)
'\n'       // Const('\n', u8)

// Boolean literals:
@true      // Const(True, bool)
@false     // Const(False, bool)
```

---

## Type System

### Base Types

```python
@dataclass(frozen=True)
class Base:
    """Base type: i64, f64, u8, bool"""
    name: str

# Supported base types:
i8, i16, i32, i64
u8, u16, u32, u64
f32, f64
bool
```

### Type Checking Constants

```python
def type_of(expr: Expr, env: TypeEnv) -> Type:
    match expr:
        case Const(value, ty):
            # Type is explicit in the node
            return ty
        # ... other cases
```

---

## Migration from Current AST

### Before (13 primitives)

```python
@dataclass
class IntLit:
    value: int
    type_suffix: str

@dataclass
class FloatLit:
    value: float
    type_suffix: str

@dataclass
class CharLit:
    value: str

# Total: 3 literal types
```

### After (1 primitive)

```python
@dataclass(frozen=True)
class Const:
    value: Any
    ty: Type

# Total: 1 constant type
```

### Migration Path

```python
# Old → New:
IntLit(42, "i64")      →  Const(42, Base("i64"))
FloatLit(3.14, "f64")  →  Const(3.14, Base("f64"))
CharLit('a')           →  Const('a', Base("u8"))

# New capability (booleans):
BoolLit(True)          →  Const(True, Base("bool"))
```

---

## Complete Minimal Core Example

### AST Representation

```python
# Source:
add = (x, y) => x + y
result = add(1, 2)

# AST:
Lam(
    ["x", "y"],
    App(
        Var("+"),
        [Var("x"), Var("y")]
    )
)

# Applied:
App(
    Lam(["x", "y"], App(Var("+"), [Var("x"), Var("y")])),
    [Const(1, Base("i64")), Const(2, Base("i64"))]
)
```

### With Pattern Matching

```python
# Source:
factorial = (n) => n => {
    0 -> 1;
    _ -> n * factorial(n - 1)
}

# AST:
Lam(
    ["n"],
    Case(
        Var("n"),
        {
            "0": ([], Const(1, Base("i64"))),
            "_": (
                [],
                App(
                    Var("*"),
                    [
                        Var("n"),
                        App(
                            Var("factorial"),
                            [App(Var("-"), [Var("n"), Const(1, Base("i64"))])]
                        )
                    ]
                )
            )
        }
    )
)
```

### With Records

```python
# Source:
point = { x = 1, y = 2 }
x_val = point.x

# AST:
Record({
    "x": Const(1, Base("i64")),
    "y": Const(2, Base("i64"))
})

FieldAccess(
    Var("point"),
    "x"
)
```

---

## Primitive Coverage

### What These 9 Primitives Give Us

| Construct | Primitive | Why Primitive |
|-----------|-----------|---------------|
| Variables | Var | Cannot be encoded |
| Functions | Lam | Cannot be encoded |
| Application | App | Cannot be encoded |
| Records | Record | Could encode but impractical |
| Field access | FieldAccess | Could use Case but inefficient |
| Pattern match | Case | Needed for ADTs + exhaustiveness |
| Polymorphism | TyAbs, TyApp | Needed for generics |
| Constants | Const | Could encode but very inefficient |

### What Can Be Macros (Everything Else!)

| Feature | Macro Definition |
|---------|------------------|
| if-then-else | → Case on boolean |
| let bindings | → Lambda application |
| Sequences | → Nested lets |
| Loops | → Recursion + case |
| Tuples | → Records with _0, _1, ... |
| Arrays | → Records with indexed fields |
| Strings | → Arrays of chars |
| Operators | → Function calls |
| Boolean ops | → Functions + case |
| return | → Effects or CPS |

**Result: ~78% of language is macros!**

---

## Benefits of This Design

### 1. Minimal Core

```
9 primitives (or 11 with effects)
vs
13 primitives (before)
vs
25+ primitives (Lisp)
vs
50+ primitives (Rust)
```

### 2. Extensible Constants

Want to add new constant types? Easy!

```python
# Add complex numbers:
Const(3+4j, Complex)

# Add rationals:
Const(Fraction(3, 4), Rational)

# Add big integers:
Const(123456789012345678901234567890, BigInt)
```

Just extend the type system - no new AST nodes!

### 3. Simple Implementation

```python
def eval_expr(expr: Expr, env: Env) -> Value:
    match expr:
        case Var(name):
            return env[name]

        case Lam(params, body):
            return Closure(params, body, env)

        case App(fn, args):
            closure = eval_expr(fn, env)
            arg_vals = [eval_expr(arg, env) for arg in args]
            return apply(closure, arg_vals)

        case Record(fields):
            return {k: eval_expr(v, env) for k, v in fields.items()}

        case FieldAccess(record, field):
            rec_val = eval_expr(record, env)
            return rec_val[field]

        case Case(scrut, alts):
            val = eval_expr(scrut, env)
            return match_pattern(val, alts, env)

        case TyAbs(tv, body):
            # Type abstraction (erased at runtime)
            return eval_expr(body, env)

        case TyApp(fn, ty):
            # Type application (erased at runtime)
            return eval_expr(fn, env)

        case Const(value, ty):
            # Constants evaluate to themselves
            return value
```

**That's the entire evaluator core!** ~50 lines of code.

### 4. Clear Semantics

Every primitive has a clear, well-defined meaning:
- Var: lookup in environment
- Lam: create closure
- App: apply function
- Record: create record
- FieldAccess: project field
- Case: pattern match
- TyAbs/TyApp: type-level (erased)
- Const: constant value

No special cases, no magic.

---

## Implementation Checklist

### Phase 1: Update AST (1 day)

- [ ] Add `Const` dataclass to `ast.py`
- [ ] Remove `IntLit`, `FloatLit`, `CharLit`
- [ ] Update all pattern matches

### Phase 2: Update Parser (2 days)

- [ ] Parse integer literals → `Const(value, i64)`
- [ ] Parse float literals → `Const(value, f64)`
- [ ] Parse char literals → `Const(value, u8)`
- [ ] Parse type suffixes (42u8, 3.14f32)
- [ ] Parse boolean literals (@true, @false)

### Phase 3: Update Type Checker (1 day)

- [ ] Type check `Const` nodes
- [ ] Remove special cases for IntLit, FloatLit, CharLit
- [ ] Handle all primitive types (i8-i64, u8-u64, f32-f64, bool)

### Phase 4: Update Evaluator (1 day)

- [ ] Evaluate `Const` nodes (return value)
- [ ] Remove special cases for old literal nodes

### Phase 5: Update Codegen (1 day)

- [ ] Generate code for `Const` nodes
- [ ] Handle all primitive types
- [ ] Optimize constant folding

**Total: ~6 days to migrate**

---

## Testing Strategy

### Test Constants

```python
def test_integer_constants():
    assert eval("42") == 42
    assert eval("42u8") == 42
    assert eval("-100i32") == -100

def test_float_constants():
    assert eval("3.14") == 3.14
    assert eval("2.5f32") == 2.5
    assert eval("1.0e-5") == 1.0e-5

def test_char_constants():
    assert eval("'a'") == 'a'
    assert eval("'\\n'") == '\n'

def test_bool_constants():
    assert eval("@true") == True
    assert eval("@false") == False
```

### Test Type Checking

```python
def test_const_types():
    assert type_of("42") == Base("i64")
    assert type_of("42u8") == Base("u8")
    assert type_of("3.14") == Base("f64")
    assert type_of("3.14f32") == Base("f32")
    assert type_of("'a'") == Base("u8")
    assert type_of("@true") == Base("bool")
```

---

## Summary

**Final Auric Core: 9 Primitives**

```
1. Var         - Variable reference
2. Lam         - Lambda abstraction
3. App         - Application
4. Record      - Record literal
5. FieldAccess - Field projection
6. Case        - Pattern matching
7. TyAbs       - Type abstraction
8. TyApp       - Type application
9. Const       - Constant literals (unified)
```

**Optional: +2 for effects (Perform, Handle)**

**This gives us:**
- ✅ Minimal core (9 primitives)
- ✅ Extensible constants (one node, many types)
- ✅ Clear semantics (no special cases)
- ✅ Efficient (direct compilation)
- ✅ Simple to implement (~50 line evaluator)

**Everything else (78%) is macros!**
- if, let, sequences, loops
- Operators, tuples, arrays, strings
- All control flow
- All syntactic sugar

**Auric achieves Scheme-level minimalism with systems-level performance.**
