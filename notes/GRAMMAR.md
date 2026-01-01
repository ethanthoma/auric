# Auric Language Grammar

## Core Philosophy

Auric uses a **unified record system** with **dependent types** as its foundation:
- Records are the ONE composite type (tuples and vectors are syntactic sugar)
- Functions are **lazy pattern matches** on their parameters
- Type constructors use `<-`, pattern destructors use `->`
- Everything builds on simple, composable primitives

## Type Hierarchy: None, One, Many

Auric has three fundamental categories of types:

### **None** (Unit)
```auric
()         // Unit type
.{}        // Empty record (same as unit)
```

### **One** (Primitive Atomic Values)
```auric
// Unsigned integers
u8, u16, u32, u64

// Signed integers
i8, i16, i32, i64

// Floating point (IEEE 754)
f32, f64

// Character (ASCII only, alias for u8)
char       // Equivalent to u8

// Defaults: integer literals → i64, float literals → f64
```

**Future:** Fixed-point types with `i#_#` / `u#_#` syntax (e.g., `i8_8`, `u20_12`)

### **Many** (Records - The ONE Composite Type)
```auric
.{ field1: Type1, field2: Type2, ... }

// All other composites are sugar:
.{ x, y }              // Tuple → .{ _0: x, _1: y }
Vec[t, n]              // Vector → dependent record with n fields
```

## Symbol Semantics

| Symbol | Meaning | Context |
|--------|---------|---------|
| `<-` | Construction/Production | Type definitions (ADT constructors) |
| `->` | Destruction/Mapping | Types (function arrows), Pattern cases |
| `=>` | Pattern Match | Connects scrutinee to match body |
| `:` | Type Annotation | Explicit type in declaration |
| `:=` | Inferred Declaration | Declare new variable, infer type |
| `=` | Shadowing/Definition | Shadow existing var (same type) or define body |
| `.{ }` | Record Literal | Creates record/tuple/vector |
| `.field` | Field Access | Accesses record field |

## Binding Forms: Declaration vs Shadowing

Auric distinguishes between **declaring** a new variable and **shadowing** an existing one:

### Declaration (First Binding)

Use `:=` or `: Type =` to declare a new variable:

```auric
x := value          // infer type
x: Type = value     // explicit type
```

### Shadowing (Rebinding)

Use `=` alone to shadow an existing variable (must have same type):

```auric
x = new_value       // must match original type
```

**Example:**
```auric
let x := 5          // declare x: Int
let x = x + 1       // shadow with same type (OK)
let x = x * 2       // shadow again (OK)
let x = "hello"     // ERROR: was Int, can't shadow with String
```

**Key rule:** Since shadowing requires the same type, no type annotation is needed - just `=` is sufficient.

### Pattern Bindings (Irrefutable Only)

Pattern bindings with `let` use `=` and only allow **irrefutable patterns** (patterns that always succeed):

**Valid (irrefutable):**
```auric
let x = value               // variable binding
let (x, y) = point          // tuple destructuring
let {x, y} = point          // record destructuring (all fields)
let _ = value               // wildcard
```

**Invalid (refutable):**
```auric
let Some(x) = opt           // ERROR: could be None
let Circle{radius} = shape  // ERROR: could be Rectangle
let Zero = n                // ERROR: could be Succ
```

**For refutable patterns, use pattern matching:**
```auric
let x = opt => {
    Some(value) -> value;
    None -> default_value
}
```

## Top-Level Definitions

### Constants (Explicit Type)

```auric
const name: type = value
```

**Examples:**
```auric
const answer: Nat = succ(succ(zero))
const point: .{ x: Nat, y: Nat } = .{ x = zero, y = succ(zero) }
```

### Constants (Inferred Type)

```auric
const name := value
```

**Examples:**
```auric
const answer := succ(succ(zero))           // infer Nat
const point := .{ x = zero, y = zero }     // infer record type
```

### Functions (Explicit Type)

```auric
const name: ParamTypes -> RetType = (params) => {
    pattern -> expr;
    pattern -> expr;
    ...
}
```

**Single parameter:**
```auric
const double: Int -> Int = (x) => {
    _ -> x + x
}
```

**Multiple parameters:**
```auric
const add: (Int, Int) -> Int = (x, y) => {
    _, _ -> x + y
}
```

**Pattern matching:**
```auric
const isZero: Nat -> Bool = (n) => {
    zero -> true;
    succ(_) -> false
}
```

**Complex pattern matching:**
```auric
const area: (t, Shape(t)) -> t = (t, shape) => {
    _, Circle{radius} -> 3.14*radius^2;
    _, Rectangle{width, height} -> width*height
}
```

### Functions (Inferred Return Type)

```auric
const name: ParamTypes -> _ = (params) => {
    body
}
```

**Example:**
```auric
const add: (Int, Int) -> _ = (x, y) => {
    _, _ -> x + y  // infer -> Int
}
```

### Functions (Fully Inferred)

```auric
const name := (params: types) {
    body
}
```

**Example:**
```auric
const double := (x: Int) {
    x + x  // infer return type
}
```

