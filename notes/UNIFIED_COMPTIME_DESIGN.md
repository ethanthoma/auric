# Unified Comptime/Runtime Design

**Philosophy:** Comptime code = Runtime code, just evaluated earlier
(Zig-inspired)

## Goal: S-Expression Power Without S-Expression Syntax

Auric achieves **Lisp-like macro capabilities** while maintaining:
- **Rust-like syntax** - familiar, type-safe, systems-level
- **Totality** - exhaustiveness checking, termination guarantees
- **Zig's comptime philosophy** - same syntax at runtime and comptime
- **Zero special primitives** - pattern matching on variants is all you need

### The Key Insight

**Lisp's power comes from homoiconicity** - code is data. Lisp uses s-expressions:
```lisp
'(defun add (x y) (+ x y))  ; Lisp: code as list
```

**Auric achieves the same with variants** - AST nodes are algebraic data types:
```auric
Lam("add", App(App(Var("+"), Var("x")), Var("y")))  // Auric: code as variants
```

Both are **structured data** you can pattern match and reconstruct. The difference is syntax, not power.

### Equivalence to S-Expressions

| Lisp Capability | S-Expression Approach | Auric Approach |
|----------------|----------------------|----------------|
| **Construct AST** | `(list 'defun 'foo ...)` | `Lam("foo", ...)` |
| **Destructure AST** | `(car expr)`, `(cdr expr)` | `Lam(name, body) -> ...` |
| **Check node type** | `(eq (car expr) 'defun)` | `expr => { Lam(...) -> ... }` |
| **Recursively transform** | `(mapcar #'transform expr)` | `Lam(p, transform(b))` |
| **Quote/splice** | `` `(,@args) `` | `{ ..args }` (spread) |

**Result:** Auric macros can do everything Lisp macros can, with:
- ✅ Type safety (exhaustiveness checking)
- ✅ Familiar syntax (no parentheses soup)
- ✅ Totality (pattern matches must be exhaustive)
- ✅ Systems performance (no runtime overhead)

## Summary

**Zero primitives, three builtin features:**

1. **Spread operator `..`** - Comptime-only record merging
1. **`unreachable` keyword** - Mark impossible code paths
1. **Thunk primitive `()`** - Suspended computations: `() => expr` and `thunk()`

**Key innovations:**

- AST nodes are **variant types** at comptime - no special primitives needed
- Variant constructors (`Var`, `App`, `Lam`, `Thunk`, `Force`) are the API - no
  wrapper functions
- Pattern matching for AST destructuring - exhaustiveness checking built-in
- **Records use `{}` not `.{}`** - no dot prefix
- Thunks `()` are distinct from empty records `{}`
- Everything uses the same syntax at runtime and comptime

## Core Principles

1. **Same Syntax, Different Time**

   - Comptime code looks identical to runtime code
   - Only difference: WHEN evaluation happens, not HOW it's written

1. **Records Everywhere**

   - No special lists (cons/nil)
   - Strings are `Record[u8]`
   - **AST nodes are tagged records** at comptime
   - All data structures are records

1. **Pattern Matching Only**

   - No `if-then-else` expressions
   - Only control flow: `value => { pattern -> result }`
   - Works same at runtime and comptime

1. **Zero Primitives**

   - No special comptime primitives
   - User-defined helper functions replace primitives
   - Everything is regular Auric code

1. **Zig-Style Error Handling**

   - Use `unreachable` keyword (not `error()` primitive)
   - Pattern match failures are automatic errors
   - No special error handling at comptime

1. **Totality Preserved**

   - Runtime records are closed (all fields known)
   - Comptime can use spread `..` for flexibility
   - Pattern matching remains exhaustive

## AST Representation at Comptime

**Zero primitives needed!** AST nodes are represented as variant types
(algebraic data types).

### AST Node Types

All AST nodes are proper variants:

```auric
type Expr =
    | Var(name: Record[u8])
    | App(fn: Expr, arg: Expr)
    | Lam(param: Record[u8], body: Expr)
    | Thunk(body: Expr)              // () => expr
    | Force(thunk: Expr)             // thunk()
    | Record(fields: Record)
    | Case(scrutinee: Expr, alts: Record)
    // ... other node types
