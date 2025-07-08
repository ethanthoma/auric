# Type

programming language with set theoretic types in a total/productive language
like charity

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
