## Scope (`{}`) Operator

`{}` is the scope delimiting operator that:

- Defines a computational scope with local bindings
- Produces a record value with exported fields
- Serves as the body for context extension via `->` (more in the `into` section)

### Fundamental Rules

#### Field Export (`.field = value`)

Rule: `.fieldname = expr` creates an exported field in the resulting record.

```
{
  .x = 5;
  .y = 10;
}
```

Produces: An anonymous record `{x: 5, y: 10}` of type `{x: Int, y: Int}`

#### Private Bindings (`let`)

Rule: `let` bindings are private to the scope, not exported. More on this in the
`into` section.

```
{
  let helper = 1;
  let another = 2;
  
  .result = helper + another;
}
```

Produces: A record `{result: 3}` of type `{result: Int}`

#### Pure Records

```
{.x = 5, .y = 10} 
```

Shorthand for record literal with no internal computation.

#### Separator Syntax: `;` and Newlines

Rule: Either `;` or newline acts as separator. Trailing separators are optional.

```
// Multiple statements per line
{let x = 1; let y = 2; .result = x + y}

// Newline-separated
{
  let x = 1
  let y = 2
  .result = x + y
}

// Mixed
{
  let x = 1; let y = 2
  .result = x + y
}
```

## Into (`->`) Operator

### Binding Rules

```
// Lazy parameters (exposed, must provide)

(x, y) -> {body}
// Type: (Int, Int) -> {result: Int}

// Private bindings (not exposed)
(x, y, helper = 1, another = x + 1) -> {body}
// Type: (Int, Int) -> {result: Int}
// helper and another are implementation details

// Pure computation (no parameters)
(result = 5 + 5) -> {.value = result}
// Type: {value: Int}
// This is just a let block
```

Rule: Any binding with `= expr` is private and not part of the signature as it
is not a value hole.

We have syntax sugar via `let`:

```
(result = 5 + 5) -> { .value = result }

// Equiv to
() -> { let result = 5 + 5; .value = result }
```

### Composition Pipeline

Each `->` extends the evaluation context for everything to its right.

```
// Chain contexts left-to-right
(x) -> (y = x + 1) -> (z = y * 2) -> {
  .result = z
}

// Equivalent to nested application
(x) -> (
  (y = x + 1) -> (
    (z = y * 2) -> {
      .result = z
    }
  )
)
```

### First-Class Contexts

```
// Define a context
context Helpers {
  x: Int,              // parameter
  y: Int,              // parameter
  doubled = x * 2,     // computed binding
  tripled = x * 3      // computed binding
}

// Apply context to scope
myFunc = Helpers -> {
  .sum = doubled + tripled
}

// Type of myFunc: (x: Int, y: Int) -> {sum: Int}
// Only x, y are parameters; doubled, tripled are private
```

## Function Application

Functions are called using parentheses `()`, not space-separated application:

```
// Correct
add(1, 2)
length(myList)
map(fn, list)

// Not valid (no space-separated application)
add 1 2        // Error
length myList  // Error
```

**Multiple arguments** are comma-separated inside the parentheses:

```
distance(point1, point2)
fold(fn, init, list)
```

**Accessing fields** on return values:

```
add(1, 2).result
length(myList).value
```

**Chaining** uses explicit parentheses:

```
process(transform(filter(list)))

// Or with intermediate bindings
{
  let filtered = filter(list)
  let transformed = transform(filtered)
  .result = process(transformed)
}
```

## Thunks and Laziness

### Core Principle: Explicit Laziness

**Default:** Everything is eager (strict evaluation) **`()` creates/forces
thunks:** Laziness is opt-in and explicit

### Parameters Are Value Holes (Not Lazy)

Parameters are dependency injection points that receive concrete values:

```
// Parameters are holes to be filled
f = (x, y) -> {.result = x + y}

// Application evaluates arguments first, then passes values
result = f(1 + 1, 2 + 2)
// Evaluates: 1+1 → 2, then 2+2 → 4
// Passes: 2 and 4 into f
```

### Thunk Types: `() -> T`

**Creating a thunk:**

```
// Suspend computation
thunk: () -> Int = () -> expensive()
delayedList: () -> List Int = () -> [1, 2, 3]
```

**Forcing a thunk:**

```
// Call with () to evaluate
value = thunk()
list = delayedList()
```

**No memoization:** Thunks evaluate every time they're forced:

```
counter = {
  let count = 0;
  () -> {count = count + 1; .value = count}
}

x = counter()  // 1
y = counter()  // 2 (re-evaluates)
```

