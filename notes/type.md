# Type

programming language with set theoretic types in a total/productive language
like charity

turing complete languages are everywhere and boring af

## Totality w/ set types

Not a blocker:

- Totality/strong normalisation is a property of the term-level reduction
  system: every closed, well-typed term reduces to a value
- Adding new type connectives does not give any extra run-time operations. Only
  changes how to classify existing values
- Intersection types are often used to prove strong normalisation. They
  characterise exactly the lambda-terms that terminate
- Subtyping systems that include top, bottom and finite (co)products can be
  shown to preserve strong normalisation under suitable syntactic restriction

Possible problems (yay):

- Algorithmic subtyping may diverge. Can limit to finite unions/intersections
  and forbid De Morgan push-down inside function types OR use semantic subtyping
  algorithms that are known to terminate
- Subject-reduction can fail for union types (Forsythe merge unrestricted). Can
  keep the surface language schematic (no run-time merges) and elaborate into
  ordinary lambda-terms
- Complement/negation breaks canonicity. Can restrict negation to atomic types
  or drop it entirely and keep only finite difference A\\B, where B is an open
  type expression

[subtyping](https://rosstate.org/publications/empower/empower-oopsla18.pdf)
[union types](https://arxiv.org/abs/1206.5386)
[negation](https://arxiv.org/abs/2111.03354)

These restrictions are orthogonal to Charity’s folds/ unfolds, so termination is
intact

Full classical complement (~A := ⊤\\A) together with dependent types gives
Girard’s paradox

Unrestricted recursive types + complement can make subtyping undecidable (duh)

Implicit down-casts (run-time tests) re-introduce partiality. Must expose them
as total pattern matches that return evidence

Type-checker implements:

- A bidirectional algorithm (Muehlboeck–Tate) for finite union/intersection
- Semantic subtyping rules (A union B \<= C iff A\<=C intersects B\<=C, etc.).
- A syntactic positivity check to preserve the initial-algebra semantics of data
  declarations

## Refinement Types

They are orthogonal

Checker works via two phases:

1. Shape phase (fast lattice walk)
1. Check that the ordinary constructors line up.

Result: a canonical shape type S

Refinement phase (SMT or proof search)

For each judgment t : {x:S | phi} generate a verification condition (VC):
“assuming the current context, prove phi(t)”. If the VC is in the allowed
theory, dispatch it to an SMT solver or run the local proof term the programmer
provides

Sub-typing combines the two results and Because each oracle terminates on its
own, the composition still terminates

## Generics

Having functions over types is super cool and seems totally unsafe in a
total/productive language (RIP my other note and Zig comptime).

There is probably a finite set of generics this language can have before running
into those issues, still need to explore...

## Effects

Algebraic effects are super cool but probably not uber performant (idk if that
matters). I think it is possible to add to the language. Might be nice for the
productivity aspect (like an IO effect).

Exceptions are less powerful than effects so no reason to entertain the idea.

Errors as values is still supported but I am unsure the trade-off.

Super not a fan of flix syntax but koka looks cool.

## Uniqueness Types

Controlled and limited mutation would be nice. Hard to know if I can sneak this
in with totality.

Clean Lang seems like a good place to look for uniqueness. Maybe there is a
limited subset that is decidable.

## Let Generalization

No.

## Polymorphism

Can explore ad-hoc (my bb overloading wooot)

Maybe an intersection-of-arrows as the type of an overloaded value

But I'm not super convinced. It is nicer for a sort-of defaults in functions
