# Auric Language Design

This document captures the core syntax and type system design decisions for
Auric.

## Design Principles

1. **Duality**: Introduction (`->`) and elimination (`<-`) are syntactic duals
2. **Uniformity**: One structure primitive (`{}`) for records, tuples, and
   arrays
3. **Totality**: No general recursion — only folds (data) and unfolds (codata)
4. **Effects**: Algebraic effects for allocation, mutation, IO — handlers scope
   effects
5. **Macros**: Most syntax is sugar defined via macros in user-space

## Core Primitives

### Thunks and Application

`()` represents delayed computation:

```
() -> e                 // intro: create a thunk (delay)
e()                     // elim: force a thunk

(x) -> e                // intro: function (thunk with binding)
f(x)                    // elim: application
```

### Structures

`{}` is the universal structure primitive:

```
{ }                     // empty structure / unit
{ a, b, c }             // positional fields
{ x = a, y = b }        // named fields
{ first, ..rest }       // destructuring pattern
```

### Arrows as Duals

`->` introduces, `<-` eliminates:

```
// Intro: build a function
(x: Int) -> x + 1

// Elim: pattern match / destructure
val <- {
    Some(x) -> x,
    None -> 0
}
```

Each branch in a match still uses `->` because it introduces a result.

## Type System

### Unified Foundation

Auric's type system is built on two ideas:

1. **Types are sets** — with restricted operations (union, intersection,
   refinement)
2. **Dependent indices** — types can depend on values, but no proof terms
   required

```
T ::=
    | Int | Bool | ...              // base sets
    | { row }                       // structure (product)
    | A | B                         // union
    | A & B                         // intersection
    | (A) -> B                      // function
    | T { P }                       // refinement (set comprehension)
    | &T                            // reference
```

The compiler infers dependent indices where possible. When it can't prove
properties statically, it falls back to runtime checks.

### Structures

`{ }` is the **single primitive** for all product types. Records, tuples, and
arrays are the same thing — contiguous memory.

```
{ }                     // unit (empty structure)
{ T }                   // one field
{ T, U, V }             // three fields (tuple)
{ x: T, y: U }          // named fields (record)
{ T..n }                // n fields of type T (array)
{ T.. }                 // ? fields of type T (slice)
```

**Key insight:** These are equivalent:

```
{ Int, Int, Int }  ≡  { Int..3 }     // same type, same memory layout
{ T }              ≡  { T..1 }       // single-element structure
```

The `..n` syntax is shorthand for repetition. The compiler optimizes layout, but
semantically it's all just contiguous fields.

**Slices** are existentially quantified — size unknown at compile time:

```
{ T.. }  ≡  ∃n. { ptr: &T, len: n }  // fat pointer at runtime
```

### Row Polymorphism

The `..` operator captures "the rest" of a row:

```
// Function polymorphic over record structure
get_x : { x: T, ..r } -> T =
    (rec) -> rec[.x]

// Works on any record with field x
get_x({ x = 1 })                    // 1
get_x({ x = 1, y = 2, z = 3 })      // 1
```

### Field Names as Values

Field names are first-class values:

```
.x              // named field literal
.0              // positional field literal (Fin-like)
```

### Uniform Indexing

All structures use the same indexing syntax:

```
// Static access (compile-time known)
s[.x]                   // named field
s[.0]                   // positional field

// Dynamic access
s[i]                    // i: Fin(n) for sized
s[i]?                   // runtime checked, returns Maybe
s[i]!                   // unchecked (unsafe)
```

Sugar: `s.x` desugars to `s[.x]`.

### Destructuring with `..`

The `..` operator enables pattern matching on structures:

```
arr: { Int..5 }

// Bind first and rest
{ first, ..rest } = arr
// first: Int
// rest: { Int..4 }

// Bind init and last
{ ..init, last } = arr
// init: { Int..4 }
// last: Int

// In pattern matching (structural recursion)
sum : { Int..n } -> Int =
    (arr) -> arr <- {
        { } -> 0,
        { x, ..xs } -> x + sum(xs)
    }
```

### Dependent Indices

Sizes are **values** that flow through the type system. No proof terms — the
compiler infers and checks:

```
{ T..n }                // n is a value (inferred or explicit)
{ T..3 }                // n = 3 (literal)
{ T.. }                 // n = ? (existential, runtime)

// Size polymorphism — n and m inferred from arguments
concat : { T..n } -> { T..m } -> { T..n + m }

// Size arithmetic in types
split : { T..n + m } -> { { T..n }, { T..m } }
```

**Inference examples:**

