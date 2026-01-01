# Macro Syntax Evolution: Side-by-Side Comparison

**Goal:** Visualize the elegance improvements at each phase

---

## Example 1: Simple Macro (when)

### Current Syntax (Verbose)
```auric
macro when = (ast: Expr) => {
    ast => {
        App(App(Var("when"), test), body) -> {
            Case(test, {
                true = { body },
                false = { Record({}) }
            })
        };
        _ -> unreachable
    }
}
```
**Lines:** 11
**Boilerplate:** High (AST constructors, manual matching)
**Readability:** 3/10

### Phase 1: Multi-arg + Quasiquote
```auric
macro when = (test: Expr, body: Expr) => {
    quote {
        $test => {
            true -> $body;
            false -> {}
        }
    }
}
```
**Lines:** 7
**Boilerplate:** Medium (still need function signature)
**Readability:** 7/10

### Phase 2A: Pattern on Syntax
```auric
macro {
    'when $test { $body }' =>
        '$test => { true -> $body; false -> {} }'
}
```
**Lines:** 3
**Boilerplate:** Low (pattern + template only)
**Readability:** 9/10

### Phase 2D: + Implicit Quote
```auric
macro {
    when $test { $body } => $test => { true -> $body; false -> {} }
}
```
**Lines:** 1
**Boilerplate:** Minimal
**Readability:** 10/10

### Common Lisp (for comparison)
```lisp
(defmacro when (test &body body)
  `(if ,test (progn ,@body)))
```
**Lines:** 2
**Readability:** 9/10 (if you know Lisp)

**Auric Phase 2D is as concise as Lisp, but:**
- ✅ Type-safe
- ✅ Pattern matches surface syntax
- ✅ More readable for non-Lispers

---

## Example 2: Complex Macro (for loop)

### Current Syntax
```auric
macro for_loop = (ast: Expr) => {
    ast => {
        App(App(App(Var("for"), Var(var_name)), list_expr), body_expr) -> {
            App(
                App(Var("map"), Lam([var_name], body_expr)),
                list_expr
            )
        };
        _ -> unreachable
    }
}
```
**Lines:** 12
**Complexity:** Very high
**Readability:** 2/10

### Phase 1: Multi-arg + Quasiquote
```auric
macro for_loop = (var_name: Record[u8], list_expr: Expr, body_expr: Expr) => {
    quote {
        map(($var_name) => $body_expr, $list_expr)
    }
}
```
**Lines:** 5
**Complexity:** Medium
**Readability:** 7/10

### Phase 2A: Pattern on Syntax
```auric
macro {
    'for $v in $lst { $body }' =>
        'map(($v) => $body, $lst)'
}
```
**Lines:** 3
**Complexity:** Low
**Readability:** 10/10

### Scheme (for comparison)
```scheme
(define-syntax for
  (syntax-rules (in)
    [(for v in lst body ...)
     (map (lambda (v) body ...) lst)]))
