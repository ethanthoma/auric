# Auric Primitives vs Macros

**Goal:** Identify the minimal core and show what can be built with macros

---

## The Minimal Core: True Primitives

Following the lambda calculus tradition, here are the **irreducible primitives**:

### Tier 1: Computation (Lambda Calculus)

```auric
type Expr =
    | Var(name: Record[u8])              // Variable reference
    | Lam(params: Vec[Record[u8], n], body: Expr)  // Lambda abstraction
    | App(fn: Expr, args: Vec[Expr, n])  // Application
```

**These cannot be defined as macros** - they're the essence of computation.

### Tier 2: Data Structures

```auric
    | Record(fields: Dict[Record[u8], Expr])  // Record construction
    | FieldAccess(record: Expr, field: Record[u8])  // Field projection
    | Case(scrutinee: Expr, alts: Dict[Pattern, Expr])  // Pattern matching
```

**Why primitive?**
- **Records** - Fundamental data structure (could use Church encoding but impractical)
- **FieldAccess** - Necessary for efficiency (could use pattern matching but slow)
- **Case** - Pattern matching on ADTs (could encode but need for exhaustiveness)

### Tier 3: Types (For Polymorphism)

```auric
    | TyAbs(tv: Record[u8], body: Expr)  // Type abstraction: Λα. e
    | TyApp(fn: Expr, ty: Type)          // Type application: e[T]
```

**Why primitive?**
- Needed for parametric polymorphism
- Type erasure at runtime (compile-time construct)

### Tier 4: Literals

```auric
    | IntLit(value: int, ty: IntType)    // Integer literals
    | FloatLit(value: float, ty: FloatType)  // Float literals
    | CharLit(value: char)               // Character literals
```

**Could be macros, but:**
- Performance (direct compilation to machine types)
- Convenience (very common)

### Tier 5: Effects (Optional Extension)

```auric
    | Perform(effect: Record[u8], arg: Expr)  // Effect invocation
    | Handle(body: Expr, handlers: Dict[Record[u8], Expr])  // Effect handler
```

**Why primitive?**
- Algebraic effects need compiler support
- Can't be encoded as normal functions

---

## Total Primitives: **~13 constructs**

Compare to:
- **Scheme R4RS:** ~5 primitives (lambda, if, define, quote, set!)
- **Lambda calculus:** 3 (var, lambda, app)
- **ML:** ~8 (var, lam, app, let, case, ADT construction)

Auric is reasonable but could be smaller.

---

## Everything Else is Macros

### Control Flow (All Macros!)

#### 1. If-Then-Else

**Primitive `if` is NOT needed!** It's a macro over Case:

```auric
// if is a macro:
macro {
    if $test { $then } else { $else } =>
        $test => {
            @true -> $then;
            @false -> $else
        }
}

// Usage:
if x > 0 { "positive" } else { "non-positive" }

// Expands to:
(x > 0) => {
    @true -> "positive";
    @false -> "non-positive"
}
```

#### 2. When/Unless

```auric
macro {
    when $test { $body } =>
        if $test { $body } else { {} }
}

macro {
    unless $test { $body } =>
        if !($test) { $body } else { {} }
}
```

#### 3. Cond (Multi-way Conditional)

```auric
macro {
    cond {
        $test1 => $body1;
        $test2 => $body2;
        ...
        _ => $default
    } =>
        if $test1 { $body1 }
        else if $test2 { $body2 }
        ...
        else { $default }
}
```

#### 4. Boolean Operators (Short-Circuit)

```auric
// && is a macro (short-circuits):
macro {
    $a && $b =>
        if $a { $b } else { @false }
}

// || is a macro:
macro {
    $a || $b =>
        if $a { @true } else { $b }
}

// ! can be a function:
not = (b) => b => {
    @true -> @false;
    @false -> @true
}
```

### Bindings (All Macros!)

#### 1. Let (Non-Recursive)

**Let is NOT primitive!** It desugars to lambda application:

```auric
// let is a macro:
macro {
    let $x = $v; $body =>
        (($x) => $body)($v)
}

// Example:
let x = 5; x + 1

// Expands to:
((x) => x + 1)(5)
```