```
let arr = { 1, 2, 3 }           // arr : { Int..3 }, n inferred from literal
let doubled = concat(arr, arr)  // doubled : { Int..6 }, arithmetic inferred

// When size unknown, becomes existential (slice)
let slice = arr[i..]            // slice : { Int.. }
```

### Fin for Safe Indexing

`Fin(n)` represents natural numbers less than n:

```
arr : { Int..5 }
i : Fin(5)
arr[i]                  // safe, total

// Literal indices convert to Fin
arr[.3]                 // .3 : Fin(5), safe
arr[.5]                 // ERROR: 5 not in Fin(5)
```

### Slicing

```
arr : { Int..10 }

// Static bounds (size preserved)
arr[2..5]               // : { Int..3 }

// Dynamic bounds (becomes slice)
arr[i..j]               // : { Int.. }
```

### Set Operations

Types support restricted set operations:

```
// Union — value is A or B
A | B

// Intersection — value is both A and B (for refinements)
A & B

// Examples
Int | String                    // either an int or string
Int & { > 0 }                   // int AND positive (same as Int { > 0 })
{ x: Int, ..r } & { y: Int, ..s }  // has both x and y fields
```

**Union** is useful for sum types and optional values:

```
Maybe(T) = T | None
Result(T, E) = T | E
```

**Intersection** is primarily for combining refinements:

```
Int & { > 0 } & { < 100 }       // positive and less than 100
Int { > 0 && < 100 }            // equivalent, more concise
```

**No negation** — `¬T` is not supported (would break totality).

## Refinement Types

Refinement types combine a base type with a predicate that constrains values.

### Basic Form

```
T { predicate }         // values of T where predicate holds
T { x | predicate }     // explicit binder
```

Examples:

```
Int { > 0 }             // positive integers
Int { >= 0 }            // natural numbers
Int { x | x >= lo && x <= hi }  // bounded
```

### Dependent Refinements

Refinements can reference other bindings in scope:

```
// Index must be less than array length
get : (arr: { T..n }, i: Int { >= 0 && < n }) -> T

// High must be >= low
clamp : (lo: Int, hi: Int { >= lo }, val: Int) -> Int { >= lo && <= hi }
```

### Sized Types as Refinements

Sized arrays and `Fin` are special cases of refinements:

```
{ T..n }    ===    { arr: Array(T) | len(arr) = n }
Fin(n)      ===    Int { >= 0 && < n }
```

### Allowed Predicates

For decidable type checking, predicates are restricted to **linear arithmetic**:

```
// Allowed (Presburger arithmetic - decidable)
Int { n > 0 }
Int { n + m < 10 }
Int { n >= lo && n <= hi }

// Not directly allowed
Int { prime?(n) }       // arbitrary predicate
```

### Reflected Functions

Since Auric functions are **total** and **pure**, they can be reflected into the
refinement logic. A reflected function becomes axioms the solver can reason
about:

```
// Total function
len : { T.. } -> Nat =
    (arr) -> arr <- {
        { } -> 0,
        { x, ..xs } -> 1 + len(xs)
    }

// Now usable in refinements
head : (arr: { T.. } { len(arr) > 0 }) -> T

sorted : { Int.. } -> Bool =
    (arr) -> arr <- {
        { } -> True,
        { _ } -> True,
        { x, y, ..rest } -> x <= y && sorted({ y, ..rest })
    }

// Use in refinement
insert_sorted : (x: Int, arr: { Int.. } { sorted(arr) })
             -> { Int.. } { sorted }
```

Requirements for a function to be reflected:

1. **Total**: Must terminate on all inputs
2. **Pure**: No side effects
3. **First-order**: No higher-order arguments (SMT limitation)

The compiler reflects the function definition as axioms for the SMT solver.
Fuel/depth limits prevent infinite unfolding of recursive definitions.

### Refinement Hierarchy

| Level           | Predicates               | Decidability           | Power          |
| --------------- | ------------------------ | ---------------------- | -------------- |
| Presburger      | `<`, `+`, `-`, constants | Always decidable       | Low            |
| + Uninterpreted | `f(x) = f(y)`            | Decidable              | Medium         |
| + Reflected     | `len(arr) > 0`           | Decidable (total/pure) | High           |
| Arbitrary       | Any predicate            | Undecidable            | Full dependent |

Auric uses reflected functions, hitting the sweet spot of expressiveness and
decidability.

## Data and Codata

Types are defined by their introduction or elimination rules.

### Data (Inductive)

Defined by constructors (intro rules). Eliminated by pattern matching.

