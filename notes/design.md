# Design

## Binding Forms & Shadowing

Bindings are done under `const` and `let`.

`let` allow for shaddowing while `const` does not.

Top level bindings have to be `const` (subject to change).

A `rec` keyword appears directly in front of the opening `{}` of the literal
that needs to be recursive. The compiler forbids any reference to the binding
name inside that block without it.

## Unified Literal Syntax

Binding to an identifier is what turns a literal into a declaration.

Functions:

```rs
// anonymous
(x:Int, y:Int) -> Int { x + y }

// named
const add_one = (x) -> x + 1
```

Records:

```rs
// anonymous record
.{ x: Int, y: Int }

// named record
const Point = .{ x: Int, y: Int }

// record value
let origin = .{ x: 0, y: 0 }
```

Tuples:

```rs
// anonymous tuple
.{ String, Int }

// named tuple
const Name_Age = .{ String, Int }

// tuple value
let user_info = .{ "James", 31 }
```

Plain braces belong to grouping, while dot-braces denote records.

## Grammar Fragments (informal)

```ebnf
Expr           ::= FuncLiteral
                 | StructLiteral
                 | TupleLiteral
                 | …                               -- existing forms

FuncLiteral    ::= "(" ParamList? ")"
                   "->" ReturnAnn?
                   RecOpt
                   FuncBody

RecOpt         ::= "rec"?                          -- if present, value may self-reference

FuncBody       ::= Expr
                 | "{" Stmt* "}"

StructLiteral  ::= ".{" StructFieldList? "}"

ConstBinding   ::= ("let" | "const") Ident "=" Expr

TypeExpr        ::= TypeSegment (SetOp TypeSegment)*   -- all SetOps in a chain
                                                       -- must be identical

SetOp           ::= "|" | "&" | "-"                    -- precedence equal

TypeSegment     ::= GroupedType
                 | TypeAtom

GroupedType     ::= "{" TypeExpr "}"                   -- explicit grouping

TypeAtom        ::= TypeFuncLit
                 | ".{" FieldTypeList? "}"             -- record type
                 | "|" VariantAlt ("|" VariantAlt)*    -- variant literal
                 | Ident "(" TypeExprList? ")"         -- type-level call
                 | Ident                               -- bare name / Any / Void

RefineType ::= "{" Predicate "}"
Predicate  ::= BoolExpr            -- uses the term-language grammar
             | Ident "∈" TypeExpr  -- optional set-membership sugar

```

## `rec`, `ana`, and `cata`

Inductive (cata) and coinductive (ana) types need a `rec` keyword.

```rs
// inductive example
const Pair = (A, B) -> .{ fst: A, snd: B }

const swap = (p: Pair(X, Y)) -> Pair(Y, X) .{
    fst: p.snd, 
    snd: p.fst,
}

// co-inductive example
const Stream = (t) -> rec .{
  head : t,
  tail : Stream(t),
}

const nats = (start:Int) -> Stream(Int) rec .{
    head = start,
    tail = nats(start + 1),
}
```

## Example

```rs
const Number   = Int | Float
const Ordered  = {Int | Float | String} & Comparable
const Natural  = Int & { n >= 0 }
const Positive = Natural - { 0 }

const Maybe = (T) -> T | Void

// binary tree
const Tree = (T) -> rec | Leaf(T) | Node(Tree(T), Tree(T))

// intersection-of-arrows
const plus = 
      { (Int,   Int  ) -> Int   } 
    | { (Float, Float) -> Float }

// co-inductive stream of strictly positive integers
const PosStream = Stream(Int & { ν > 0 })

const from = (n: Int & { ν > 0 }) -> PosStream .{
    head = n,
    tail = from(n + 1),
}


// total function that stops at the first non-positive
const allPositive = (s: Stream(Int)) -> Bool {
  { s.head <= 0 } -> false
  _               -> allPositive(s.tail)
}

// the type checks because the intersection keeps only the safe calls
let ok = allPositive(from(1))      // Bool
```