### Syntactic Sugar: Simple Functions

When there's no pattern matching, the `_ ->` can be omitted via macro:

```auric
const double: Int -> Int = (x) => {
    x + x  // sugar for: _ -> x + x
}
```

### Type Definitions

```auric
type Name(TypeParams) = {
    Constructor1 <- { field1: type1, field2: type2 };
    Constructor2 <- { field3: type3 }
}
```

**Examples:**

Simple ADT:
```auric
type Bool = {
    True <- {};
    False <- {}
}
```

Recursive type:
```auric
type Nat = {
    Zero <- {};
    Succ <- { pred: Nat }
}
```

Parameterized type:
```auric
type Option(t) = {
    Some <- { value: t };
    None <- {}
}
```

Generic shape type:
```auric
type Shape(t) = {
    Circle <- { radius: t };
    Rectangle <- { width: t, height: t };
    Triangle <- { base: t, height: t }
}
```

## Pattern Matching

### Irrefutable vs Refutable Patterns

**Irrefutable patterns** always match (safe for `let` bindings):
- Variables: `x`, `_`
- Tuples: `(x, y, z)`
- Records: `{x, y}` (all fields present)

**Refutable patterns** might fail (require `=>` pattern matching):
- ADT constructors: `Some(x)`, `None`, `Circle{radius}`
- Specific values: `Zero`, `Succ(n)`
- Any pattern that doesn't cover all cases

**Rule:** Use `let ... =` for irrefutable patterns, `... => { }` for refutable ones.

### Eager Pattern Matching (on values)

```auric
value => {
    pattern1 -> expr1;
    pattern2 -> expr2;
    ...
}
```

**Example:**
```auric
const result = shape => {
    Circle{radius} -> 3.14*radius^2;
    Rectangle{width, height} -> width*height
}
```

### In Let Bindings

```auric
let name = value => {
    pattern1 -> expr1;
    pattern2 -> expr2
}
```

**Example:**
```auric
const compute = (offset: Option(Point)) => {
    _ -> {
        let p = offset => {
            Some(point) -> point;
            None -> .{ x = zero, y = zero }
        };
        return p.x
    }
}
```

### Pattern Syntax

**Wildcard:**
```auric
_ -> expr  // matches anything
```

**Variable binding:**
```auric
x -> expr  // binds value to x
```

**Constructor patterns:**
```auric
Zero -> expr
Succ(n) -> expr
Some(value) -> expr
None -> expr
```

**Record destructuring:**
```auric
Circle{radius} -> expr
Rectangle{width, height} -> expr
Point{x, y} -> expr
```

**Multiple patterns (tuple matching):**
```auric
const f: (Int, Bool) -> Int = (x, b) => {
    _, True -> x;
    _, False -> 0
}
```

## Records, Tuples, and Vectors

### Record Types

**Named fields:**
```auric
.{ x: Int, y: Int }
```

**Unlabeled fields (tuple):**
```auric
.{ Int, Int }  // equivalent to .{ _0: Int, _1: Int }
```

### Record Values

**Named fields:**
```auric
.{ x = 5, y = 10 }
```

**Unlabeled fields (tuple):**
```auric
.{ 5, 10 }  // equivalent to .{ _0 = 5, _1 = 10 }
```

### Field Access

**Named fields:**
```auric
const point = .{ x = 5, y = 10 }
const x_val = point.x
```

**Indexed fields:**
```auric
const tuple = .{ 5, 10, 15 }
const first = tuple._0
const second = tuple._1
```

### Vectors (Dependent Records)

Vectors are records with compile-time length tracking:

```auric
const empty: Vec[Nat, zero] = .{ }
const vec1: Vec[Nat, succ(zero)] = .{ zero }
const vec2: Vec[Nat, succ(succ(zero))] = .{ zero, succ(zero) }
```

**Field access (compile-time):**
```auric
const first = vec2._0
const second = vec2._1
```

## Literals

### Primitive Literals

**Integer literals (default to i64):**
```auric
42          // i64 (default)
0xFF        // i64 hexadecimal
0b1010      // i64 binary
0o777       // i64 octal

// With type suffixes
42u8        // u8
255u32      // u32
-100i32     // i32
1000u64     // u64
```

**Float literals (default to f64):**
```auric
3.14        // f64 (default)
2.5e10      // f64
1.0e-5      // f64

// With type suffixes
3.14f32     // f32
2.5f64      // f64 (explicit)
```

**Character literals (ASCII, expands to u8):**
```auric
'a'         // → 97u8
'Z'         // → 90u8
'\n'        // → 10u8 (newline)
'\t'        // → 9u8 (tab)
```

**String literals (expands to Vec[u8, n]):**
```auric
"hello"     // → Vec[u8, 5] = .{ 'h', 'e', 'l', 'l', 'o' }
```

## Macros

### Array Indexing

```auric
vec[0]  // expands to vec._0 (compile-time)
vec[1]  // expands to vec._1
```

**Note:** Indices must be compile-time numeric literals.

### Character Literal

```auric
'a'   // macro expands to: 97u8
```

### String Literal

