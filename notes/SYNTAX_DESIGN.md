# Auric Syntax Design

**Status:** Finalized design, pending implementation

## Core Philosophy

1. **Files are records** - Top-level definitions become fields
1. **Blocks return values** - Last expression or explicit `return`
1. **Thunks are primitives** - `()` for suspended computation
1. **Records use `{}`** - No dot prefix needed
1. **Simple syntax** - Use `=` for fields, `let`/`const` for locals
1. **Zero-cost abstractions** - Compile-time evaluation, no runtime overhead

## Systems Programming with Familiar Syntax

Auric is designed for **systems programming** with **Rust-like syntax** rather than Lisp-style s-expressions:

### What Makes It a Systems Language?

**Memory control:**
- Records are stack-allocated by default
- Field access compiled to direct offsets (no hash tables)
- No garbage collection (region-based memory management)
- Explicit lifetimes through regions

**Zero-cost abstractions:**
- Macros expand at compile time (zero runtime cost)
- Pattern matching compiles to efficient jump tables
- Monomorphization (like Rust/C++) - no runtime polymorphism
- Inline-friendly: small functions inline completely

**Performance characteristics:**
```auric
// This field access:
point.x

// Compiles to (in C):
*((int64_t*)point_addr + 0)  // Direct offset, no lookup

// This pattern match:
shape => {
    Circle(r) -> 3.14 * r * r;
    Rectangle(w, h) -> w * h
}

// Compiles to (in C):
switch (shape->tag) {
    case CIRCLE: return 3.14 * shape->data.circle.r * shape->data.circle.r;
    case RECTANGLE: return shape->data.rectangle.w * shape->data.rectangle.h;
}
```

### Rust-Like Syntax, Not Lisp Syntax

**Compare the same macro in different languages:**

**Lisp (s-expressions):**
```lisp
(defmacro when (test &rest body)
  `(if ,test
       (progn ,@body)
       nil))
```

**Auric (Rust-like syntax):**
```auric
macro when = (test: Expr, body: Expr) => {
    Case(test, {
        true = { body },
        false = { Record({}) }
    })
}
```

**Key differences:**
- ✅ Type annotations (`test: Expr`)
- ✅ Named fields in records (`{ true = { body } }`)
- ✅ Familiar operators (`=>`, `->`)
- ✅ Braces and semicolons (C-family style)
- ❌ No parentheses prefix syntax
- ❌ No quote/unquote operators

**Result:** Same macro power as Lisp, with syntax familiar to systems programmers.

______________________________________________________________________

## Field Definitions vs Local Bindings

### Fields (Exported/Accessible)

Use `=` without keyword:

```auric
// Top-level (file fields)
pi = 3.14159
add = (x, y) => x + y

// Record fields
point = { x = 1, y = 2 }

// With type annotation
pi: f64 = 3.14159
add: (Int, Int) -> Int = (x, y) => x + y
```

### Local Bindings (Not Exported)

Use `let` or `const` keyword:

```auric
add = (x, y) => {
    let sum = x + y      // Local binding
    const double = sum * 2  // Local constant
    return double
}

// `sum` and `double` are not accessible outside this function
```

**The rule:** No keyword = field, has keyword = local

______________________________________________________________________

## Records vs Blocks

### Records

Contain field definitions with `=`:

```auric
// Record literal
point = { x = 1, y = 2 }

// Nested records
user = {
    name = "Alice",
    age = 30,
    location = { x = 10, y = 20 }
}

// Shorthand (if we support it)
make_user = (name, age) => {
    { name, age }  // Means { name = name, age = age }
}
```

### Blocks

Contain statements, local bindings, and `return`:

```auric
// Block with local bindings
compute = (x) => {
    let y = x + 1
    let z = y * 2
    return z
}

// Single expression (braces optional)
identity = (x) => { return x }
identity = (x) => x  // Equivalent

// Early return
safe_div = (x, y) => {
    if y == 0 { return 0 }
    return x / y
}
```

### Disambiguation

```auric
// Record (has = for fields)
{ x = 1, y = 2 }

// Block (has let/const or return)
{
    let x = 1
    return x
}