#### 2. Let (Recursive)

```auric
// rec let uses fixed-point combinator:
macro {
    let rec $f = $v; $body =>
        let $f = fix(($f) => $v); $body
}

// Where fix is:
fix = (f) => (x) => f((y) => x(x)(y))((x) => f((y) => x(x)(y)))
```

#### 3. Multiple Bindings

```auric
macro {
    let $x = $v; let $y = $w; $body =>
        let $x = $v; (let $y = $w; $body)
}

// Desugars to nested lambdas:
// ((x) => ((y) => body)(w))(v)
```

#### 4. Const (Same as Let)

```auric
macro {
    const $x = $v; $body => let $x = $v; $body
}
```

### Sequences (Macro!)

```auric
// Sequences desugar to nested lets:
macro {
    { $e1; $e2; $e3 } =>
        let _ = $e1;
        let _ = $e2;
        $e3
}

// Example:
{ print("a"); print("b"); 42 }

// Expands to:
let _ = print("a");
let _ = print("b");
42
```

### Loops (All Macros!)

#### 1. For Loop

```auric
macro {
    for $v in $lst { $body } =>
        map(($v) => $body, $lst)
}
```

#### 2. While Loop

```auric
macro {
    while $test { $body } =>
        let rec loop = () => {
            if $test {
                let _ = $body;
                loop()
            } else {
                {}
            }
        };
        loop()
}
```

#### 3. Loop (Infinite)

```auric
macro {
    loop { $body } =>
        let rec loop = () => {
            let _ = $body;
            loop()
        };
        loop()
}
```

### Data Structures (All Macros!)

#### 1. Tuples

```auric
// Tuples are just records with indexed fields:
macro {
    ($e1, $e2, $e3) =>
        { _0 = $e1, _1 = $e2, _2 = $e3 }
}

// Tuple type:
macro {
    ($T1, $T2, $T3) =>
        { _0: $T1, _1: $T2, _2: $T3 }
}
```

#### 2. Arrays/Lists

```auric
// Array literals:
macro {
    [$e1, $e2, $e3] =>
        { _0 = $e1, _1 = $e2, _2 = $e3 }
}

// Vec type with dependent length:
type Vec(T, n) = Record with n fields of type T
```

#### 3. Strings

```auric
// String literals:
macro {
    "hello" =>
        { _0 = 'h', _1 = 'e', _2 = 'l', _3 = 'l', _4 = 'o' }
        : Vec[u8, 5]
}
```

### Type Definitions (Macro!)

#### ADT Definitions

```auric
// Type definitions can be macros:
macro {
    type Option(T) = {
        Some <- { value: T };
        None <- {}
    } =>
        // Generate constructor functions:
        Some = (value) => @Some(value);
        None = @None;
        // And type definition
        type Option(T) = ...
}
```

### Pattern Matching Sugar (Macros!)

#### 1. Function with Pattern Matching

```auric
// Multi-clause function:
macro {
    fn $name($param) = {
        $pat1 -> $body1;
        $pat2 -> $body2;
        ...
    } =>
        $name = ($param) => $param => {
            $pat1 -> $body1;
            $pat2 -> $body2;
            ...
        }
}
```

#### 2. Match Expression

```auric
// Match is just sugar for case:
macro {
    match $e {
        $pat1 -> $body1;
        $pat2 -> $body2;
        ...
    } =>
        $e => {
            $pat1 -> $body1;
            $pat2 -> $body2;
            ...
        }
}
```

#### 3. Guards in Patterns

```auric
macro {
    $e => {
        $pat when $guard -> $body;
        ...
    } =>
        $e => {
            $pat -> if $guard { $body } else { unreachable };
            ...
        }
}
```

### Special Forms (Macros!)

#### 1. Return

```auric
// return as early exit (using effects or exceptions):
macro {
    return $e =>
        perform(Return, $e)
}

// Function handles return:
macro {
    fn $name($params) { $body } =>
        $name = ($params) =>
            handle $body {
                Return(v) -> v
            }
}
```

#### 2. Break/Continue

```auric
macro {
    break =>
        perform(Break, {})
}

macro {
    continue =>
        perform(Continue, {})
}
```