```

**Key distinction:**

- **`Thunk`** - Suspended computation, no parameters: `() => expr`
- **`Force`** - Evaluate thunk: `thunk()`
- **`Lam`** - Function with parameter: `(x) => expr`
- **`App`** - Function application: `f(x)`

### Construction Uses Variant Constructors

**No helper functions needed!** Variant constructors are already functions:

```auric
// Constructors are built into the language
Var("x")              // Creates Var variant
App(f, x)             // Creates App variant
Lam("x", body)        // Creates Lam variant
Thunk(expr)           // Creates Thunk variant: () => expr
Force(thunk)          // Creates Force variant: thunk()
Record({ x = 1 })     // Creates Record variant (no dot prefix!)
```

**Benefits over helper functions:**

- ✅ More concise - no wrapper functions needed
- ✅ Type-safe - exhaustiveness checking works properly
- ✅ No string typos - `Var` not `"Var"`
- ✅ Native to the language - uses Auric's variant system

### AST Destructuring via Pattern Matching

No special primitives - just use variant pattern matching:

```auric
macro transform = (ast: Expr) => {
    ast => {
        // Destructure App variant
        App(f, a) -> App(a, f);  // Reverse application

        // Destructure Var variant
        Var(n) -> ast;  // Keep as-is

        // Destructure Lam variant
        Lam(p, b) -> Lam(p, transform(b));  // Recurse on body

        // Destructure Thunk variant
        Thunk(body) -> Thunk(transform(body));  // Recurse into thunk

        // Destructure Force variant
        Force(t) -> Force(transform(t));  // Recurse on forced expression

        // Destructure Record variant
        Record(fs) -> ast;  // Process fields...

        // Exhaustiveness checking ensures all cases handled!
    }
}
```

### Eliminated Primitives

**Previously needed 11 primitives, now need 0:**

- ❌ `var(name)` → variant constructor `Var(name)`
- ❌ `app(fn, arg)` → variant constructor `App(fn, arg)`
- ❌ `lam(param, body)` → variant constructor `Lam(param, body)`
- ❌ `record(fields)` → variant constructor `Record(fields)`
- ❌ `app_fn(app)` → pattern match `App(f, a) -> f`
- ❌ `app_arg(app)` → pattern match `App(f, a) -> a`
- ❌ `lam_param(lam)` → pattern match `Lam(p, b) -> p`
- ❌ `lam_body(lam)` → pattern match `Lam(p, b) -> b`
- ❌ `var_name(var)` → pattern match `Var(n) -> n`
- ❌ `type_of(expr)` → pattern match on variant
- ❌ `record_fields(r)` → pattern match `Record(fs) -> fs`
- ❌ `is_record(expr)` → pattern match + dependent types
- ❌ `fold_record(...)` → pattern match + dependent types + recursion
- ❌ `error(msg)` → use `unreachable` keyword

## Builtin Features (Not Primitives!)

**Total: 3 builtin language features**

### 1. Spread Operator `..` (Comptime-Only)

The spread operator merges records. To preserve totality, it **only works at
compile-time**.

### Syntax

```auric
// Merge records (later fields override)
{ ..r1, ..r2 }

// Extend record
{ x = 1, ..rest }

