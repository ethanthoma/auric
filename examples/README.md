# Auric Examples

This directory contains example programs demonstrating Auric's features with the new grammar syntax.

## Core Language Examples

### `showcase.au`
**Main showcase of the Auric language**

Comprehensive demonstration of all language features:
- Primitive types (integers, floats, characters)
- Pattern matching with `=>` syntax
- Function definitions with new syntax
- Records and tuples
- Vectors (dependent records)
- Type hierarchy (None/One/Many)

Run: `uv run python -m auric examples/showcase.au`

## Feature-Specific Tests

### `primitives_test.au`
Tests all primitive numeric types:
- Integer literals with different bases (decimal, hex, binary, octal)
- Type suffixes (`42u8`, `3.14f32`, etc.)
- Default types (i64 for integers, f64 for floats)
- Character literals with escape sequences

### `test_macros_simple.au`
Tests user-defined macros:
- Simple macro definitions
- Conditional code generation
- AST substitution

### `test_macros_comprehensive.au`
More advanced macro examples:
- Multiple macro definitions
- Code transformation
- Demonstrating macro capabilities

### `test_comptime.au`
Tests compile-time evaluation (comptime):
- `param()` syntax to evaluate AST at macro expansion time
- Compile-time conditionals
- Zig-style comptime execution in macros

### `test_macro_simple_composition.au`
Tests macro composition:
- Macros calling other macros
- Compile-time macro expansion within macros

See `../MACROS.md` for full macro documentation.

### `test_for_loop.au`
Tests the `for` loop syntax for iterating over lists:
- `for i = ..list { body }` - iterate over list elements
- Works with empty lists, single element, and multiple elements
- Uses `..` syntax to indicate iteration (preserves `..` for range syntax in future)

### `pattern_match_test.au`
Tests pattern matching with the `=>` syntax:
- Simple pattern matching on booleans
- Pattern matching on natural numbers
- Demonstrates eager pattern matching

### `test_new_function_syntax.au`
Tests the new function definition syntax:
- `const name: Type -> Type = (params) => { body }`
- Pattern matching in function bodies
- Recursive functions

### `macro_test.au`
Tests the macro system:
- Array indexing macro: `vec[0]` → `vec._0`
- Compile-time macro expansion
- Zero-overhead abstractions

## Other Tests

### `test_const.au`
Simple constant definition test. Minimal example for testing basic functionality.

### `test_effects_comprehensive.au`
Tests the effect system:
- Print effect
- Random effect
- Sleep effect

### `test_handle.au`
Tests effect handlers:
- Handling Print effects
- Handling Read effects

### `test_imports.au`
Tests the module import system:
- Importing standard library modules (`std/nat`)
- Using imported functions

## Running Examples

All examples can be run with:
```bash
uv run python -m auric examples/<filename>.au
```

## Example Output

When you run an example, you'll see:
1. Parse status and definition count
2. Macro expansion status
3. Type checking results with inferred types
4. Evaluation results with computed values

Example:
```
Running showcase.au...
============================================================
✓ Parsed 34 definitions
✓ Expanded macros
✓ Type checked successfully
  answer : ShapeT(shape=Base(name='i64'))
  pi : ShapeT(shape=Base(name='f64'))
  ...

============================================================
Evaluation:
============================================================
answer = ('int', 42, 'i64')
pi = ('float', 3.14159265359, 'f64')
...

============================================================
✓ Completed successfully
```

## Grammar Reference

All examples follow the grammar specification in `notes/GRAMMAR.md`. Key syntax:

### Declarations
```auric
const name := value              // Inferred type
const name: Type = value         // Explicit type
```

### Functions
```auric
const f: A -> B = (x) => {
    pattern -> expr;
    pattern -> expr;
}
```

### Pattern Matching
```auric
value => {
    pattern -> expr;
    pattern -> expr;
}
```

### Records and Tuples
```auric
.{ field = value }               // Named record
.{ value1, value2 }              // Tuple (unlabeled record)
```

### Vectors
```auric
Vec[Type, length]                // Dependent record with compile-time length
```

## Standard Library

The `std/` directory contains standard library modules:
- `std/nat.au` - Natural number utilities (`is_zero`, `pred`)
- `std/bool.au` - Boolean utilities (`not`)
- `std/list.au` - List utilities (placeholder)

Import with: `import std/nat`