```
data Nat {
    -> Zero,
    Nat -> Succ
}

// Construction
Zero
Succ(Succ(Zero))

// Elimination (fold)
n <- {
    Zero -> 0,
    Succ(m) -> 1 + recurse(m)
}
```

### Codata (Coinductive)

Defined by destructors (elim rules). Introduced by providing observations.

```
codata Stream(T) {
    head <- T,
    tail <- Stream(T)
}

// Construction (unfold)
ones : Stream(Nat) = {
    head -> Succ(Zero),
    tail -> ones
}

// Elimination
ones.head               // Succ(Zero)
ones.tail.head          // Succ(Zero)
```

### Duality Summary

| Data (Inductive)        | Codata (Coinductive)       |
| ----------------------- | -------------------------- |
| Defined by constructors | Defined by destructors     |
| Eliminated by matching  | Introduced by observations |
| Finite                  | Potentially infinite       |
| `->` in definition      | `<-` in definition         |

## Syntax Summary

### Types

```
{ x: T, y: U }          // named fields (record)
{ T, U, V }             // positional fields (tuple)
{ T..n }                // n repeated fields (sized array)
{ T.. }                 // unknown repeated fields (slice)
{ x: T, ..r }           // row variable (polymorphism)
```

### Expressions

```
x                       // variable
() -> e                 // thunk
(x) -> e                // function
f(x)                    // application
{ a, b, c }             // structure literal
s[.x]                   // field access
s[i]                    // index
val <- { pat -> e }     // pattern match
```

### Patterns

```
x                       // bind variable
{ x, y }                // match structure
{ x, ..rest }           // bind first and rest
{ ..init, x }           // bind init and last
{ .x = a, ..rest }      // bind named field and rest
```

## Macros

Most of Auric's syntax is sugar defined via hygienic macros. This keeps the core
language minimal while allowing expressive surface syntax.

### Design Goals

1. **Pattern-template rewriting**: Macros match syntax patterns and produce
   expansions
2. **Hygienic**: Macro-introduced bindings don't capture user variables
3. **Unified with types**: Macro constraints use the same refinement syntax as
   types
4. **Non-Lisp**: No S-expressions, uses Auric's native syntax

### Syntax

Macros are defined with pattern-template rules using `->`:

```
macro let =
    `let x = e; body` -> `((x) -> body)(e)`

macro if =
    `if c then t else f` -> `c <- { True -> t, False -> f }`

macro or =
    `a or b` -> `a <- { True -> True, False -> b }`
```

Backticks `` ` `` delimit syntax fragments. Names in patterns become pattern
variables, substituted in the template.

### With Type Constraints

Macro parameters can have type constraints using the same syntax as function
types:

```
macro let : (x: Name, e: Expr, body: Expr) -> Expr =
    `let x = e; body` -> `((x) -> body)(e)`

macro for : (x: Name, iter: Expr, body: Expr) -> Expr =
    `for x in iter { body }` -> `iter <- fold { (x, acc) -> body }`
```

Syntax types:

- `Expr` — any expression
- `Name` — identifier
- `Pattern` — destructuring pattern
- `Type` — type expression

### Refinements on Syntax

Since refinement types are unified, macros can use predicates:

```
macro assert : (cond: Expr { boolean? }) -> Expr =
    `assert cond` -> `cond <- { True -> (), False -> panic() }`

macro let : (x: Name { fresh? }, e: Expr, body: Expr) -> Expr =
    `let x = e; body` -> `((x) -> body)(e)`
```

### Multiple Rules

Macros can have multiple patterns (tried in order):

```
macro cond =
    `cond { else -> e }` -> `e`,
    `cond { c -> e, ..rest }` -> `c <- {
        True -> e,
        False -> cond { ..rest }
    }`
```

### Recursive Macros

Macros can be recursive:

```
macro list =
    `list()` -> `{ }`,
    `list(x)` -> `{ x }`,
    `list(x, ..rest)` -> `{ x, ..list(..rest) }`
```

### Hygiene

Introduced bindings are automatically renamed to avoid capture:

```
macro or =
    `a or b` -> `let tmp = a; tmp <- { True -> tmp, False -> b }`

