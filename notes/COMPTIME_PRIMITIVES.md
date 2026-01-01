# Compile-Time Primitives (@ Builtins)

⚠️ **Status:** Being redesigned! See `UNIFIED_COMPTIME_DESIGN.md` for new
philosophy.

**Old design:** Special `@` primitives with unique syntax **New design:**
Regular functions, unified runtime/comptime syntax, Zig-inspired

This document describes the **old implementation**. The new design is being
documented in `UNIFIED_COMPTIME_DESIGN.md`.

## AST Construction (Build Code)

### `@var(name: String) -> Expr`

Create variable reference.

```auric
@var("cons")  // → Var("cons")
```

### `@app(fn: Expr, arg: Expr) -> Expr`

Function application.

```auric
@app(@var("cons"), x)  // → App(Var("cons"), x)
```

### `@lam(param: String, body: Expr) -> Expr`

Lambda abstraction.

```auric
@lam("x", @app(@var("succ"), @var("x")))  // → (x) => succ(x)
```

### `@field_access(record: Expr, field: String) -> Expr`

Record field access.

```auric
@field_access(vec, "_0")  // → vec._0
```

### `@seq(exprs: List[Expr]) -> Expr`

Sequence of expressions.

```auric
@seq([expr1, expr2, expr3])  // → { expr1; expr2; expr3 }
```

## AST Inspection (Examine Code)

### `@is_record(expr: Expr) -> Bool`

Check if expression is a Record literal.

```auric
@is_record(.{ _0 = x })  // → @true
@is_record(my_var)       // → @false
```

### `@record_fields(record: Record) -> List[(String, Expr)]`

Extract fields from Record as list of (name, value) pairs.

```auric
@record_fields(.{ _0 = a, _1 = b })  // → [("_0", a), ("_1", b)]
```

## Data Manipulation

### `@concat(strings: String...) -> String`

Concatenate strings.

```auric
@concat("_", "0")  // → "_0"
```

### `@to_string(value: Any) -> String`

Convert value to string representation.

```auric
@to_string(42)  // → "42"
```

### `@fold_right(list: List[A], init: B, fn: A -> B -> B) -> B`

Right fold over list.

```auric
@fold_right([1,2,3], nil, (x, acc) => cons(x, acc))
```

### `@map(list: List[A], fn: A -> B) -> List[B]`

Map function over list.

```auric
@map(fields, (pair) => process(pair))
```

## Example Usage

### Define `@for` macro:

```auric
macro @for = (iterable, body_fn) => {
  if @is_record(iterable) {
    let fields = @record_fields(iterable);
    let iterations = @map(fields, (pair) => {
      let field_val = pair._1;
      @app(body_fn, field_val)
    });
    @seq(iterations)
  } else {
    // Fallback: keep as macro invocation for later expansion
    @macro_invocation("@for", [iterable, body_fn])
  }
}
```

### Define `index` macro:

```auric
macro index = (vec, i) => {
  @field_access(vec, @concat("_", @to_string(i)))
}
```

### Define `list` macro:

```auric
macro list = (elements) => {
  @fold_right(elements, @var("nil"), (elem, acc) => {
    @app(@app(@var("cons"), elem), acc)
  })
}
```

## Working Examples

### Simple Macro with AST Construction

```auric
// Works perfectly!
macro double_succ = (n) => @app(@succ, @app(@succ, n))

const test := double_succ(@zero)  // → @succ(@succ(@zero))
```

### Known Limitation: Lambda Syntax in Macro Bodies

Currently, lambdas inside macro bodies (e.g., `(x) => expr`) are parsed as
pattern-matching syntax, which causes parse errors. This prevents defining
complex macros like:

```auric
// Doesn't parse yet due to lambda syntax issue
macro @for = (iterable, body_fn) =>
  @seq(@map(@record_fields(iterable), (elem) => @app(body_fn, elem)))
```

**Workaround:** Complex macros like `@for`, `index`, and `list` remain
Python-registered until the parser is updated to handle lambdas in macro bodies.

## Design Principles

1. **Minimal**: Only what's necessary, nothing more
1. **Composable**: Primitives combine to build complex macros
1. **Uniform**: Same `@` prefix as other builtins
1. **Pure**: No side effects, deterministic results
1. **Zig-like**: Look like regular function calls

## Implementation Notes

- These functions operate on AST nodes during macro expansion
- Available only in macro bodies (compile-time context)
- Return AST expressions that get spliced into the code
- Type-safe: will error if given wrong AST node type
