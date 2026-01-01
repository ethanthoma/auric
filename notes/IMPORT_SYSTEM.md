# Import System in Auric

Auric supports a flexible module system for organizing code and reusing definitions.

## Import Syntax

### Wildcard Import (Import Everything)
```auric
import std/builtins: *
```
Imports all definitions from the module.

### Selective Import
```auric
import std/builtins: is_zero, one, two, pred
```
Imports only the specified names.

### Legacy Import (Deprecated)
```auric
import std/builtins
```
Imports everything (equivalent to wildcard `*`). Use `import module: *` instead for clarity.

## Module Resolution

Modules are resolved relative to the project root:
- `import std/builtins` → loads `std/builtins.au`
- `import my/module` → loads `my/module.au`

The `.au` extension is added automatically if not specified.

## Standard Library Modules

### `std/builtins`
Core utility functions and constants:
- **Functions**: `is_zero`, `pred`, `not`
- **Constants**: `one`, `two`, `three`, `four`, `five`, `six`, `seven`, `eight`, `nine`, `ten`

### `std/nat`
Natural number utilities (from original standard library).

### `std/bool`
Boolean utilities (from original standard library).

## Examples

### Using Wildcard Imports
```auric
import std/builtins: *

const result := is_zero(@zero)  // @true
const num := six                // @succ(@succ(...))
```

### Using Selective Imports
```auric
import std/builtins: one, two, three

const sum := one  // Only imported names available
// const x := six  // ERROR: 'six' not imported
```

### Importing Multiple Modules
```auric
import std/builtins: is_zero, one
import std/nat: *

const check := is_zero(one)
```

## Design Philosophy

The import system supports Auric's "minimal builtins + rich macros" philosophy:

- **Compiler builtins** (marked with `@`) are always available
- **Standard library functions** must be explicitly imported
- Selective imports avoid namespace pollution
- Users can create their own module hierarchies

## Future Enhancements

**Module Exports:**
```auric
// In module file
export is_zero, pred  // Explicit exports
private _internal     // Not exported
```

**Aliased Imports:**
```auric
import std/builtins: is_zero as check_zero
```

**Re-exports:**
```auric
export * from std/nat  // Re-export everything from another module
```

## Implementation Status

✅ Wildcard imports (`import module: *`)
✅ Selective imports (`import module: name1, name2`)
✅ Module file loading from `std/` directory
✅ Both `.au` file extension handling

**Next Steps:**
- Export declarations
- Import aliases
- Private definitions
- Circular dependency detection
