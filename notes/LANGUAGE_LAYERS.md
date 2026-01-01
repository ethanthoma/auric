# Auric Language Architecture: Layered Design

**Philosophy:** Small core + powerful macros = expressive language

---

## The Layer Cake

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: User-Defined Syntax (100% Macros)                 │
│  - Domain-specific languages                                 │
│  - Custom control flow                                       │
│  - Project-specific abstractions                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Standard Library (100% Macros)                    │
│  - if, when, unless, cond                                   │
│  - let, const, sequences                                     │
│  - for, while, loop                                         │
│  - Tuples, arrays, strings                                  │
│  - Operators (+, -, *, /, <, >, ==, etc.)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Macro System                                      │
│  - Pattern matching on syntax                               │
│  - Quasiquoting                                             │
│  - Hygiene                                                  │
│  - Macro expansion                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Core Language (13 Primitives)                     │
│  - Var, Lam, App (lambda calculus)                         │
│  - Record, FieldAccess (data)                               │
│  - Case (pattern matching)                                  │
│  - TyAbs, TyApp (types)                                    │
│  - Literals (efficiency)                                    │
│  - Perform, Handle (effects)                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: Runtime / Code Generator                          │
│  - Type checking / Elaboration                              │
│  - Optimization                                             │
│  - Code generation (LLVM/C)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: The Core (13 Primitives)

### What You CANNOT Define as Macros

```auric
// Lambda calculus (3):
Var(name)                  // x
Lam(params, body)          // (x, y) => body
App(fn, args)              // f(x, y)

// Data structures (2):
Record(fields)             // { x = 1, y = 2 }
FieldAccess(record, field) // point.x

// Pattern matching (1):
Case(scrutinee, alts)      // x => { pattern -> result }

// Polymorphism (2):
TyAbs(tv, body)            // Λα. body
TyApp(fn, ty)              // f[Int]

// Literals (3):
IntLit(42, i64)            // 42
FloatLit(3.14, f64)        // 3.14
CharLit('a')               // 'a'

// Effects (2):
Perform(effect, arg)       // perform(Print, "hello")
Handle(body, handlers)     // handle { ... }
```

**Total: 13 constructs**

This is the bedrock - implemented in the compiler/interpreter.

---

## Layer 2: The Macro System

### Meta-Language for Defining Syntax

```auric
// Define new syntax:
macro {
    'pattern' => 'template'
}

// With features:
- Pattern matching on surface syntax
- Quasiquoting (quote/unquote)
- Type annotations in patterns
- Guards, ellipsis, alternatives
- Automatic hygiene
```

**The macro system itself is NOT a macro** - it's part of the compiler.

---

## Layer 3: Standard Library (All Macros!)

### Control Flow (9 macros)

```auric
// if-then-else:
if $test { $then } else { $else } =>
    $test => { @true -> $then; @false -> $else }

// when:
when $test { $body } =>
    if $test { $body } else { {} }

// unless:
unless $test { $body } =>
    if !($test) { $body } else { {} }

// cond:
cond { $test1 => $body1; $test2 => $body2; _ => $default } =>
    if $test1 { $body1 } else if $test2 { $body2 } else { $default }

// and (short-circuit):
$a && $b => if $a { $b } else { @false }

// or (short-circuit):
$a || $b => if $a { @true } else { $b }

// not (function, not macro):
not = (b) => b => { @true -> @false; @false -> @true }
```

### Bindings (5 macros)

```auric
// let (desugars to lambda application):
let $x = $v; $body =>
    (($x) => $body)($v)

// let rec (fixed-point combinator):
let rec $f = $v; $body =>
    let $f = fix(($f) => $v); $body

// const (same as let):
const $x = $v; $body =>
    let $x = $v; $body

// Sequences:
{ $e1; $e2; $e3 } =>
    let _ = $e1; let _ = $e2; $e3

// Multiple lets:
let $x = $v; let $y = $w; $body =>
    let $x = $v; (let $y = $w; $body)
```

### Loops (3 macros)