// Expansion of: x or y
// Becomes: let tmp#123 = x; tmp#123 <- { True -> tmp#123, False -> y }
// User's 'tmp' variable (if any) is not affected
```

### Core vs Sugar

The core language is minimal:

```
// Core primitives (not macros)
x                       // variable
() -> e                 // thunk
(x) -> e                // function
f(x)                    // application
{ ... }                 // structure
s[.x]                   // index
e <- { ... }            // match
```

Everything else can be a macro:

```
// Defined as macros
let x = e; body         // let binding
if c then t else f      // conditional
data T { ... }          // inductive type
codata T { ... }        // coinductive type
for x in e { ... }      // iteration
a + b                   // operators (maybe)
```

### References

The macro system draws from:

- [D-Expressions: Lisp Power, Dylan Style](https://people.csail.mit.edu/jrb/Projects/dexprs.pdf)
  (Bachrach & Playford)
- [Sweeten Your JavaScript](https://users.soe.ucsc.edu/~cormac/papers/dls14a.pdf)
  (Disney et al.)
- [Beyond Notations](https://pp.ipd.kit.edu/uploads/publikationen/ullrich20beyond.pdf)
  (Ullrich & de Moura)

## Algebraic Effects

Auric uses **algebraic effects** to handle allocation, mutation, and IO. Effects
make side effects explicit in types while keeping call sites clean — no
threading of allocators or context through every function.

### Design Goals

1. **Effects in types**: Function signatures declare what effects they perform
2. **Handlers scope effects**: `->` extends context with effect handlers
3. **No implicit context**: No Odin-style threading, no labeled argument piping
4. **Totality preserved**: Effects don't affect termination guarantees

### Effect Declarations

Effects declare operations that can be performed:

```
// Allocation effect — parameterized by region R
effect Alloc(R) {
    alloc <- (T) -> &T
}

// Mutation effect
effect Mut(R) {
    read <- (&T) -> T
    write <- (&T, T) -> ()
}

// IO effect
effect IO {
    print <- (String) -> ()
    read_line <- () -> String
}
```

The `<-` indicates these are elimination forms — operations we invoke.

### Function Types with Effects

Effects appear after `/` in function types:

```
// Pure function — no effects
add : (Int, Int) -> Int

// Allocates in region R
make_node : (Int) -> &Node / Alloc(R)

// Allocates and mutates
build_list : (Int) -> &List(Int) / Alloc(R), Mut(R)

// Multiple effects
main : () -> () / IO
```

No effects = pure function. The compiler enforces this.

### Using Effect Operations

Inside an effectful function, call operations directly:

```
make_node : (Int) -> &Node / Alloc(R) =
    (v) -> alloc({ value = v, children = {} })

increment : (&Int) -> () / Mut(R) =
    (ref) -> write(ref, read(ref) + 1)
```

No allocator parameter — `alloc` is an effect operation handled elsewhere.

### Handlers

Handlers provide implementations for effects. The `->` operator extends context
with a handler:

```
// arena handles Alloc(R) and Mut(R) effects
arena -> {
    let a = make_node(1)    // alloc handled by arena
    let b = make_node(2)    // alloc handled by arena
    { a, b }
}
// Result: pure value, effects discharged
```

### Handler Scoping

Handlers scope effects — inner handlers shadow outer:

```
outer_arena -> {
    let a = make_node(1)        // uses outer_arena

    inner_arena -> {
        let b = make_node(2)    // uses inner_arena
        let c = make_node(3)    // uses inner_arena
    }

    let d = make_node(4)        // back to outer_arena
}
```

### Mutation Within Regions

Mutation is allowed within a handler's scope. From outside, the function is
pure:

```
// Externally pure, internally mutable (like Flix regions)
sort : ({ T..n }) -> { T..n } =
    (list) -> arena -> {
        let arr = alloc(to_array(list))
        sort_inplace(arr)           // mutates arr
        to_list(arr)
    }
    // arena freed, result is pure value
```

### Effect Polymorphism

Functions can be polymorphic over effects:

```
// map preserves whatever effects f has
map : ((T) -> U / E, { T..n }) -> { U..n } / E =
    (f, arr) -> arr <- fold {
        {} -> {},
        { x, ..xs } -> (acc) -> { f(x), ..acc }
    }

// If f is pure, map is pure
// If f has IO, map has IO
```

### Totality and Effects

Effects are orthogonal to termination. Totality comes from structural recursion:

```
// Total: fold over structure (regardless of effects)
sum : ({ Int..n }) -> Int / IO =
    (arr) -> arr <- fold {
        {} -> 0,
        { x, ..xs } -> (acc) -> {
            print("Adding " ++ show(x))
            x + acc
        }
    }
```

**Not allowed:** General recursion, even with effects.

```
// REJECTED: not structural recursion
fib_bad : (Int) -> Int =
    (n) -> n <- {
        0 -> 0,
        1 -> 1,
        _ -> fib_bad(n - 1) + fib_bad(n - 2)  // not structural!
    }

// OK: expressed as fold
fib : (Nat) -> Nat =
    (n) -> (n <- fold {
        Zero -> { 0, 1 },
        Succ -> (acc) -> { acc.1, acc.0 + acc.1 }
    }).0