// Edge case: single identifier
{ x }        // Block returning x's value
{ x = x }    // Record with field x
```

______________________________________________________________________

## Thunks (Suspended Computation)

**Syntax:**

- `() => expr` - Create thunk
- `thunk()` - Force evaluation

**AST:**

- `Thunk(body: Expr)` - Suspended computation
- `Force(thunk: Expr)` - Evaluate thunk

**Examples:**

```auric
// Lazy evaluation
expensive = () => heavy_computation()
result = expensive()  // Force when needed

// Double wrapping
delayed = () => () => 42
value = delayed()()  // 42

// Empty record vs thunk returning empty record
empty_record = {}           // Record with no fields
lazy_empty = () => {}       // Thunk returning empty record
forced = lazy_empty()       // Force to get {}
```

**Distinction:**

- `{}` - Empty record (data)
- `() => {}` - Thunk returning empty record (computation)

______________________________________________________________________

## Files as Records

### Without `return` - File is a Record

```auric
// math.au
pi = 3.14159
e = 2.71828
add = (x, y) => x + y

// Implicitly: { pi = 3.14159, e = 2.71828, add = ... }

// main.au
import math

math.pi
math.add(1, 2)
```

### With `return` - File is an Expression

```auric
// pi.au
compute_pi = () => {
    // ... computation ...
    3.141592653589793
}

return compute_pi()  // File value is the result

// main.au
import pi  // pi is a number, not a record

print(pi)  // 3.141592653589793
```

______________________________________________________________________

## Pattern Matching

```auric
// Match on records
process_point = (point) => {
    point => {
        { x = 0, y = 0 } -> "origin";
        { x = px, y = py } -> "point at ({px}, {py})";
    }
}

// Match on variants
process_expr = (ast: Expr) => {
    ast => {
        Var(name) -> "variable {name}";
        App(f, a) -> "application";
        Lam(param, body) -> "lambda";
        Thunk(body) -> "thunk";
        Force(thunk) -> "force";
    }
}
```

______________________________________________________________________

## Complete Examples

### Simple File

```auric
// math.au

// Constants
pi: f64 = 3.14159
e: f64 = 2.71828

// Functions
add = (x, y) => x + y

factorial = (n) => {
    n => {
        0 -> 1;
        _ -> n * factorial(n - 1);
    }
}

// Records
origin = { x = 0, y = 0 }

make_point = (x, y) => {
    return { x = x, y = y }
}
```

### File with Return

```auric
// config.au

// Define some settings
debug_mode = true
max_retries = 3

compute_config = () => {
    let base = { debug = debug_mode, retries = max_retries }

    let with_timeout = {
        ..base,
        timeout = if debug_mode { 1000 } else { 100 }
    }

    return with_timeout
}

// Export the computed config
return compute_config()

// Usage:
// import config
// config.debug  // true
// config.timeout  // 1000 or 100
```

### Macro Example

```auric
// Optimize AST by eliminating double negation
optimize = (ast: Expr) => {
    ast => {
        // not(not(x)) -> x
        App(Var("not"), App(Var("not"), x)) -> optimize(x);

        // id(x) -> x
        App(Var("id"), x) -> optimize(x);

        // Recurse into sub-expressions
        App(f, a) -> App(optimize(f), optimize(a));
        Lam(p, b) -> Lam(p, optimize(b));
        Thunk(body) -> Thunk(optimize(body));
        Force(t) -> Force(optimize(t));

        // Keep everything else
        _ -> ast;
    }
}
```

______________________________________________________________________

## Syntax Summary

| Concept | Syntax | Example | |---------|--------|---------| | Field definition
| `name = value` | `pi = 3.14` | | Type annotation | `name: Type = value` |
`pi: f64 = 3.14` | | Local binding | `let name = value` | `let x = 1` | | Record
literal | `{ field = value, ... }` | `{ x = 1, y = 2 }` | | Block |
`{ statements; return expr }` | `{ let x = 1; return x }` | | Thunk |
`() => expr` | `() => compute()` | | Force | `expr()` | `thunk()` | | Function |
`(param) => expr` | `(x) => x + 1` | | Pattern match |
`expr => { pattern -> result }` | `x => { 0 -> "zero" }` | | Return |
`return expr` | `return 42` | | Import | `import module` | `import math` |

______________________________________________________________________

## Design Decisions

### Why `=` for fields?

- ✅ Simple and familiar
- ✅ Context disambiguates (no `let` = field, has `let` = local)
- ✅ Works for top-level and records (unified)

### Why `return` keyword?

- ✅ Explicit control over block/function return value
- ✅ Allows early exit
- ✅ Makes file-as-expression possible
- ✅ Optional for last expression (Rust-style)

### Why files are records?

- ✅ Consistent: everything is data
- ✅ Natural module system
- ✅ Can override with `return` for computed exports
- ✅ Follows Nix philosophy

### Why thunks are primitives?

- ✅ Distinct from empty records
- ✅ Enable lazy evaluation
- ✅ Clean syntax: `()` pairs with function call `()`
- ✅ Useful for macros and metaprogramming

---

## Language Comparison: Concrete Examples

### Example: List Map Function

**Lisp:**
```lisp
(defun map (f lst)
  (if (null lst)
      nil
      (cons (funcall f (car lst))
            (map f (cdr lst)))))