```auric
// for:
for $v in $lst { $body } =>
    map(($v) => $body, $lst)

// while:
while $test { $body } =>
    let rec loop = () => {
        if $test { let _ = $body; loop() } else { {} }
    };
    loop()

// loop (infinite):
loop { $body } =>
    let rec loop = () => { let _ = $body; loop() };
    loop()
```

### Data Structures (3 macros)

```auric
// Tuples:
($e1, $e2, $e3) =>
    { _0 = $e1, _1 = $e2, _2 = $e3 }

// Arrays:
[$e1, $e2, $e3] =>
    { _0 = $e1, _1 = $e2, _2 = $e3 }

// Strings:
"hello" =>
    { _0 = 'h', _1 = 'e', _2 = 'l', _3 = 'l', _4 = 'o' }
```

### Operators (20+ macros)

```auric
// Arithmetic:
$a + $b => add($a, $b)
$a - $b => sub($a, $b)
$a * $b => mul($a, $b)
$a / $b => div($a, $b)
$a % $b => mod($a, $b)

// Comparison:
$a < $b => lt($a, $b)
$a > $b => gt($a, $b)
$a <= $b => le($a, $b)
$a >= $b => ge($a, $b)
$a == $b => eq($a, $b)
$a != $b => ne($a, $b)

// Bitwise:
$a & $b => bitand($a, $b)
$a | $b => bitor($a, $b)
$a ^ $b => bitxor($a, $b)
$a << $b => shl($a, $b)
$a >> $b => shr($a, $b)

// Unary:
-$a => neg($a)
!$a => not($a)
~$a => bitnot($a)
```

**Total standard library: ~41 macros**

All defined in `std/prelude.au`, automatically imported.

---

## Layer 4: User-Defined Syntax

### Examples of What Users Can Define

#### 1. Pipeline Operator

```auric
macro {
    $a |> $f => $f($a)
}

// Usage:
data
  |> filter(is_even)
  |> map(double)
  |> sum
```

#### 2. Try-Catch

```auric
macro {
    try { $body } catch $e { $handler } =>
        handle $body {
            Error($e) -> $handler
        }
}
```

#### 3. Async/Await

```auric
macro {
    async { $body } =>
        perform(Async, () => $body)
}

macro {
    await $expr =>
        perform(Await, $expr)
}
```

#### 4. SQL-Like Queries

```auric
macro {
    select $fields from $table where $cond =>
        filter(
            (row) => $cond,
            map((row) => { $fields }, $table)
        )
}

// Usage:
select { name, age } from users where age > 18
```

#### 5. Testing DSL

```auric
macro {
    test $name { $body } =>
        register_test($name, () => $body)
}

macro {
    assert_eq($a, $b) =>
        if !($a == $b) {
            panic("Assertion failed: " ++ stringify($a) ++ " != " ++ stringify($b))
        }
}

// Usage:
test "addition works" {
    assert_eq(1 + 1, 2)
}
```

#### 6. Pattern Guards

```auric
macro {
    $e => {
        $pat if $guard -> $body;
        ...
    } =>
        $e => {
            $pat -> if $guard { $body } else { unreachable };
            ...
        }
}
```

---

## Coverage Analysis

### What Percentage is Macro-Defined?

| Category | Primitives | Macros | % Macro |
|----------|-----------|--------|---------|
| **Core computation** | 3 | 0 | 0% |
| **Data structures** | 2 | 3 | 60% |
| **Pattern matching** | 1 | 4 | 80% |
| **Types** | 2 | 0 | 0% |
| **Literals** | 3 | 3 | 50% |
| **Effects** | 2 | 0 | 0% |
| **Control flow** | 0 | 9 | 100% |
| **Bindings** | 0 | 5 | 100% |
| **Loops** | 0 | 3 | 100% |
| **Operators** | 0 | 20+ | 100% |
| **TOTAL** | **13** | **~47** | **~78%** |

**Four-fifths of the language is macros!**

---

## Comparison to Other Languages

### Language Minimalism Spectrum

```
More Primitives ←──────────────────────────────────→ More Macros

C/C++                 Rust            Lisp         Scheme        Auric
  │                    │               │             │            │
  ▼                    ▼               ▼             ▼            ▼
~200              ~50 prims        ~25 prims     ~5 prims    ~13 prims
prims             ~10% macro       ~50% macro    ~90% macro  ~78% macro
~0% macro         coverage         coverage      coverage    coverage
coverage
```

