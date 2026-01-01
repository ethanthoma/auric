# Macro System Design for Auric

## Goals

1. **Syntax sugar on top of primitives** - Macros desugar to core record/function primitives
2. **Hygiene** - Avoid variable capture
3. **Compile-time expansion** - All macros expand before type checking
4. **Pattern-based** - Match on syntax patterns, expand to templates

## Core Principles

- Macros are NOT primitives - they're syntax transformations
- Everything desugars to records, functions, and primitives
- Macro expansion happens in a separate pass before type checking
- Keep it simple - this is sugar, not a full metaprogramming system

## Macro Syntax

### Defining Macros

```auric
// Basic macro definition
macro vec_index(v, i) {
  v._(stringify(i))
}

// Pattern-based macro (hypothetical)
macro when(cond, body) {
  // TODO: Define what this expands to
  // (depends on actual control flow primitives)
}
```

### Using Macros

```auric
// Array indexing syntax
const v = .{ zero, succ(zero), succ(succ(zero)) }
const first = v[0]  // expands to v._0

// String literals
const msg = "hello"  // expands to .{ 'h', 'e', 'l', 'l', 'o' }

// When macro (hypothetical - not yet implemented)
when(x > 0, Print("positive"))  // would need control flow primitives
```

## Built-in Macros

### 1. Array Indexing: `vec[n]` → `vec._n`

```auric
macro index(vec, n) {
  vec._(stringify(n))
}

// Usage:
const v = .{ zero, succ(zero) }
const x = v[0]  // → v._0
```

### 2. String Literals: `"text"` → record of chars

```auric
macro string(s) {
  // Expands "hello" to .{ 'h', 'e', 'l', 'l', 'o' }
  .{ ...chars(s) }
}
```

### 3. List Literals: `[x, y, z]` → nested cons

```auric
macro list(...elems) {
  // [1, 2, 3] → cons(1, cons(2, cons(3, nil)))
  fold_right(elems, nil, (elem, rest) -> cons(elem, rest))
}
```

### 4. Do-notation for effects

```auric
macro do(...stmts) {
  // do { x <- Read(); Print(x) }
  // → Read() >>= (x -> Print(x))
  chain_effects(stmts)
}
```

## Implementation Strategy

### Phase 1: Macro Definition Storage

```python
# In parser or separate macro module
@dataclass
class MacroDef:
    name: str
    params: List[str]
    template: Exp  # The expansion template

macro_table: Dict[str, MacroDef] = {}
```

### Phase 2: Macro Expansion Pass

```python
def expand_macros(e: Exp, macros: Dict[str, MacroDef]) -> Exp:
    """
    Walk the expression tree and expand all macro invocations.
    This runs BEFORE type checking.
    """
    if isinstance(e, MacroInvocation):
        macro = macros[e.macro_name]
        # Substitute parameters with arguments
        return expand_macros(substitute(macro.template, macro.params, e.args), macros)

    # Recursively expand in subexpressions
    # ...

    return e
```

### Phase 3: Integration into Pipeline

```python
# Current: parse → type_check → evaluate
# New:     parse → expand_macros → type_check → evaluate

def run_auric(src: str):
    sigs, defs = parse(src)

    # NEW: Expand macros in all definitions
    expanded_defs = {name: expand_macros(expr, macro_table)
                     for name, expr in defs.items()}

    # Type check expanded code
    types = type_of(expanded_defs, env)

    # Evaluate
    results = evaluate(expanded_defs, env)
    return results
```

## Hygiene Strategy

**Simple approach: Gensym for introduced bindings**

```python
def gensym(base: str) -> str:
    """Generate unique variable name"""
    global _gensym_counter
    _gensym_counter += 1
    return f"{base}${_gensym_counter}"

# When expanding macro, rename all bound variables
def expand_macro_hygienically(macro: MacroDef, args: List[Exp]) -> Exp:
    # 1. Substitute parameters with arguments
    expanded = substitute(macro.template, macro.params, args)

    # 2. Rename all bindings introduced by the macro
    expanded = rename_bindings(expanded, gensym)

    return expanded
```

## Example: Implementing `v[i]` syntax

### Step 1: Extend Lexer

```python
# Recognize [ and ] as tokens
SPECIAL_CHARS = {"(", ")", "{", "}", "[", "]", ".", ",", "=", ":", "|", "&", "-", ">"}
```

### Step 2: Parse as Macro Invocation

```python
# In _expr() after primary expression:
if b.peek() == "[":
    b.pop()  # consume "["
    index_tokens = []
    while b.peek() != "]":
        index_tokens.append(b.pop())
    b.pop()  # consume "]"

    index_expr = _expr(Buf(index_tokens))
    # Create macro invocation: index(lhs, index_expr)
    lhs = MacroInvocation("index", [lhs, index_expr])
```

### Step 3: Built-in Index Macro

```python
# Built-in macro: vec[i] → vec._i when i is literal
def expand_index_macro(vec_expr: Exp, index_expr: Exp) -> Exp:
    # If index is a literal number, expand to field access
    if isinstance(index_expr, Var) and index_expr.name.isdigit():
        return FieldAccess(vec_expr, f"_{index_expr.name}")

    # Otherwise, error - we only support compile-time indices
    raise SyntaxError("Vector indices must be compile-time constants")
```

## Macro Categories

### 1. Syntax Sugar (Pure Desugaring)
- `v[0]` → `v._0`
- `"hello"` → `.{ 'h', 'e', 'l', 'l', 'o' }`
- `[1, 2, 3]` → `cons(1, cons(2, cons(3, nil)))`

### 2. Control Flow Sugar (Future)
- TBD based on actual control flow primitives in Auric
- May not be needed if language stays purely functional

### 3. Effect Composition
- `do { x <- Read(); Print(x) }` → chained effects
- `let! x = Read() in Print(x)` → effect binding

### 4. Record/Tuple Sugar
- `(x, y, z)` → `.{ x, y, z }` (redundant but convenient)
- Computed field names: `.{ [name] = value }` → macro expansion

## Design Decisions

### DO:
- ✓ Keep macros simple and pattern-based
- ✓ Expand before type checking (macros don't see types)
- ✓ Make common syntactic patterns convenient
- ✓ Use gensym for hygiene

### DON'T:
- ✗ Allow macros to inspect types (that's for type-level functions)
- ✗ Allow macros to perform side effects
- ✗ Create complex macro DSL - keep it simple
- ✗ Allow runtime macro expansion

## Open Questions

1. **Macro definition syntax** - Should macros be defined in Auric syntax or externally?
   - Option A: Auric syntax `macro name(params) { template }`
   - Option B: Python-defined built-ins only
   - **Decision: Start with Python built-ins, add Auric syntax later**

2. **Variadic macros** - Do we need `...rest` syntax?
   - Probably yes for list literals: `[1, 2, 3]`
   - Use `*args` style: `macro list(*elems) { ... }`

3. **Quasiquotation** - Do we need `` ` `` and `,` for building syntax?
   - Not needed initially - simple template substitution is enough
   - Can add later if needed for complex macros

4. **Macro expansion order** - Inside-out or outside-in?
   - **Decision: Outside-in (expand outer macros first)**
   - Simpler to implement and reason about

## Next Steps

1. Add `MacroInvocation` AST node
2. Implement basic macro expansion pass
3. Add built-in macros: `index`, `string`, `list`
4. Test with examples
5. Consider adding Auric-level macro definitions later