```

### Memoization Example

```
// Cache effect for memoization
effect Cache {
    get <- (Int) -> Maybe(Int)
    put <- (Int, Int) -> ()
}

// Fib using cache (still needs structural recursion on Nat)
fib_memo : (Nat) -> Nat / Cache =
    (n) -> (n <- fold {
        Zero -> { 0, 1 },
        Succ -> (acc) -> {
            put(acc.0, acc.1)
            { acc.1, acc.0 + acc.1 }
        }
    }).0

// Handler implements Cache with mutable map
memo -> {
    fib_memo(nat(50))
}
```

### Generational References

For cyclic data structures (graphs, etc.), references use generational checks at
runtime:

```
Node = {
    value: Int,
    neighbors: { &Node.. }      // may form cycles
}

// Safe dereference (returns Maybe)
n.neighbors[0]?.value

// Unchecked (unsafe)
n.neighbors[0]!.value
```

Generational checks (~11% overhead) catch use-after-free when static analysis
can't prove safety.

### Comparison with Other Approaches

| Aspect          | Rust           | Koka         | Flix          | Auric                 |
| --------------- | -------------- | ------------ | ------------- | --------------------- |
| Effect tracking | Lifetimes      | Effect types | Effect types  | Effect types          |
| Mutation        | Borrow checker | Effect       | Region-scoped | Effect + region       |
| Handler syntax  | N/A            | `with`       | `region`      | `->`                  |
| Totality        | No             | Optional     | No            | Required (Charity)    |
| Allocation      | Manual         | Perceus RC   | GC            | Effect + generational |

### References

Effects system draws from:

- [Koka Language](https://koka-lang.github.io/koka/doc/book.html) — algebraic
  effects with Perceus
- [Flix Regions](https://doc.flix.dev/regions.html) — scoped mutation in pure
  functions
- [Handlers of Algebraic Effects](https://www.eff-lang.org/) — Eff language
- [Vale's Generational References](https://verdagon.dev/blog/generational-references)
- [Frank Language](https://arxiv.org/abs/1611.09259) — effects with handlers

## Type System Summary

The type system unifies several concepts under a minimal set of primitives:

### Core Grammar

```
Type ::=
    | Base                          // Int, Bool, ...
    | { row }                       // structure (record/tuple/array)
    | A | B                         // union
    | A & B                         // intersection (refinement)
    | (A) -> B                      // pure function
    | (A) -> B / Effects            // effectful function
    | &T                            // reference

Row ::=
    | ε                             // empty
    | T, Row                        // positional field
    | x: T, Row                     // named field
    | T..n                          // repeated (n fields of T)
    | T..                           // repeated (existential)
    | ..r                           // row variable

Effects ::=
    | Effect                        // single effect
    | Effect, Effects               // multiple effects

Effect ::=
    | Name                          // IO, Cache, ...
    | Name(params)                  // Alloc(R), Mut(R), ...

Predicate ::=
    | { P }                         // predicate set
```

### Unification Principles

1. **One structure primitive**: `{ }` covers records, tuples, arrays, slices
2. **Types as sets**: union `|`, intersection `&` (includes refinement)
3. **Indices are values**: `n` in `{ T..n }` is a value, inferred
4. **Effects explicit**: `/` separates return type from effects
5. **Totality required**: only structural recursion (folds/unfolds)

### How Features Compose

```
// Structure + size
{ Int..n }                          // array of n ints

// Structure + refinement (intersection)
{ Int..n } & { sorted }             // sorted array

// Structure + reference
&{ Int..n }                         // reference to array

// Union + refinement
(Int | String) & { len > 0 }        // non-empty int or string

// Function + dependent index (pure)
concat : { T..n } -> { T..m } -> { T..n + m }

// Function + effects
make_node : (Int) -> &Node / Alloc(R)

// Function + effects + refinement
make_positive : (Int) -> &Int & { > 0 } / Alloc(R)

// Effect polymorphism
map : ((T) -> U / E, { T..n }) -> { U..n } / E
```

### Mental Model

```
┌─────────────────────────────────────────────────────────┐
│                      Type                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │                   Shape                          │   │
│  │   { }  |  A | B  |  (A) -> B  |  &T             │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Refinement (via intersection)            │   │
│  │   T & { predicate }                             │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │               Effects (on functions)             │   │
│  │   (A) -> B / Alloc(R), Mut(R), IO               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

Most code uses shapes + effects. Refinements add value constraints. Handlers
scope effects with `->`. Totality comes from structural recursion
(folds/unfolds).