### Lazy Fields

Fields can have thunk types:

```
type Config = {
  name: String;                    // eager field
  lazyDefaults: () -> Defaults;    // lazy field
}

config = {
  .name = "MyConfig";
  .lazyDefaults = () -> loadDefaults();
}

// Access
name = config.name              // immediate
defaults = config.lazyDefaults() // forces computation
```

### Compositional Patterns

**Short-circuit evaluation:**

```
and = (a: Bool, b: () -> Bool) -> {
  .result = if a then b() else false
}

// Second arg not evaluated if first is false
result = and(false, () -> expensive())
```

**Conditional execution:**

```
ifThenElse = (cond: Bool, then: () -> T, else: () -> T) -> {
  .result = if cond then then() else else()
}
```

**Lazy data structures:**

```
type Stream = (T: Type) -> {
  head: T;
  tail: () -> Stream T;  // coinductive via laziness
}

naturals = (n) -> {
  .head = n;
  .tail = () -> naturals(n + 1);
}
```

### With Sized Records

```
// Array of lazy computations
lazyArray: (() -> Int)[10] = array(10, (i) -> () -> compute(i))

// Force specific element
value = lazyArray[5]()
```

## Pattern Matching (`match`)

Pattern matching provides multi-path scopes for eliminating sum types
(variants). It uses right-handed syntax consistent with `->`.

### Right-Handed Matching

```
// Explicit parameter
length = (list) -> list -> match {
  Nil => {.result = 0}
  Cons {head, tail} => {.result = 1 + length(tail).result}
}

// Inline matching
result = myList -> match {
  Nil => {.result = 0}
  Cons {head, tail} => {.result = head}
}

// Implicit parameter (sugar)
length = match {
  Nil => {.result = 0}
  Cons {head, tail} => {.result = 1 + length(tail).result}
}
// Desugars to: (list) -> list -> match { ... }
```

**Rule:** Values flow left-to-right via `->`, including into pattern matches.

### Pattern Types

**Constructor patterns:**

```
Nil => ...
Cons {head, tail} => ...
```

**Record patterns (destructuring):**

```
{x, y} => ...
{name, age} => ...
```

**Nested patterns:**

```
Cons {head, tail: Nil} => ...
Branch {left: Leaf {value}, right} => ...
```

**Wildcard:**

```
_ => ...
```

### Pattern Matching in Parameters

Records can be destructured in function parameters:

```
// Destructure record parameters
distance = ({x: x1, y: y1}, {x: x2, y: y2}) -> {
  let dx = x2 - x1
  let dy = y2 - y1
  .result = sqrt(dx*dx + dy*dy)
}

// Shorthand when names match
addPoints = ({x, y}, {x: x2, y: y2}) -> {
  .x = x + x2
  .y = y + y2
}
```

### Exhaustiveness

Pattern matches must be exhaustive for totality - all cases must be handled.

## Type Definitions

### Sum Types (Variants)

Sum types use `<-` to define constructors:

```
type List = (T: Type) -> {
  Nil <- {};
  Cons <- {head: T, tail: List T};
}

type Result = (T: Type, E: Type) -> {
  Ok <- {value: T};
  Err <- {error: E};
}

type Tree = (T: Type) -> {
  Leaf <- {value: T};
  Branch <- {left: Tree T, right: Tree T};
}
```

**Nullary constructors** can omit `<- {}`:

```
type Bool = {
  True;
  False;
}
// Desugars to: True <- {}; False <- {};

type Nat = {
  Zero;
  Succ <- {pred: Nat};
}
```

### Product Types (Records)

Product types use `:` to define fields:

```
type Point = (T: Type) -> {
  x: T;
  y: T;
}

type Pair = (A: Type, B: Type) -> {
  first: A;
  second: B;
}

type Triple = (A: Type, B: Type, C: Type) -> {
  first: A;
  second: B;
  third: C;
}
```

### Generic Types

Type parameters use function-like syntax with `->`:

```
// Type constructor as a function
List : Type -> Type
List = (T: Type) -> {
  Nil;
  Cons <- {head: T, tail: List T};
}

// Multiple parameters
Result : Type -> Type -> Type
Result = (T: Type, E: Type) -> {
  Ok <- {value: T};
  Err <- {error: E};
}

// Application
IntList = List Int
MyResult = Result String Error
```

### Construction and Elimination Duality

**Sum types (variants):**

- **Construction:** Choose one variant → `Cons {.head = 1, .tail = Nil}`
- **Elimination:** Handle all cases → `list -> match { ... }`