// Concatenate indexed records (arrays/strings)
{ ..vec1, ..vec2 }  // Auto-reindex: _0, _1, _2, ...
```

### Type Behavior

**Named fields:**

```auric
{ x = 1, ...({ y = 2, z = 3 }) }
→ { x = 1, y = 2, z = 3 }
```

**Indexed fields (arrays/strings):**

```auric
{ _0 = 'a', _1 = 'b', ..({ _0 = 'c', _1 = 'd' }) }
→ { _0 = 'a', _1 = 'b', _2 = 'c', _3 = 'd' }  // Reindexed!
```

### Totality Guarantee

**Comptime (macros):** Spread allowed, fields known statically

```auric
macro concat_strings = (s1, s2) => { ..s1, ..s2 }  // ✓ OK
```

**Runtime:** No spread, must enumerate fields explicitly

```auric
const merge = (r1, r2) => { x = r1.x, y = r2.y }  // ✓ Total
const bad = (r1, r2) => { ..r1, ..r2 }            // ✗ Error!
```

### 2. `unreachable` Keyword (Runtime & Comptime)

Marks code paths that are logically impossible. Inspired by Zig's `unreachable`.

**Type signature:** `unreachable -> Never` (bottom type)

**Behavior:**

- **At comptime:** Compile error with location
- **At runtime (debug):** Panic with location
- **At runtime (release):** Undefined behavior (optimizer assumes it never
  executes)

**Usage:**

```auric
// Mark impossible branches
const safe_head = (list: List(T)) => {
    list => {
        Cons(x, _) -> x;
        Nil -> unreachable  // Caller guarantees non-empty
    }
}

// Exhaustiveness in macros
macro transform = (ast: Expr) => {
    ast => {
        .{ tag = "App" } -> ...;
        .{ tag = "Var" } -> ...;
        _ -> unreachable  // All other cases shouldn't happen
    }
}

// Pattern match failures are automatic (don't need explicit unreachable)
const process = (x: Int) => {
    x => {
        0 -> "zero";
        // If x is not 0, automatically unreachable
    }
}
```

**Replaces `error(msg)` primitive:**

- ❌ Old: `error("custom message")` - special primitive
- ✅ New: `unreachable` - builtin keyword, consistent with Zig
- Custom messages: Use assert library functions at comptime

### 3. Thunk Primitive `()` (Runtime & Comptime)

**Thunks are suspended computations**, different from empty records.

**Syntax:**

- `() => expr` - Create thunk (suspend computation)
- `thunk()` - Force thunk (evaluate)
- `()()` - Create and immediately force

**AST representation:**

- `Thunk(body)` - Suspended computation
- `Force(thunk)` - Evaluation

**Distinction from empty records:**

```auric
// Empty record (data with zero fields)
const empty_data: {} = {}           // Record({})

// Thunk returning empty record (suspended computation)
const lazy_empty = () => {}         // Thunk(Record({}))

// Force to get the empty record
const result = lazy_empty()         // Force(...) → Record({})

// Double wrapping
const delayed = () => () => 42      // Thunk(Thunk(IntLit(42)))
const value = delayed()()           // Force(Force(...)) → 42
```

**Use cases:**

```auric
// Lazy evaluation
const expensive = () => heavy_computation()
// ... later when needed:
const result = expensive()

// Conditional evaluation
const debug_info = () => collect_debug_data()
const info = if debugging { debug_info() } else { {} }

// Infinite structures
const ones = () => { head = 1, tail = ones }
```

**In macros:**

```auric
macro delay = (ast: Expr) => Thunk(ast)

macro force_all = (ast: Expr) => {
    ast => {
        Thunk(body) -> Force(ast);  // Unwrap thunk
        App(f, a) -> App(force_all(f), force_all(a));  // Recurse
        _ -> ast
    }
}
```

## Examples

### Simple Macro with Bracket Syntax

```auric
// Macro that generates field access at index i
macro index = (vec: Expr, i: Record[u8]) => {
    vec[i]  // Bracket syntax constructs FieldAccess AST
            // i must be compile-time known
}

// Usage:
const v = { _0 = @zero, _1 = @succ(@zero) }
const first = index(v, "_0")  // Expands to: v["_0"] or v._0 (same)