```auric
"hello"  // macro expands to: Vec[u8, 5] = .{ 104u8, 101u8, 108u8, 108u8, 111u8 }
```

## Block Expressions

### Let/Return Blocks

```auric
{
    let x = expr1;
    let y = expr2;
    return expr3
}
```

**Or implicitly return last expression:**
```auric
{
    let x = expr1;
    let y = expr2;
    x + y
}
```

## Comments

```auric
// Single-line comment
```

## Complete Examples

### Example 1: Simple Function

```auric
const increment: Nat -> Nat = (x) => {
    _ -> succ(x)
}
```

### Example 2: Polymorphic Identity

```auric
const identity: (t, T) -> t = (t, x) => {
    _, _ -> x
}

const test := identity(Nat, zero)
```

### Example 3: Pattern Matching on ADT

```auric
type Option(t) = {
    Some <- { value: t };
    None <- {}
}

const unwrapOr: (Option(t), T) -> t = (opt, default) => {
    _, Some{value} -> value;
    _, None -> default
}
```

### Example 4: Shape Area Calculator

```auric
type Shape(t) = {
    Circle <- { radius: t };
    Rectangle <- { width: t, height: t }
}

const area: (t, Shape(t)) -> t = (t, shape) => {
    _, Circle{radius} -> 3.14 * radius^2;
    _, Rectangle{width, height} -> width * height
}
```

### Example 5: Primitive Types

```auric
// Integers (default to i64)
const x := 42              // i64 (default)
const y := -100            // i64
const small: u8 = 255u8    // explicit u8
const big := 1000u64       // explicit u64

// Floats (default to f64)
const pi := 3.14159        // f64 (default)
const tiny: f32 = 1.0e-5f32  // explicit f32

// Characters (ASCII, u8)
const letter: char = 'A'
const newline: char = '\n'

// Strings (Vec[u8, n])
const msg: Vec[u8, 5] = "hello"
const greeting := "world"  // type inferred

// Records with primitives
const point := .{ x = 1.5, y = 2.5 }  // .{ x: f64, y: f64 }
```

### Example 6: Unified Records/Tuples/Vectors

```auric
// Named record
const person := .{ name = zero, age = succ(zero) }
const age = person.age

// Tuple
const point := .{ succ(zero), succ(succ(zero)) }
const x = point._0

// Vector
const vec: Vec[Nat, succ(succ(zero))] = .{ zero, succ(zero) }
const first = vec[0]  // macro expands to vec._0
```

## Design Rationale

### Why None, One, Many?

Auric's type system has three fundamental categories:

**None (Unit):**
- Represents "no value" or "empty"
- Empty record `.{}` or unit `()`
- Used for side effects, void returns

**One (Primitives):**
- Atomic, indivisible values
- Efficient machine types (u8, u32, f64, etc.)
- Cannot be decomposed into smaller parts
- **Defaults:** Integer literals → `i64`, float literals → `f64`
- **Future:** Fixed-point numbers (`i#_#`, `u#_#`) where integers are special case (`i64 = i64_0`)

**Many (Records):**
- The ONE composite type
- All structured data builds on records
- Tuples and vectors are syntactic sugar over records

This creates a clean hierarchy:
- 0 fields → None
- 1 atomic value → One
- N fields → Many (records)

**Everything is built from these three categories.**

### Why `<-` and `->`?

**Beautiful duality:**
- `<-` constructs values (synthesis)
- `->` destructs values (analysis)

```auric
// Construction
type Option(t) = {
    Some <- { value: t }  // build values
}

// Destruction
const unwrap: Option(t) -> t = (opt) => {
    Some{value} -> value  // take apart values
}
```

### Why `=>` for Pattern Matching?

Distinguishes between:
- **Type arrow**: `ParamTypes -> RetType` (function type)
- **Match arrow**: `value => { ... }` (connects scrutinee to cases)
- **Case arrow**: `pattern -> expr` (maps pattern to result)

Each arrow has a clear, distinct role.

### Why Functions are Pattern Matches?

**Lazy pattern matching:**
```auric
const f: t -> U = (x) => { ... }
```

The `(x)` creates a **thunk** (lazy computation) that pattern matches on `x` when applied.

**Eager pattern matching:**
```auric
const result = value => { ... }
```

Immediately evaluates the pattern match.

Both use the same pattern syntax, just lazy vs. eager.

### Why Records are Primitive?

**Unification:**
- Records: `.{ name = value }`
- Tuples: `.{ value1, value2 }` (unlabeled records)
- Vectors: `Vec[T, n]` (dependent records with length tracking)

**Single primitive, zero overhead:**
- Field names resolved at compile time
- No runtime dictionaries or lookups
- Compile-time field access only

## Migration Guide

### From Old Syntax

**Old:**
```auric
const f = (x: Int) -> Int { x }
```

**New:**
```auric
const f: Int -> Int = (x) => { _ -> x }
```

**Key changes:**
1. Type signature before `=`
2. Parameter binding with `= (params) =>`
3. Body is pattern matching cases
4. `->` only for types and pattern cases, not definition