**Product types (records):**

- **Construction:** Provide all fields → `{.x = 5, .y = 10}`
- **Elimination:** Select one field → `point.x`

The `<-` in constructors mirrors the elimination via pattern matching:

```
// Construction (choose one)
myList = Cons {.head = 1, .tail = Nil}

// Elimination (handle all)
myList -> match {
  Nil => ...
  Cons {head, tail} => ...
}
```

### Type Inference: Inductive vs Coinductive

The compiler automatically infers whether a type is:

- **Inductive** (finite, recursive) - uses constructors with `<-` and
  self-reference
- **Coinductive** (infinite, corecursive) - uses lazy fields `() -> Self`
- **Simple** - no self-reference

**Inductive types** (constructors + self-reference):

```
type List = (T: Type) -> {
  Nil;
  Cons <- {head: T, tail: List T};
}
// Checked for structural recursion (termination)
```

**Coinductive types** (lazy recursive fields):

```
type Stream = (T: Type) -> {
  head: T;
  tail: () -> Stream T;  // lazy field enables infinite structure
}
// Checked for productivity (corecursion)
```

**Simple types** (no self-reference):

```
type Bool = {True; False;}
type Point = {x: Int; y: Int;}
// No totality checking needed
```

**Error: Eager recursive field**

```
type Broken = {
  field: Broken;  // Error: would require infinite eager evaluation
}
```

**Rules:**

- `<-` + self-reference → inductive
- `() -> Self` in field → coinductive
- `Self` eagerly in field → **error** (infinite structure)
- No self-reference → simple

A type cannot mix constructors (`<-`) and fields (`:`) - it must be either a sum
or a product.

### Examples

```
// Inductive sum type
type Expr = {
  Lit <- {value: Int};
  Var <- {name: String};
  Add <- {left: Expr, right: Expr};
  Lambda <- {param: String, body: Expr};
  App <- {func: Expr, arg: Expr};
}

// Pattern matching
eval = (expr) -> expr -> match {
  Lit {value} => {.result = value}
  Var {name} => {.result = lookupVar(name)}
  Add {left, right} => {
    .result = eval(left).result + eval(right).result
  }
  Lambda {param, body} => {.result = makeClosure(param, body)}
  App {func, arg} => {.result = apply(eval(func), eval(arg))}
}

// Coinductive product type  
type InfiniteTree = (T: Type) -> {
  value: T;
  left: () -> InfiniteTree T;   // lazy recursive fields
  right: () -> InfiniteTree T;
}

// Productive corecursion
fullTree = (x) -> {
  .value = x;
  .left = () -> fullTree(x);
  .right = () -> fullTree(x);
}

// Consuming coinductive structures
type Stream = (T: Type) -> {
  head: T;
  tail: () -> Stream T;
}

naturals = (n) -> {
  .head = n;
  .tail = () -> naturals(n + 1);
}

// Operations on streams
map = (f: T -> U, stream: Stream T) -> {
  .head = f(stream.head);
  .tail = () -> map(f, stream.tail());  // suspend recursive call
}

take = (n: Nat, stream: Stream T) -> match n {
  Zero -> Nil
  Succ m -> Cons {
    .head = stream.head;
    .tail = take(m, stream.tail());  // force tail when needed
  }
}
```

## Sized Records

All records have an implicit size. Records are the only collective type - arrays
are just sized records with size > 1.

### Size Syntax: `[]`

```
// Single instance (implicit size 1)
point: {x: Int, y: Int}

// Fixed-size array (compile-time known size)
points: {x: Int, y: Int}[10]

// Variable-size slice (runtime size)
slice: {x: Int, y: Int}[]
```

**Key distinction:**

- `T[n]` - fixed size (compile-time known), no overhead, exact size in type
- `T[]` - variable size (runtime), fat pointer (ptr + len), existential size

### Type Definitions with Sizes

```
// Base structure
type Point = {
  x: Float;
  y: Float;
}

// Fixed-size array type
type Points = (n: Nat) -> Point[n]

// Variable-size slice type
type PointSlice = Point[]
```

### Memory Layout

**Fixed-size arrays** (no overhead):

```
particles: Particle[1000]
// Memory: [Particle, Particle, Particle, ...] × 1000
// Size: sizeof(Particle) * 1000
// No header, just contiguous data
```

**Variable-size slices** (fat pointer):

```
slice: Particle[]
// Memory representation:
// {
//   ptr: Pointer Particle;
//   len: Nat;
// }
```

