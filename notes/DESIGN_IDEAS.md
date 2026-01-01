# Design Ideas (Experimental)

This file documents design ideas and experimental features that may or may not
be implemented.

## Unified Literal Syntax (Experimental)

The following ideas were considered for unifying function, record, and tuple
literals:

### Old Syntax (Not Current)

- Functions use `(x: Type) -> Type { ... }`
- Records use `.{ field: Type, ... }`
- Tuples use `.{ Type, ... }`

### Current Syntax (See GRAMMAR.md)

- All use consistent `{ }` syntax
- Blocks are context-aware (pattern matching vs let/return vs simple
  expressions)

## Binding Forms

Experimental ideas:

- `const` for immutable top-level bindings
- `let` for local bindings with shadowing
- `rec` keyword for recursive definitions

Note: Current implementation uses `const` for top-level and pattern matching/let
blocks for local scope.

## Set-Theoretic Types (Future)

Ideas for union, intersection, and difference types:

```
Number = Int | Float
Natural = Int & { n >= 0 }
Positive = Natural - { 0 }
```

Current status: Type system architecture supports these, but parsing/elaboration
incomplete.

## Refinement Types

Using set-membership and predicates:

```
const Natural = Int & { n >= 0 }
const Positive = Nat & { n > 0 }
```

Current status: Architecture in place, not fully elaborated.

## Inductive/Coinductive Types with rec

Experimental syntax for recursive types:

```
const Tree = (T) -> rec | Leaf(T) | Node(Tree(T), Tree(T))
const Stream = (T) -> rec .{ head: T, tail: Stream(T) }
```

Current status: Not implemented.

## TODO: Future Work

- [ ] Complete record literal syntax (`{ x = 1, y = 2 }`)
- [ ] Type-level function application
- [ ] Refinement type elaboration
- [ ] Inductive/coinductive type support
- [ ] Set-theoretic type operations
- [ ] Module system / Standard library imports