#### 3. Assert

```auric
macro {
    assert $test =>
        if !($test) {
            panic("Assertion failed")
        }
}
```

---

## Operator Desugaring (Macros!)

### Arithmetic Operators

**Option 1: Desugar to function calls**
```auric
macro {
    $a + $b => add($a, $b)
    $a - $b => sub($a, $b)
    $a * $b => mul($a, $b)
    $a / $b => div($a, $b)
}

// Where add, sub, etc. are builtins
```

**Option 2: Keep as primitives for efficiency**
- But could still be builtins rather than AST nodes

### Comparison Operators

```auric
macro {
    $a < $b => lt($a, $b)
    $a > $b => gt($a, $b)
    $a <= $b => le($a, $b)
    $a >= $b => ge($a, $b)
    $a == $b => eq($a, $b)
    $a != $b => ne($a, $b)
}
```

### Chained Comparisons

```auric
macro {
    $a < $b < $c =>
        let x = $b;
        lt($a, x) && lt(x, $c)
}
```

---

## What About Thunks?

### Thunk and Force (Primitives?)

**Option 1: Make primitive**
```auric
type Expr =
    | Thunk(body: Expr)      // () => expr
    | Force(thunk: Expr)     // thunk()
```

**Option 2: Encode as lambda**
```auric
// Thunk = lambda with unit parameter:
macro {
    () => $e => (dummy) => $e
}

// Force = apply to unit:
macro {
    $thunk() => $thunk({})
}
```

**Recommendation:** Make primitive for clarity and optimization

---

## Minimal Auric Core

### Absolute Minimum (8 constructs)

If we're ruthless about minimalism:

```auric
type Expr =
    // Lambda calculus core:
    | Var(name)
    | Lam(params, body)
    | App(fn, args)

    // Data structures:
    | Record(fields)
    | FieldAccess(record, field)

    // Pattern matching:
    | Case(scrutinee, alts)

    // Types:
    | TyAbs(tv, body)
    | TyApp(fn, ty)
```

**Everything else is macros or builtins!**

Literals, if, let, sequences, loops, operators - all macros.

### Practical Core (13 constructs)

For practicality, add:

```auric
    // Literals (efficiency):
    | IntLit(value, ty)
    | FloatLit(value, ty)
    | CharLit(value)

    // Effects (algebraic effects):
    | Perform(effect, arg)
    | Handle(body, handlers)
```

---

## Macro Coverage Analysis

### How Much is Macro-Defined?

| Category | Total Constructs | Primitives | Macros | % Macro |
|----------|------------------|------------|---------|---------|
| Control flow | 10 | 1 (Case) | 9 | 90% |
| Bindings | 5 | 0 | 5 | 100% |
| Sequences | 1 | 0 | 1 | 100% |
| Loops | 3 | 0 | 3 | 100% |
| Data structures | 5 | 2 | 3 | 60% |
| Operators | 20+ | 0 | 20+ | 100% |
| Pattern matching | 5 | 1 | 4 | 80% |
| Special forms | 5 | 0 | 5 | 100% |
| **Total** | **~54** | **~13** | **~41** | **~76%** |

**Three quarters of the language is macros!**

---

## Comparison to Other Languages

### Scheme

**Primitives:** ~5
- lambda, if, define, quote, set!

**Macros:** Everything else
- let, cond, and, or, when, unless, case, etc.

**Macro coverage:** ~90%

### Rust

**Primitives:** ~50+
- Many built-in constructs

**Macros:** Limited
- Mostly for pattern repetition
- Can't define control flow

**Macro coverage:** ~10%

### Lisp (Common Lisp)

**Primitives:** ~25 special forms
- lambda, if, let, progn, setq, quote, etc.

**Macros:** Extensive
- loop, when, unless, cond, etc.

**Macro coverage:** ~50%

### Auric (Proposed)

**Primitives:** ~13
- Var, Lam, App, Record, FieldAccess, Case, TyAbs, TyApp, literals, effects

**Macros:** Extensive
- if, let, sequences, loops, operators, data structures, etc.

**Macro coverage:** ~76%

**Auric is closer to Scheme than Rust in philosophy!**

---

## Benefits of Macro-Heavy Design