### Structure of Arrays (SoA) Access

Sized records enable both Array of Structures (AoS) and Structure of Arrays
(SoA) views:

```
particles: {x: Float, y: Float, vx: Float, vy: Float}[100]

// AoS access: particle then field
particles[i].x

// SoA access: field then index (all x-coordinates)
particles.x[i]
```

Both access patterns work with the same underlying data.

### Operations

**Fixed-size operations** (preserve size):

```
map: T[n] -> (T -> U) -> U[n]
zip: T[n] -> U[n] -> (T, U)[n]
reverse: T[n] -> T[n]
```

**Variable-size operations** (return slices):

```
filter: T[] -> (T -> Bool) -> T[]
concat: T[] -> T[] -> T[]
flatten: T[][] -> T[]
```

**Size conversion:**

```
toSlice: T[n] -> T[]                    // always safe
withSize: T[] -> exists n. (T[n], Nat)  // recover size info
```

### Slicing Syntax

```
fullArray: T[100]

slice1: T[] = fullArray[10..20]    // elements 10-19
slice2: T[] = fullArray[..50]      // first 50
slice3: T[] = fullArray[50..]      // from 50 to end

// With refined types (when range is statically known)
slice4: T[10] = fullArray[10..20]  // exactly 10 elements
```

### Pattern Matching on Slices

```
processList = (items: T[]) -> items -> match {
  [] -> {.result = "empty"}              // size 0
  [head, ...tail] -> {                   // size >= 1
    .first = head;
    .rest = tail;  // tail: T[]
  }
}
```

### Safe Indexing

**With Fin (bounded index type):**

```
type Fin = (n: Nat) -> {
  FZ : Fin (Succ n);
  FS <- {pred: Fin n} : Fin (Succ n);
}

// Type-safe indexing (can't be out of bounds)
index: T[n] -> Fin n -> T
```

**With runtime checks:**

```
// Returns option for runtime values
indexMaybe: T[] -> Nat -> Option T

// Or with bounds checking
indexChecked: T[] -> Nat -> Result T String
```

### Complete Example

```
// Define structure
type Particle = {
  x: Float;
  y: Float;
  vx: Float;
  vy: Float;
}

// Fixed-size array (stack allocated, size known)
particles: Particle[1000] = array(1000, (i) -> {
  .x = randomFloat();
  .y = randomFloat();
  .vx = 0.0;
  .vy = 0.0;
})

// Slice (creates view with runtime size)
activeParticles: Particle[] = particles[0..activeCount]

// Filter (unknown size at compile time)
fastParticles: Particle[] = filter(activeParticles, (p) -> 
  sqrt(p.vx * p.vx + p.vy * p.vy) > 10.0
)

// Map preserves size
updated: Particle[1000] = map(particles, (p) -> {
  .x = p.x + p.vx;
  .y = p.y + p.vy;
  .vx = p.vx;
  .vy = p.vy;
})

// SoA access (get all x-coordinates)
xPositions: Float[1000] = particles.x
```

### Type System Rules

**Subtyping:**

```
T[n] <: T[]
// Fixed-size arrays can be used as slices
```

**Existential elimination:**

```
T[] ≡ exists n. T[n]
// Slices are existentially quantified over size
```

**Size arithmetic** (at type level):

```
append: T[n] -> T[m] -> T[n + m]
take: Nat -> T[n] -> T[min(k, n)]
drop: Nat -> T[n] -> T[max(0, n - k)]
```

### Sized Records vs Inductive/Coinductive Types

Sized records complement inductive and coinductive types - they serve different
purposes:

**Sized records** (`T[n]`) - for contiguous, indexed data:

```
particles: Particle[1000]  // contiguous memory, random access
xCoords: Float[1000] = particles.x  // SoA access
```

**Inductive types** (recursive with constructors) - for structural recursion:

```
type List = (T: Type) -> {
  Nil;
  Cons <- {head: T, tail: List T};
}
```

**Coinductive types** (lazy recursive fields) - for infinite/corecursive
structures:

```
type Stream = (T: Type) -> {
  head: T;
  tail: () -> Stream T;
}
```

**When to use each:**

- Use `T[n]`: contiguous memory, indexing, SoA access, performance-critical
- Use inductive types: structural recursion, symbolic computation, finite data
- Use coinductive types: infinite streams, lazy evaluation, corecursive
  definitions

**Conversion:**

```
toArray: List T -> exists n. T[n]
fromArray: T[n] -> List T
toList: Stream T -> Nat -> List T  // take n elements
```