// Sugar - dot notation works too:
const also_first = v._0  // Desugars to: v["_0"]
```

### Complex Example: Lisp-Style Macro with Variant Matching

```auric
macro for = (ast: Expr) => {
    // Pattern match on AST variant structure
    ast => {
        // Match: for(x, list, body) → ((for x) list) body
        App(App(App(Var("for"), Var(var_name)), expr), body) -> {
            // Transform: for(x, list, body)
            // Into: map(lam(x, body), list)
            App(App(Var("map"), Lam(var_name, body)), expr)
        };
        _ -> unreachable
    }
}
```

**Simpler example - reverse function application:**

```auric
macro pipe = (ast: Expr) => {
    ast => {
        // Match: pipe(f, x) → (pipe f) x
        App(App(Var("pipe"), f), x) -> {
            // Transform to: f(x)
            App(f, x)
        };
        _ -> unreachable
    }
}

// Usage: pipe(double, 5) → double(5)
```

**Recursive transformation:**

```auric
macro optimize = (ast: Expr) => {
    ast => {
        // Eliminate double negation
        App(Var("not"), App(Var("not"), x)) -> optimize(x);

        // Identity: id(x) → x
        App(Var("id"), x) -> optimize(x);

        // Recurse into sub-expressions
        App(f, a) -> App(optimize(f), optimize(a));
        Lam(p, b) -> Lam(p, optimize(b));

        // Keep everything else
        _ -> ast
    }
}
```

### Advanced Example: Lisp-Style Quasiquote

**Lisp quasiquote** lets you template code with splicing:
```lisp
`(defun ,name (,@params) ,body)  ; Template with holes
```

**Auric equivalent** using record spread:
```auric
macro make_function = (name: Record[u8], params: Expr, body: Expr) => {
    // Construct: (name param1 param2 ...) => body
    // Strategy: fold params into nested Lams
    params => {
        Record(fields) -> {
            // Spread fields into parameter list
            let param_names = { ..fields }  // Get all parameter names
            // Build nested lambdas: (x) => (y) => (z) => body
            fold_params(param_names, body)
        };
        _ -> unreachable
    }
}

macro fold_params = (params: Record, body: Expr) => {
    // Convert { _0 = "x", _1 = "y" } into nested Lams
    // Base case handled by pattern exhaustiveness
    params => {
        Record({ _0 = name }) -> Lam(name, body);  // Last param
        Record({ _0 = name, ..rest }) -> {
            // Recursive case: wrap in lambda and recurse
            Lam(name, fold_params(rest, body))
        };
        Record({}) -> body;  // No params, just body
    }
}
```

### Example: Common Lisp's `when` Macro

**Lisp:**
```lisp
(defmacro when (test &rest body)
  `(if ,test (progn ,@body) nil))
