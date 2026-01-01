# Builtins vs Macros in Auric

Auric distinguishes between **compiler builtins** and **user-definable macros**.

## Compiler Builtins (marked with `@`)

These are fundamental primitives provided by the compiler and **cannot be
redefined** by users:

### Data Constructors

- `@zero`, `@succ` - Natural number constructors
- `@true`, `@false` - Boolean constructors

### Types

- `@Nat` - Natural numbers
- `@Bool` - Booleans
- `@Unit` - Unit type

### Effects

- `@Print` - Output to stdout
- `@Read` - Read from stdin
- `@Sleep` - Pause execution
- `@Random` - Generate random numbers

### Core Constructs

- `@record` - Record types and literals (`.{ }` syntax)
- `@case` - Pattern matching

## Standard Library Macros (no `@`)

These are **user-definable** and can be redefined or not imported:

### Control Flow

- `for` - Loop over collections (compile-time unrolling)
- `if` - Conditional expressions

### Data Structures

- `list` - List literal macro `[x, y, z]`
- `index` - Array indexing `vec[i]`

### User-Defined Types

- `Nat`, `Bool` - Can be defined by users (currently use `@Nat`, `@Bool`)
- `List`, `Vec` - User-definable collection types

## Design Philosophy

**Minimal Builtins + Rich Macros**

- Keep compiler builtins to a minimum (only what's truly primitive)
- Implement language features as macros when possible
- Allow users to extend the language through macros
- Enable different "flavors" of Auric by importing different macro sets

## Examples

### Builtin Usage (cannot redefine)

```auric
const three := @succ(@succ(@succ(@zero)))
const is_true := @true
```

### Macro Usage (can redefine)

```auric
// Use standard library 'for' macro
for i = ..vec { print(i) }

// Or define your own 'for'!
macro my_for = (iterable, body) => { ... }
```

## Future: Import System

Eventually, standard library macros will be importable:

```auric
import std: for, if, list  // Import specific macros
import std: *              // Import all standard macros

// Or don't import to avoid namespace pollution
// and define your own!
```

## Phase 2 Status

✓ `for` loops converted from special form to registered macro

- Parser creates `MacroInvocation("@for", [iterable, lambda])`
- Macro expander handles compile-time unrolling
- Users can (in future) override or not import `for`

**Next Steps:**

- Convert other special forms (`if`) to macros
- Implement import/module system
- Allow user-defined syntax macros
