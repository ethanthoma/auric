# Syntax

## Three Primitives

Laziness `()` (Suspension & Forcing). Computation primitive. It allows any
expression to be suspended (made lazy) and evaluated later:

- (expression): Suspends the expression into a lazy "thunk".
- thunk(): Forces the evaluation of a suspended thunk.

Mapping `->` (Transformation): Relation primitive. It defines a directional
mapping from a pattern on the left to an expression on the right.

Grouping `{}` (Structure & Scope). Composition primitive. It groups a set of
mappings and expressions into a single, cohesive unit, defining a scope.

## Catamorphism & Matching

A function definition is a pattern match on the `all` case.

Take Gleam pattern match example:

```gleam
fn get_or_default(val: Option(int), default: int) -> int {
    case val {
        Some(x) -> x
        None -> default
    }
}
```

Taking that all expressions become matches, we get:

```gleam
fn get_or_default(val: Option(int), default: int) -> int {case {
    _ -> case val {
        Some(x) -> x
        None -> default
    }
}}
```

We then decompose the nested matches so that you can match directly on the
parameters (like Haskel and co):

```rs
fn get_or_default(val: Option(int), default: int) -> int {
    Some(x), _ -> x
    None, default -> default
}
```

A recursive call is only allowed inside the function's body, and only on a
variable that is a structurally smaller piece of one of the matched patterns.
Any other form of recursion is a compile-time error.

## Anamorphism

For producing a coinductive data structure, we can use the `()` syntax,
explicitly suspending computation.

## Decls

Set types are very structural. We can probably have a `distinct` keyword for
making them nominal.

I like the uniformity of Odin Lang syntax but I can see an argument for
readability. Maybe we can have a special `type` keyword:

```rs
type Point = {x: int, y: int}
type Some<T> = { tag: "Some", value: T }
type None = { tag: "None" }

type Maybe<T> = Some<T> | None
```

I don't like `<>` for generics. Gleam syntax for it is nice (i.e. just functions
over types which I think maps cleanly).

I like Zig Lang tuples/structs. A struct (or a record) is a product type with
named fields. A tuple does not have named fields. This way the syntax is more or
less the same which is nice since they're both product types.

```rs
type None
type Some(T) = {value: T} // a record/struct
type Maybe(T) = Some(T) | None

type Vec2(T) = {T, T} // a tuple
```

Idk if I should use 'let' bindings for type alias' or use `type` + `alias`.
Maybe the latter since it is more clear.