### 1. Small Core

- Easier to implement
- Easier to verify
- Easier to optimize
- Fewer edge cases

### 2. Extensibility

- Users can define new control flow
- Can experiment with new features
- Library-defined language extensions

### 3. Consistency

- Everything follows same rules
- Macros use same pattern matching
- No special cases

### 4. Understandability

- Can see how features work
- Can macroexpand to understand
- No magic

### 5. Evolvability

- Can change surface syntax without changing core
- Can deprecate old syntax gradually
- Can add new syntax without compiler changes

---

## Example: Building Up From Core

### Starting with just Var, Lam, App, Case, Record

```auric
// Primitives only:
factorial = (n) => n => {
    @zero -> @one;
    @succ(m) -> mul(n, factorial(m))
}

// Add 'if' macro:
factorial = (n) =>
    if n == 0 {
        1
    } else {
        n * factorial(n - 1)
    }

// Add 'let' macro:
factorial = (n) => {
    let base = if n == 0 { 1 };
    let rec_case = n * factorial(n - 1);
    if n == 0 { base } else { rec_case }
}

// Add operator macros:
factorial = (n) =>
    if (n == 0) then 1 else (n * factorial(n - 1))
```

**Same primitive core, different surface syntax via macros!**

---

## Implications for Implementation

### Phase 1: Implement Core (~4 weeks)

1. Var, Lam, App - Basic lambda calculus
2. Record, FieldAccess - Data structures
3. Case - Pattern matching
4. Literals - IntLit, etc.

**Can now run programs** (albeit with verbose syntax)

### Phase 2: Implement Macro System (~6 weeks)

1. Multi-arg App/Lam
2. Quasiquote syntax
3. Pattern on syntax
4. Macro expander

**Can now define surface syntax**

### Phase 3: Standard Library Macros (~2 weeks)

1. if, when, unless, cond
2. let, const, sequences
3. for, while, loop
4. Operators (+, -, *, /, <, >, ==, etc.)
5. Data structure sugar (tuples, arrays, strings)

**Now have usable language!**

### Phase 4: Advanced Features (~6 weeks)

1. Type system (polymorphism, dependent types)
2. Effects
3. Optimizations

**Production-ready language**

**Total:** ~18 weeks from primitives to full language

---

## Recommendations

### 1. Embrace Macro-Heavy Design

- Keep core minimal (~13 primitives)
- Define everything else as macros
- Follow Scheme philosophy, not Rust

### 2. Expose Macro Expansion

```auric
// User can see how their code expands:
macroexpand(if x > 0 { 1 } else { -1 })
// → x > 0 => { @true -> 1; @false -> -1 }

macroexpand_all(
    let x = 5;
    let y = x + 1;
    y * 2
)
// → ((x) => ((y) => mul(y, 2))(add(x, 1)))(5)
```

### 3. Standard Library of Macros

Create `std/prelude.au` with all common macros:
- Control flow (if, when, unless, cond)
- Bindings (let, const)
- Operators (arithmetic, comparison, boolean)
- Data structures (tuples, lists, strings)
- Loops (for, while, loop)

**Users import automatically, or can define their own!**

### 4. Allow User-Defined Syntax

```auric
// User can define their own control flow:
macro {
    repeat $n times { $body } =>
        for _ in range(0, $n) { $body }
}

// Or their own operators:
macro {
    $a |> $f => $f($a)  // Pipeline operator
}
```

---

## Summary

**Auric's primitives:**
- ~13 core constructs
- ~76% of language is macros
- Similar philosophy to Scheme
- Highly extensible

**Everything else is built with macros:**
- Control flow (if, when, unless, cond)
- Bindings (let, const, sequences)
- Loops (for, while, loop)
- Data structures (tuples, lists, strings)
- Operators (arithmetic, comparison)
- Special forms (return, break, continue)

**This makes Auric:**
- ✅ Small core (easy to implement)
- ✅ Highly extensible (users can add syntax)
- ✅ Evolvable (change surface without changing core)
- ✅ Understandable (macroexpand shows how things work)
- ✅ Consistent (everything follows same rules)

**Like Scheme: Minimal core, maximal power through macros.**
