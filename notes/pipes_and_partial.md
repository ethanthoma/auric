# Pipes and Partial Application

## Design Philosophy

Auric uses **explicit partial application** without auto-currying. This provides:
- Clear error messages when arguments are missing
- Explicit intent when creating partial functions
- Good type inference
- No confusion between values and functions

## Placeholder Syntax

Inspired by Zig's `_name` convention for multiple discards.

### Rules

- `_` - Single anonymous placeholder
- `_name` - Named placeholder (for multiple holes, self-documenting)
- Names are for clarity only - filling is **positional left-to-right**

### Grammar

```ebnf
Placeholder ::= "_" Ident?
```

## Partial Application

Function calls with placeholders create new functions waiting for those arguments.

### Single Placeholder

```rs
const add = (x, y) -> x + y

const add1 = add(1, _)              // Int -> Int
const add_to_5 = add(_, 5)          // Int -> Int

add1(10)                            // 11
```

### Multiple Placeholders

```rs
const make_point = point(_x, _y, 0)       // (Int, Int) -> Point
make_point(10, 20)                        // point(10, 20, 0)

const insert = db_insert(_table, _data, timestamp: now())
insert("users", user_record)              // db_insert("users", user_record, ...)
```

**Filling order:** Arguments fill placeholders left-to-right by position, regardless of names.

```rs
const f = compute(_b, 5, _a)
f(x, y)
// First placeholder _b gets x
// Second placeholder _a gets y
// → compute(x, 5, y)
```

### Error Messages

```rs
// Missing argument - immediate error
const bad = add(1)
// ERROR: add expects 2 arguments, got 1
//        Use _ for partial application: add(1, _)

// Wrong type
const bad = add("hello", _)
// ERROR: Expected Int, got String in argument 1 of add
```

## Pipe Operator `|>`

The pipe operator enables data-flow style programming without requiring currying.

### Basic Rule

`left |> right` where `right` is a function call:
- If `right` contains placeholders, they receive values from `left`
- Placeholders filled **left-to-right** positionally
- If no placeholder, value goes to first argument (default)

### Single Value Pipes

```rs
// With explicit placeholder
data |> map(_, transform)              // map(data, transform)
data |> fold(0, add, _)                // fold(0, add, data)

// Default first argument (no placeholder needed)
data |> map(transform)                 // map(data, transform)
data |> filter(is_valid)               // filter(data, is_valid)
```

### Multiple Value Pipes

When piping tuples or multiple values, use named placeholders:

```rs
(x, y) |> func(_a, _b, z)
// _a gets x, _b gets y (left-to-right)
// → func(x, y, z)

(width, height) |> rectangle(_w, _h, "blue")
// → rectangle(width, height, "blue")

(point, color) |> draw(_p, canvas, _c)
// → draw(point, canvas, color)
```

### Chaining

```rs
data
  |> map(transform)
  |> filter(is_valid)
  |> fold(0, sum, _)
  |> format_result
```

### Complex Cases with Lambdas

For complex transformations, use lambda syntax:

```rs
(x, y) |> (a, b) -> {
  const sum = a + b
  const prod = a * b
  .{ sum, prod }
}

result |> r -> match r {
  Ok(v) -> v
  Err(e) -> default
}
```

## Relationship Between Features

The key insight: **In pipes, placeholders work through partial application**

```rs
data |> map(_, transform)
```

Is actually:
1. `map(_, transform)` creates a partial function of type `List(a) -> List(b)`
2. Pipe calls that function with `data`

So `_` always means "partial application" - pipes simply call the resulting function!

### Equivalences

```rs
// These are equivalent:
data |> map(transform)
data |> map(_, transform)
map(_, transform)(data)

// These are equivalent:
(x, y) |> func(_a, _b, z)
func(_a, _b, z)(x, y)
func(x, y, z)
```

## Examples

### Partial Application Standalone

```rs
// Create reusable partial functions
const get_user_by_id = db_query("users", where: _id)
const save_user = db_insert("users", _data, timestamp: now())

// Use them
const user = get_user_by_id(42)
save_user(updated_user)
```

### Pipes for Data Flow

```rs
// Single values
load_data("input.json")
  |> parse_json
  |> validate_schema
  |> transform(_, rules)
  |> save_to("output.json")

// Multiple values
(width, height)
  |> rectangle(_w, _h, fill: "blue")
  |> add_border(_, 2, "black")
  |> render(_, canvas)
```

### Mixed Usage

```rs
// Define with partial application
const draw_rect = rectangle(_w, _h, fill: "blue")

// Use in pipe
(10, 20) |> draw_rect |> render(_, canvas)
```

## Implementation Notes

### Parser

- Recognize `_` and `_identifier` as placeholder tokens
- In function calls, collect placeholders and their positions
- Generate partial application AST node when placeholders present

### Type Checker

- Function call with N placeholders has type `(T1, T2, ..., TN) -> ReturnType`
- Placeholders filled positionally, not by name
- Names only for error messages and documentation

### Evaluator

- Partial application creates closure capturing filled arguments
- Pipe operator checks if RHS is partial application, calls it with LHS
- Default behavior: insert LHS as first argument if no placeholders