```

**Rust:**
```rust
fn map<A, B>(f: impl Fn(A) -> B, lst: List<A>) -> List<B> {
    match lst {
        Nil => Nil,
        Cons(x, xs) => Cons(f(x), map(f, *xs))
    }
}
```

**Auric:**
```auric
map: (f: A -> B, lst: List(A)) -> List(B) = (f, lst) => {
    lst => {
        Nil -> Nil;
        Cons(x, xs) -> Cons(f(x), map(f, xs))
    }
}
```

**Observations:**
- Auric syntax closer to Rust than Lisp
- Type annotations present (like Rust)
- Pattern matching syntax (like Rust)
- Concise function definition (like Lisp)

### Example: Macro Definition

**Lisp (when macro):**
```lisp
(defmacro when (test &rest body)
  `(if ,test
       (progn ,@body)
       nil))
```

**Rust (declarative macro):**
```rust
macro_rules! when {
    ($test:expr, $($body:expr),*) => {
        if $test {
            $($body)*
        }
    };
}
```

**Auric:**
```auric
macro when = (test: Expr, body: Expr) => {
    Case(test, {
        true = { body },
        false = { Record({}) }
    })
}
```

**Observations:**
- Auric manipulates AST directly (like Lisp)
- Type-safe constructors (`Case`, `Record`)
- No special macro syntax (unlike both Lisp and Rust)
- Pattern matching on AST structure (powerful like Lisp)

### Example: Generic Data Structure

**Lisp (dynamically typed):**
```lisp
(defstruct point x y)
```

**Rust:**
```rust
struct Point<T> {
    x: T,
    y: T
}
```

**Auric:**
```auric
// Type definition
type Point(T) = {
    Point <- { x: T, y: T }
}

// Or just use anonymous record:
point: { x: i64, y: i64 } = { x = 10, y = 20 }
```

**Observations:**
- Auric records are first-class (like Rust structs)
- Stack-allocated by default (like Rust)
- No constructor boilerplate needed
- Can use anonymous or named types

### Example: Module System

**Lisp:**
```lisp
(defpackage :math
  (:export :pi :add))

(in-package :math)

(defconstant pi 3.14159)
(defun add (x y) (+ x y))
```

**Rust:**
```rust
// math.rs
pub const PI: f64 = 3.14159;
pub fn add(x: i64, y: i64) -> i64 {
    x + y
}
```

**Auric:**
```auric
// math.au (files are records!)
pi: f64 = 3.14159
add = (x, y) => x + y

// Implicitly exports: { pi = 3.14159, add = ... }
```

**Observations:**
- Simplest module system (files = records)
- No `pub`, `export`, or package declarations needed
- Same syntax as defining a record
- Follows Nix philosophy

### Key Takeaway

Auric achieves **Lisp power** through:
- Pattern matching on AST variants (not string manipulation)
- Compile-time evaluation (macros are just functions on AST)
- Homoiconicity (code is data, but typed data)

While maintaining **Rust ergonomics**:
- Familiar syntax (braces, type annotations)
- Zero-cost abstractions
- Stack allocation by default
- No special macro syntax to learn