```

**Auric:**
```auric
macro when = (ast: Expr) => {
    ast => {
        // Match: when(test, body1, body2, ...)
        // Transform to: test => { true -> { body1; body2; ... }; false -> {} }
        App(App(Var("when"), test), body) -> {
            // Build case expression
            Case(test, {
                true = { body },
                false = { Record({}) }
            })
        };
        _ -> unreachable
    }
}
```

### Example: Anaphoric Macros

**Lisp aif** (anaphoric if) - binds condition result to `it`:
```lisp
(defmacro aif (test then else)
  `(let ((it ,test))
     (if it ,then ,else)))
```

**Auric:**
```auric
macro aif = (ast: Expr) => {
    ast => {
        // Match: aif(test, then_branch, else_branch)
        App(App(App(Var("aif"), test), then_branch), else_branch) -> {
            // Transform to: let it = test; it => { true -> then; false -> else }
            Let("it", test,
                Case(Var("it"), {
                    true = { then_branch },
                    false = { else_branch }
                })
            )
        };
        _ -> unreachable
    }
}
```

### Example: Code-Walking for Free Variables

**Find all free variables in an expression** (common Lisp macro task):

```auric
macro free_vars = (ast: Expr) => {
    let go = (ast: Expr, bound: Record) => {
        ast => {
            Var(n) -> {
                // Check if n is in bound set
                bound => {
                    Record(fields) -> {
                        // If n is a field, it's bound
                        // Otherwise, it's free
                        // Return record of free vars
                        has_field(fields, n) => {
                            true -> Record({});
                            false -> Record({ n = {} })
                        }
                    };
                    _ -> unreachable
                }
            };

            Lam(param, body) -> {
                // Add param to bound set
                let new_bound = { ..bound, { param = {} } }
                go(body, new_bound)
            };

            App(f, a) -> {
                // Union of free vars from both sides
                let fvars_f = go(f, bound)
                let fvars_a = go(a, bound)
                { ..fvars_f, ..fvars_a }
            };

            _ -> Record({})  // No free vars in other cases
        }
    }

    go(ast, Record({}))  // Start with empty bound set
}
```

## What's Unified vs. Comptime-Only

### Unified (Same at Runtime & Comptime):

- ✓ Pattern matching: `value => { pattern -> result }`
- ✓ Let bindings: `let x = value in body`
- ✓ Lambdas: `(x) => body`
- ✓ Thunks: `() => expr` and `thunk()`
- ✓ Function calls: `f(x)`
- ✓ Records: `{ x = 1, y = 2 }` (no dot prefix!)
- ✓ Variants: Algebraic data types with constructors
- ✓ Field access: `record.field` or `record["field"]`
- ✓ Error handling: `unreachable` keyword

### Comptime-Only (No Runtime Equivalent):

- **Spread operator:** `..` (for record merging)
- **AST as variants:** At comptime, `Expr` is a variant type that can be pattern
  matched. At runtime, `Expr` doesn't exist (macros are already expanded).

### Key Insight: Everything Works the Same!

At comptime:

```auric
// Build AST using variant constructors
const ast = App(Var("f"), Var("x"))

// Destructure using pattern matching
ast => {
    App(f, a) -> ...;
    Var(n) -> ...;
    Thunk(body) -> ...;
}
```

At runtime:

```auric
// Build data using variant constructors
const user = User("Alice", 25)
const lazy = () => expensive()

// Destructure using pattern matching
user => {
    User(name, age) -> ...;
    Guest -> ...;
}
```

**The only differences:**

1. Comptime can use spread `..` operator
1. Comptime has access to `Expr` variant type (AST nodes)

## Design Rationale

### Why Comptime-Only Spread?

1. **Preserves Totality**

   - Runtime records are closed → exhaustiveness checking works
   - Comptime records can be open → macros are flexible

1. **Zig-Like Philosophy**

   - Comptime has extra power for metaprogramming
   - Runtime is predictable and type-safe

1. **Clear Separation**

   - Macros manipulate structure (comptime)
   - Programs manipulate values (runtime)

### Why Records, Not Lists?

1. **Auric's Native Structure**

   - Everything is records
   - Consistent with language design

1. **Type Safety**

   - Records have known fields
   - Better error messages

1. **Simplicity**

   - One data structure to learn
   - Not trying to be Lisp

### Why Same Syntax?

1. **Learnability**

   - Learn once, use everywhere
   - No special "macro syntax"

1. **Predictability**

   - Comptime code behaves like runtime code
   - Easy to reason about

1. **Zig-Inspired**

   - Comptime is not magic
   - Just evaluation at compile-time

### Why Bracket Syntax for Field Access?

**Primary syntax:** `record["field"]`

- Bracket notation is the canonical form
- Field name must be compile-time constant (preserves totality)
- Explicit and uniform

**Sugar:** `record.field` → `record["field"]`

- Dot notation desugars at parse time
- Just convenience, not a separate operation

**At comptime:**

```auric
macro index = (vec: Expr, i: Record[u8]) => {
    vec[i]  // Constructs FieldAccess(vec, i)
    // Or: vec._i (desugars to same thing)
}
```

**Totality preserved:**

- Only compile-time known field names allowed
- Runtime field computation: `record[compute_field()]` → Error!
- All field access statically checkable

### Why Dependent Types Eliminate Runtime Fold?

**Problem:** How do you iterate over record fields polymorphically at runtime?

**Traditional approach:** `fold_record(r, init, fn)` primitive

**Auric's approach:** Dependent types + closed records + pattern matching

1. **Records are closed** - All fields known statically (RecordT in type system)
1. **Dependent types track structure** - `Vec(n, T)` knows it has n indexed
   fields
1. **Pattern matching handles all cases** - Can destructure based on type info
1. **Recursion on type-level indices** - Iterate using the dependent index

**Example without fold:**

```auric
// Type tells us exactly what fields exist
const process = (r: RecordT { x: Int, y: Int, z: Int }) => {
    r => {
        .{ x = a, y = b, z = c } -> a + b + c  // Exhaustive pattern match
    }
}

// With dependent length index
const sum_vec = (n: Nat, v: Vec(n, Int)) => {
    n => {
        0 -> 0;  // Empty vector
        succ(m) -> {
            // Field name computed from type-level index
            let head = v["_" ++ nat_to_string(m)]  // Compile-time constant!
            head + sum_vec(m, v)
        }
    }
}
```

**Key insight:** The type system provides enough static information to eliminate
the need for a runtime fold primitive. You recurse on the TYPE structure, not
the VALUE structure.

## Totality: What Lisp and Zig Lack

Auric's key differentiator is **totality** - all programs are guaranteed to:
1. **Terminate** (no infinite loops)
2. **Cover all cases** (exhaustive pattern matching)
3. **Be type-safe** (no runtime type errors)

### Comparison

| Feature | Lisp | Zig | Auric |
|---------|------|-----|-------|
| **Macro power** | ✅ Full (s-expressions) | ✅ Full (comptime) | ✅ Full (variants) |
| **Systems performance** | ❌ GC overhead | ✅ Zero overhead | ✅ Zero overhead |
| **Exhaustiveness** | ❌ Optional | ❌ Optional | ✅ Enforced |
| **Termination** | ❌ Partial functions | ❌ Partial functions | ✅ Total functions |
| **Unified syntax** | ❌ Special macro syntax | ✅ Same syntax | ✅ Same syntax |

### Totality in Macros

**Non-exhaustive pattern match (compile error):**
```auric
macro bad_transform = (ast: Expr) => {
    ast => {
        App(f, a) -> ...;
        Var(n) -> ...;
        // ERROR: Missing cases for Lam, Thunk, Force, Record, Case!
    }
}
```

**Exhaustive pattern match (compiles):**
```auric
macro transform = (ast: Expr) => {
    ast => {
        App(f, a) -> App(transform(f), transform(a));
        Var(n) -> ast;
        Lam(p, b) -> Lam(p, transform(b));
        Thunk(body) -> Thunk(transform(body));
        Force(t) -> Force(transform(t));
        Record(fs) -> ast;  // TODO: transform fields
        Case(s, alts) -> ast;  // TODO: transform cases
    }
}
```

### Termination Checking

Auric enforces **structural recursion** - recursive calls must be on syntactic subterms:

**Valid (terminates):**
```auric
macro count_apps = (ast: Expr) => {
    ast => {
        App(f, a) -> 1 + count_apps(f) + count_apps(a);  // ✓ Recurse on subterms
        Lam(p, b) -> count_apps(b);                      // ✓ Recurse on subterm
        _ -> 0;
    }
}
```

**Invalid (doesn't terminate):**
```auric
macro infinite = (ast: Expr) => {
    infinite(ast)  // ✗ Not a subterm, infinite loop!
}
```

### Why This Matters for Systems Programming

**Lisp problem:** Macros can loop forever at compile time
```lisp
(defmacro infinite () (infinite))  ; Hangs compiler
```

**Zig problem:** Comptime can loop forever
```zig
comptime {
    while (true) {}  // Hangs compiler
}
```

**Auric solution:** Structural recursion guarantees termination
```auric
// All macros terminate - guaranteed by the type checker
macro transform = (ast: Expr) => { ... }  // ✓ Terminates
```

**Result:** Build times are predictable, compilation always finishes.

## The Three-Way Synthesis

Auric combines the best of three worlds:

### From Lisp: Homoiconicity and Macro Power

**What we borrowed:**
- Code as data (AST manipulation)
- Pattern matching on code structure
- Recursive transformations
- Quasiquoting (via spread `..`)

**What we improved:**
- Type-safe variant constructors instead of untyped lists
- Exhaustiveness checking on pattern matches
- Structural termination checking
- Better error messages (field names vs list positions)

### From Zig: Unified Comptime/Runtime

**What we borrowed:**
- Same syntax at compile-time and runtime
- `comptime` evaluation = `runtime` evaluation, just earlier
- Predictable compilation model
- No magic (everything is explicit)

**What we improved:**
- Totality (Zig comptime can infinite loop)
- Exhaustiveness (Zig switches are optional)
- Dependent types (Zig has limited compile-time types)
- Region-based memory instead of manual memory management

### From Rust: Systems Programming and Safety

**What we borrowed:**
- Familiar syntax (braces, semicolons, type annotations)
- Zero-cost abstractions
- Monomorphization (no runtime polymorphism cost)
- Lifetimes (regions in Auric)

**What we improved:**
- Simpler syntax (no lifetimes annotations in most cases)
- Total functions (no `panic!`, `unwrap()`, or `unreachable!()` at runtime)
- Simpler macro system (no token trees, just AST variants)
- Records instead of tuples/structs (unified model)

### The Result: A New Category

|  | Lisp | Zig | Rust | **Auric** |
|--|------|-----|------|-----------|
| **Macro power** | ✅ S-expr | ✅ Comptime | ⚠️ Token trees | ✅ **AST variants** |
| **Systems perf** | ❌ GC | ✅ Manual | ✅ Zero-cost | ✅ **Zero-cost** |
| **Memory safety** | ❌ GC only | ⚠️ Manual | ✅ Borrow checker | ✅ **Regions** |
| **Totality** | ❌ Partial | ❌ Partial | ❌ Partial | ✅ **Total** |
| **Type safety** | ⚠️ Dynamic | ✅ Static | ✅ Static | ✅ **Static + Dependent** |
| **Syntax** | ❌ S-expr | ✅ C-like | ✅ C-like | ✅ **Rust-like** |
| **Learning curve** | High (parens) | Medium | High (borrowck) | **Medium** |

**Auric's unique position:**
- Lisp's macro power with Rust's syntax
- Zig's comptime philosophy with totality guarantees
- Rust's systems performance with simpler memory model
- **The only total systems language with full macro power**

### Why This Matters

**For systems programming:**
- Predictable performance (no GC, direct compilation)
- Memory safety (regions, no manual management)
- Guaranteed termination (no infinite loops in production)

**For macro programming:**
- Full AST manipulation (like Lisp)
- Type-safe transformations (exhaustiveness checking)
- Guaranteed termination (no infinite macro expansion)

**For correctness:**
- Total functions (all code paths handled)
- Exhaustive patterns (no missed cases)
- Dependent types (length-indexed vectors, etc.)

**Example showing all three:**
```auric
// Macro that transforms AST (Lisp power)
macro inline_identity = (ast: Expr) => {
    ast => {
        App(Var("id"), x) -> x;  // Inline id(x) → x
        App(f, a) -> App(inline_identity(f), inline_identity(a));
        Lam(p, b) -> Lam(p, inline_identity(b));
        _ -> ast;  // Exhaustive (totality)
    }
}  // Compiles to zero-cost transformation (systems perf)

// Usage in systems code:
make_point = (x: i64, y: i64) -> { x: i64, y: i64 } = {
    // id() calls get inlined away by macro
    { x = id(x), y = id(y) }  // Becomes: { x = x, y = y }
}  // Zero runtime overhead, type-safe, stack-allocated
```

**Result:** Lisp's expressiveness, Rust's performance, and mathematical totality - all in one language.

## Next Steps

1. Implement AST destructuring primitives
1. Add spread operator `..` to parser (comptime-only)
1. Update macro expander to use unified syntax
1. Test with real macros (for, when, etc.)
1. Document totality guarantees with examples
