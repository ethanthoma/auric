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
- **Coinductive** (infinite, corecursive) - uses fields with `:` and
  self-reference
- **Simple** - no self-reference

**Inductive types** (automatically detected from `<-` + self-reference):

```
type Nat = {
  Zero;
  Succ <- {pred: Nat};
}
// Checked for structural recursion (termination)
```

**Coinductive types** (automatically detected from `:` + self-reference):

```
type Stream = (T: Type) -> {
  head: T;
  tail: Stream T;
}
// Checked for productivity (corecursion)
```

**Simple types** (no self-reference):

```
type Bool = {True; False;}
type Point = {x: Int; y: Int;}
// No totality checking needed
```

**Rule:** A type cannot mix constructors (`<-`) and fields (`:`) - it must be
either a sum or a product.

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
  left: InfiniteTree T;
  right: InfiniteTree T;
}

// Productive corecursion
fullTree = (x) -> {
  .value = x;
  .left = fullTree(x);
  .right = fullTree(x);
}
```