**Auric sits between Lisp and Scheme:**
- More minimal than Lisp
- Less minimal than Scheme
- Much more minimal than Rust/C++

---

## Benefits of Layered Architecture

### 1. Separation of Concerns

```
User syntax (Layer 4)
    ↓ (macroexpand)
Standard syntax (Layer 3)
    ↓ (macroexpand)
Core syntax (Layer 1)
    ↓ (typecheck + compile)
Machine code (Layer 0)
```

Each layer has a clear responsibility.

### 2. Evolvability

```auric
// Want to change 'if' syntax?
// Just update the macro - core unchanged!

// Old:
if test { then } else { else }

// New:
test ? then : else

// Just change one macro definition!
macro {
    $test ? $then : $else =>
        $test => { @true -> $then; @false -> $else }
}
```

### 3. Understandability

```auric
// User sees:
let x = 5;
if x > 0 { "pos" } else { "neg" }

// Macroexpand once:
((x) => if x > 0 { "pos" } else { "neg" })(5)

// Macroexpand again:
((x) => x > 0 => {
    @true -> "pos";
    @false -> "neg"
})(5)

// This is core! No more macros.
```

Users can see exactly how things work.

### 4. Extensibility

```auric
// Language doesn't have pattern guards?
// User can add them!

macro {
    $e => { $pat when $guard -> $body; ... } =>
        $e => { $pat -> if $guard { $body } else { unreachable }; ... }
}

// Now pattern guards work!
```

Users aren't limited by language designer's choices.

### 5. Testability

```auric
// Can test each layer independently:

// Test core:
((x) => x + 1)(5)  // Should return 6

// Test macro expansion:
assert_eq(
    macroexpand(let x = 5; x + 1),
    ((x) => x + 1)(5)
)

// Test optimization:
assert_eq(
    optimize(((x) => x + 1)(5)),
    6  // Constant folded
)
```

---

## Implementation Strategy

### Phase 1: Core (4 weeks)

Implement the 13 primitives:
- Lambda calculus (Var, Lam, App)
- Data (Record, FieldAccess, Case)
- Types (TyAbs, TyApp)
- Literals
- Effects (if desired)

**Result:** Can run programs (with verbose syntax)

### Phase 2: Macro System (6 weeks)

Implement:
- Multi-arg App/Lam
- Quasiquote syntax
- Pattern matching on syntax
- Macro expander
- Hygiene

**Result:** Can define surface syntax

### Phase 3: Standard Library (2 weeks)

Define ~41 macros:
- Control flow (if, when, unless, etc.)
- Bindings (let, const)
- Loops (for, while, loop)
- Operators
- Data structure sugar

**Result:** Usable language

### Phase 4: Type System (4 weeks)

Implement:
- Type checking
- Polymorphism
- Dependent types
- Type inference

**Result:** Safe language

### Phase 5: Optimization (2 weeks)

Implement:
- Constant folding
- Inlining
- Dead code elimination
- Region analysis

**Result:** Fast language

**Total: ~18 weeks**

---

## Summary: The Power of Layers

**Layer 1 (Primitives):**
- 13 constructs
- Implements computation + data + types
- Irreducible

**Layer 2 (Macros):**
- Meta-language for syntax
- Pattern matching + quasiquoting
- Part of compiler

**Layer 3 (Standard Library):**
- ~41 macros
- Defines convenient syntax
- Editable by users

**Layer 4 (User Code):**
- Unlimited extensions
- Domain-specific languages
- Project-specific abstractions

**This gives us:**
- ✅ Small core (easy to implement/verify)
- ✅ Powerful macros (Lisp-level)
- ✅ Extensible (users add syntax)
- ✅ Evolvable (change surface not core)
- ✅ Understandable (macroexpand shows all)
- ✅ Type-safe (checked after expansion)
- ✅ Total (termination guaranteed)

**Auric achieves:**
- Scheme's minimalism
- Lisp's macro power
- Rust's type safety
- Unique totality

**All in one language!**