```
**Lines:** 4
**Readability:** 8/10

**Auric wins on readability and conciseness!**

---

## Example 3: Optimization Pass

### Current Syntax
```auric
macro optimize = (ast: Expr) => {
    ast => {
        // Double negation
        App(Var("not"), [App(Var("not"), [x])]) -> optimize(x);

        // Identity
        App(Var("id"), [x]) -> optimize(x);

        // Arithmetic identities
        App(App(Var("+"), x), IntLit(0)) -> optimize(x);
        App(App(Var("+"), IntLit(0)), x) -> optimize(x);
        App(App(Var("*"), x), IntLit(0)) -> IntLit(0);
        App(App(Var("*"), IntLit(0)), x) -> IntLit(0);
        App(App(Var("*"), x), IntLit(1)) -> optimize(x);
        App(App(Var("*"), IntLit(1)), x) -> optimize(x);

        // Recurse
        App(f, args) -> App(optimize(f), map(optimize, args));
        Lam(params, body) -> Lam(params, optimize(body));

        // Default
        _ -> ast
    }
}
```
**Lines:** 22
**Repetition:** High (many similar patterns)
**Readability:** 5/10

### Phase 1: Multi-arg + Quasiquote
```auric
macro optimize = (ast: Expr) => {
    ast => {
        quote { not(not($x)) } -> optimize(x);
        quote { id($x) } -> optimize(x);

        quote { $x + 0 } -> optimize(x);
        quote { 0 + $x } -> optimize(x);
        quote { $x * 0 } -> quote { 0 };
        quote { 0 * $x } -> quote { 0 };
        quote { $x * 1 } -> optimize(x);
        quote { 1 * $x } -> optimize(x);

        quote { $f($..args) } ->
            quote { $(optimize(f))($..map(optimize, args)) };

        _ -> ast
    }
}
```
**Lines:** 17
**Repetition:** Still high
**Readability:** 7/10

### Phase 2E: + Alternatives
```auric
macro optimize = (ast: Expr) => {
    ast => {
        quote { not(not($x)) } -> optimize(x);
        quote { id($x) } -> optimize(x);

        quote { $x + 0 } | quote { 0 + $x } -> optimize(x);
        quote { $x * 0 } | quote { 0 * $x } -> quote { 0 };
        quote { $x * 1 } | quote { 1 * $x } -> optimize(x);

        quote { $f($..args) } ->
            quote { $(optimize(f))($..map(optimize, args)) };

        _ -> ast
    }
}
```
**Lines:** 14
**Repetition:** Reduced
**Readability:** 8/10

### Phase 2F: Parameter Pattern + Implicit Quote
```auric
macro optimize(
    | not(not($x)) => optimize($x)
    | id($x) => optimize($x)

    | $x + 0 | 0 + $x => optimize($x)
    | $x * 0 | 0 * $x => 0
    | $x * 1 | 1 * $x => optimize($x)

    | $f($args...) => $(optimize(f))($(map(optimize, $args)...))

    | _ => ast
)
```
**Lines:** 11
**Repetition:** Minimal
**Readability:** 10/10

### Common Lisp (with Optima pattern matching)
```lisp
(defun optimize (ast)
  (match ast
    (`(not (not ,x)) (optimize x))
    (`(id ,x) (optimize x))

    ((or `(+ ,x 0) `(+ 0 ,x)) (optimize x))
    ((or `(* ,x 0) `(* 0 ,x)) 0)
    ((or `(* ,x 1) `(* 1 ,x)) (optimize x))

    (`(,f . ,args)
     `(,(optimize f) ,@(mapcar #'optimize args)))

    (_ ast)))
```
**Lines:** 13
**Readability:** 8/10 (for Lispers)

**Auric Phase 2F is MORE concise and MORE readable!**

---

## Example 4: Type-Aware Macro (Auric-only)

### Phase 2D: With Type Queries
```auric
macro inline = (f: Expr, x: Expr) => {
    let f_type = type_of(f)
    let x_type = type_of(x)

    (f_type, x_type) => {
        // Inline if function is simple and arg is constant
        (Arrow(_, _), _) when is_simple(f) && is_const(x) =>
            inline_app(f, x);

        // Specialize polymorphic functions
        (Forall(tv, body), ty) =>
            inline(instantiate(f, tv, ty), x);

        // Default: no inlining
        _ => quote { $f($x) }
    }
}
```

**Lisp can't do this!** No type information at macro time.

---

## Elegance Metrics

| Phase | Conciseness | Readability | Power | Type Safety |
|-------|-------------|-------------|-------|-------------|
| **Current** | 2/10 | 3/10 | 8/10 | 10/10 |
| **Phase 1** | 6/10 | 7/10 | 9/10 | 10/10 |
| **Phase 2A** | 9/10 | 9/10 | 9/10 | 10/10 |
| **Phase 2E** | 9/10 | 9/10 | 10/10 | 10/10 |
| **Phase 2F** | 10/10 | 10/10 | 10/10 | 10/10 |
| **Lisp** | 9/10 | 8/10 | 10/10 | 0/10 |

**Auric Phase 2F achieves:**
- ✅ Lisp-level conciseness
- ✅ Better readability (no parens soup)
- ✅ Same power (full AST manipulation)
- ✅ Type safety (unique!)
- ✅ Totality (unique!)
- ✅ Exhaustiveness (unique!)

---

## Feature Impact Analysis

### Impact of Each Feature

| Feature | Conciseness | Readability | Power | Type Safety |
|---------|-------------|-------------|-------|-------------|
| Multi-arg App | +2 | +2 | +1 | 0 |
| Quasiquote | +2 | +2 | 0 | 0 |
| Pattern on syntax | +3 | +4 | 0 | +1 |
| Ellipsis | +1 | +1 | +2 | 0 |
| Type annotations | 0 | +1 | +1 | +3 |
| Guards | +1 | 0 | +2 | +1 |
| Alternatives | +2 | +1 | 0 | 0 |
| Parameter patterns | +1 | +2 | 0 | 0 |
| Implicit quote | +1 | +1 | 0 | 0 |

**Highest impact features:**
1. **Pattern on syntax** (+3/+4/0/+1) - Huge readability win
2. **Multi-arg App** (+2/+2/+1/0) - Foundation for everything
3. **Quasiquote** (+2/+2/0/0) - Essential for templates
4. **Type annotations** (0/+1/+1/+3) - Type safety
5. **Alternatives** (+2/+1/0/0) - Reduces repetition

---

## Recommended Priority

### Must Have (Phase 1)
1. Multi-arg App/Lam - **Foundation**
2. Quasiquote syntax - **Essential**

### High Priority (Phase 2A-C)
3. Pattern on syntax - **Biggest readability win**
4. Ellipsis - **Handle variable args**
5. Type annotations - **Safety + documentation**

### Medium Priority (Phase 2D-E)
6. Guards - **Conditional matching**
7. Alternatives - **Reduce duplication**

### Nice to Have (Phase 2F+)
8. Parameter patterns - **Syntactic sugar**
9. Implicit quote - **Less noise**
10. Named sub-patterns - **Complex patterns**

---

## Final Syntax Example

**The ultimate Auric macro syntax:**

```auric
macro optimize(
    // Algebraic simplification
    | not(not($x)) => optimize($x)
    | $x + 0 | 0 + $x | $x - 0 => optimize($x)
    | $x * 0 | 0 * $x => 0
    | $x * 1 | 1 * $x | $x / 1 => optimize($x)

    // Constant folding (with guards)
    | $x:lit $op:BinOp $y:lit => const_fold(op, x, y)

    // Inline pure functions
    | $f:ident($args:expr...) when is_pure(f) && all(is_const, $args) =>
        const_apply(f, $args...)

    // Beta reduction
    | (($x:ident) => $body)($arg) => substitute(x, arg, body)

    // Recursive descent
    | $f($args...) => $(optimize(f))($(map(optimize, $args)...))
    | ($params...) => $body => ($params...) => optimize($body)

    // Default
    | $x => $x
)
```

**This is:**
- As concise as Lisp ✅
- More readable than Lisp ✅
- Type-safe (unlike Lisp) ✅
- Total (unlike any language) ✅
- Pattern matches surface syntax ✅

**Auric achieves the impossible: Better than Lisp at Lisp's own game!**
