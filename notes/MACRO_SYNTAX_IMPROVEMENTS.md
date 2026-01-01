# Advanced Macro Syntax Improvements

**Goal:** Make Auric macros MORE elegant than s-expressions

---

## Current State (After Phase 1)

**With multi-arg + quasiquote:**
```auric
macro for = (v: Record[u8], lst: Expr, body: Expr) => {
    quote { map(($v) => $body, $lst) }
}
```

**Still verbose:**
- Need to destructure AST manually
- Explicit `quote { }` everywhere
- Type annotations verbose
- No pattern matching on concrete syntax

---

## Improvement 1: Pattern on Quoted Syntax (Rhombus)

**Instead of matching AST structure:**
```auric
macro for = (ast: Expr) => {
    ast => {
        App(Var("for"), [Var(v), lst, body]) -> ...
    }
}
```

**Match what user actually writes:**
```auric
macro {
    'for $v in $lst { $body }' => 'map(($v) => $body, $lst)'
}
```

**Benefits:**
- ✅ Matches surface syntax, not AST
- ✅ No manual destructuring
- ✅ More readable
- ✅ Less coupled to AST representation

**Syntax:**
- `'...'` quotes syntax pattern
- `$var` binds to AST node
- Right side is template

---

## Improvement 2: Ellipsis for Repetition (Scheme)

**Problem: Handling variable-length arguments**
```auric
// How to match f(x, y, z) with any number of args?
'$f($args)' => ...  // Only matches one arg!
```

**Solution: Ellipsis `...`**
```auric
macro {
    // Match any number of arguments:
    'f($args...)' => 'g($args...)'

    // Match at least one:
    'cons($head, $tail...)' => '{ _0 = $head, $tail... }'

    // Multiple ellipsis:
    'zip($xs..., $ys...)' => ...
}
```

**Benefits:**
- ✅ Handle variable-length patterns
- ✅ Clean syntax (from Scheme)
- ✅ Composable

---

## Improvement 3: Type-Annotated Patterns (Racket)

**Problem: Want to ensure we match the right kind of thing**
```auric
'for $v in $lst { $body }'
// What if v is not an identifier? What if lst is not expression?
```

**Solution: Syntax classes**
```auric
macro {
    'for $v:ident in $lst:expr { $body:block }' =>
        'map(($v) => $body, $lst)'
}
```

**Builtin classes:**
- `:ident` - Identifier
- `:expr` - Expression
- `:ty` - Type
- `:block` - Block
- `:pat` - Pattern
- `:lit` - Literal

**Benefits:**
- ✅ Better error messages ("expected identifier, got 123")
- ✅ Type checking in patterns
- ✅ Self-documenting

**Custom syntax classes:**
```auric
syntax class BinOp = { '+' | '-' | '*' | '/' }

macro {
    'optimize($x $op:BinOp 0)' when op == '+' || op == '-' => '$x'
}
```

---

## Improvement 4: Guards on Patterns (Haskell)

**Problem: Sometimes pattern alone isn't enough**
```auric
// Want to inline only pure functions:
'$f($x)' => inline(f, x)  // But what if f has effects?
```

**Solution: Pattern guards**
```auric
macro optimize = {
    '$f($x)' when is_pure(f) => inline(f, x);

    'not(not($x))' => optimize(x);

    '$x $op $y' when is_constant(x) && is_constant(y) =>
        const_fold(op, x, y);

    _ => ast
}
```

**Benefits:**
- ✅ More precise control
- ✅ Can query properties (purity, constantness, etc.)
- ✅ Composable with patterns

---

## Improvement 5: Implicit Quote/Unquote

**Problem: Too many quotes**
```auric
macro for = (v, lst, body) => {
    quote { map(($v) => $body, $lst) }  // quote everywhere!
}
```

**Solution: Context-sensitive quoting**

**In macro definition context:**
- RHS is automatically quoted
- Variables are automatically unquoted
- Explicit `$` only when needed for clarity

```auric
// Implicit quote on RHS:
macro {
    for $v in $lst { $body } => map(($v) => $body, $lst)
    //                           ^^^^^^^^^^^^^^^^^^^^^^^^^
    //                           Implicitly quoted!
}

// Explicit quote when building complex AST:
macro complex = (x: Expr) => {
    let tmp = fresh_var()
    { let $tmp = $x; $tmp + $tmp }  // Still quoted
}
```

**Benefits:**
- ✅ Less syntactic noise
- ✅ More readable
- ✅ Quote/unquote only when ambiguous

---

## Improvement 6: Named Sub-Patterns (Dylan)

**Problem: Complex patterns hard to read**
```auric
'$f($(g($x)), $(h($y)))' => ...  // What's what?
```

**Solution: Named sub-patterns with `as`**
```auric
macro {
    '$f($arg1 as $g($x), $arg2 as $h($y))' =>
        'g($f(x, $arg2))'  // Can refer to $arg1 or $g($x)
}
```

**Benefits:**
- ✅ More readable
- ✅ Can refer to sub-trees
- ✅ Better error messages

---

## Improvement 7: Alternatives and Fallback (MetaOCaml)

**Problem: Sometimes multiple patterns produce same result**
```auric
macro {
    '$x + 0' => $x;
    '0 + $x' => $x;  // Duplicated RHS!
}
```

**Solution: Pattern alternatives**
```auric
macro {
    '$x + 0' | '0 + $x' => $x;

    '$x * 0' | '0 * $x' => 0;

    '$x * 1' | '1 * $x' | '$x / 1' => $x;
}
```

**Benefits:**
- ✅ DRY (don't repeat yourself)
- ✅ More concise
- ✅ Groups related patterns

---

## Improvement 8: Recursive Patterns (Prolog-style)

**Problem: Deep matching requires deep nesting**
```auric
macro {
    'not(not($x))' => $x;
    'not(not(not(not($x))))' => $x;  // Need to repeat?
}
```

**Solution: Recursive pattern matching**
```auric
macro {
    'not(not($x))' => optimize($x);  // Recursively process result
}

// Or with explicit recursion:
macro normalize = {
    'not(not($x))' => normalize($x);  // Keep simplifying
    _ => ast
}
```

**Benefits:**
- ✅ Handles nested patterns
- ✅ Automatic recursion
- ✅ No manual traversal

---

## Improvement 9: Destructuring in Function Parameters

**Problem: Every macro starts with pattern match**
```auric
macro for = (ast: Expr) => {
    ast => {
        'for $v in $lst { $body }' => ...
    }
}
```

**Solution: Pattern in parameter**
```auric
macro for('for $v in $lst { $body }') =>
    map(($v) => $body, $lst)

// Or multiple patterns:
macro optimize(
    | 'not(not($x))' => optimize($x)
    | '$x + 0' | '0 + $x' => $x
    | '$x * 0' | '0 * $x' => 0
    | _ => ast
)
```

**Benefits:**
- ✅ No boilerplate match
- ✅ More concise
- ✅ Pattern directly in signature

---

## Improvement 10: Hygienic Capture (Scheme)

**Problem: Want to capture variables intentionally**
```auric
macro with_logging(body) => {
    let logger = Logger.new()  // Fresh variable
    { logger.start(); $body; logger.end() }
    // But how does body access logger?
}
```

**Solution: Explicit hygiene control**
```auric
macro with_logging($body) => unhygienic(logger) {
    { let logger = Logger.new();
      logger.start();
      $body;  // Can now use 'logger'
      logger.end() }
}

// Usage:
with_logging {
    logger.log("hello")  // Works!
}
```

**Or pattern-based:**
```auric
macro with_logging($body) => {
    // Inject 'it' variable:
    inject(it = Logger.new()) {
        { it.start(); $body; it.end() }
    }
}
```

**Benefits:**
- ✅ Intentional capture
- ✅ Anaphoric macros
- ✅ Still safe (explicit)

---

## Complete Example: All Features Combined

**Ultra-concise macro definition:**

```auric
macro optimize(
    // Simple patterns with alternatives
    | '$x + 0' | '0 + $x' | '$x - 0' => $x
    | '$x * 0' | '0 * $x' => 0
    | '$x * 1' | '1 * $x' | '$x / 1' => $x

    // Recursive patterns
    | 'not(not($x))' => optimize($x)

    // With guards
    | '$x $op:BinOp $y' when is_const(x) && is_const(y) =>
        const_fold(op, x, y)

    // Ellipsis for multiple args
    | '$f($args...)' when is_pure(f) && all(is_const, args) =>
        const_apply(f, $args...)

    // Named sub-patterns
    | 'if $test { $then } else { $else }' as $if_expr
        when equals($then, $else) =>
        { $then; $test }  // Evaluate test for effects, return then

    // Recursive call
    | '$f($args...)' => $f($(map(optimize, $args)...))

    // Default
    | _ => ast
)
```

**Compare to Lisp:**
```lisp
(defun optimize (ast)
  (match ast
    ;; Simple patterns
    ((or `(+ ,x 0) `(+ 0 ,x) `(- ,x 0)) x)
    ((or `(* ,x 0) `(* 0 ,x)) 0)
    ((or `(* ,x 1) `(* 1 ,x) `(/ ,x 1)) x)

    ;; Recursive
    (`(not (not ,x)) (optimize x))

    ;; With guard
    (`(,op ,x ,y)
     (when (and (const? x) (const? y) (binop? op))
       (const-fold op x y)))

    ;; Multiple args
    (`(,f . ,args)
     (when (and (pure? f) (every #'const? args))
       (const-apply f args)))

    ;; Named sub-pattern
    ((and if-expr `(if ,test ,then ,else))
     (when (equal then else)
       `(progn ,then ,test)))

    ;; Recursive
    (`(,f . ,args)
     `(,f ,@(mapcar #'optimize args)))

    (_ ast)))
```

**Auric is actually MORE concise!** And type-safe!

---

## Syntax Summary

| Feature | Syntax | Example |
|---------|--------|---------|
| Quote pattern | `'...'` | `'for $v in $lst { $body }'` |
| Bind variable | `$var` | `'f($x)'` binds x |
| Type annotation | `$var:type` | `'for $v:ident in $lst:expr'` |
| Ellipsis | `$vars...` | `'f($args...)'` |
| Alternative | `pat1 \| pat2` | `'$x + 0' \| '0 + $x'` |
| Guard | `when expr` | `'$f($x)' when is_pure(f)` |
| Named sub-pattern | `$p as pattern` | `$if as 'if $t { $b }'` |
| Implicit quote | (none) | RHS auto-quoted in macro |
| Unquote | `$var` | `$x` splices value |
| Splice | `$..vars` | `f($..args)` splices all |

---

## Implementation Phases

### Phase 2A: Pattern on Syntax (2 weeks)

**Add:**
```auric
macro {
    'pattern' => 'template'
}
```

**Parser:**
1. Recognize `'...'` as syntax pattern
2. Parse pattern, extract `$vars`
3. Generate matcher code
4. Parse RHS as template

### Phase 2B: Ellipsis (1 week)

**Add:**
```auric
'f($args...)'
```

**Implementation:**
- `$var...` matches zero or more
- Generate loop in matcher
- Expand in template

### Phase 2C: Type Annotations (1 week)

**Add:**
```auric
'$v:ident' '$x:expr' '$t:ty'
```

**Implementation:**
- Check bound variable type
- Better error messages
- Type-driven matching

### Phase 2D: Guards (1 week)

**Add:**
```auric
'pattern' when condition => 'template'
```

**Implementation:**
- Evaluate guard after pattern matches
- Can call arbitrary functions
- Short-circuit on false

### Phase 2E: Alternatives (3 days)

**Add:**
```auric
'pat1' | 'pat2' | 'pat3' => 'template'
```

**Implementation:**
- Try patterns in order
- Share RHS code
- Simple desugaring

### Phase 2F: Parameter Patterns (1 week)

**Add:**
```auric
macro for('for $v in $lst { $body }') => ...
```

**Implementation:**
- Pattern in parameter position
- Desugar to match
- Cleaner syntax

---

## Expected Final Elegance

**Lisp (Common Lisp with Optima):**
```lisp
(defmacro for ((var lst) &body body)
  `(map (lambda (,var) ,@body) ,lst))
```

**Auric (with all improvements):**
```auric
macro for('for $v:ident in $lst:expr { $body:block }') =>
    map(($v) => $body, $lst)
```

**Comparison:**
- Lisp: 2 lines, manual quasiquote, no types
- Auric: 2 lines, implicit quote, type-safe

**Auric is MORE elegant because:**
- ✅ Pattern matches what user writes
- ✅ Type annotations for safety
- ✅ No manual quoting
- ✅ Exhaustiveness checking
- ✅ Totality guaranteed

---

## Beyond Lisp: Unique Auric Features

**What Auric can do that Lisp can't:**

### 1. Type-Aware Macros
```auric
macro specialize($f:expr, $x:expr) => {
    let f_type = type_of(f)
    let x_type = type_of(x)

    (f_type, x_type) => {
        (Arrow(Int, Int), Int) when is_const(x) =>
            unroll_int_function(f, x);
        _ => App(f, [x])
    }
}
```

### 2. Dependent Type Generation
```auric
macro make_vector($elems...) => {
    let n = count($elems...)
    quote {
        ($elems...) : Vec[_, $n]  // Generate indexed type
    }
}
```

### 3. Exhaustiveness-Checked Patterns
```auric
macro handle_result($expr:expr) => {
    $expr => {
        Ok($val) => $val;
        Err($e) => unreachable  // Caller guarantees Ok
        // Compiler ensures we handled all cases!
    }
}
```

### 4. Totality-Checked Transformations
```auric
// Compiler verifies this terminates:
macro simplify($ast:expr) => {
    $ast => {
        'not(not($x))' => simplify($x);  // Structural recursion
        // All recursive calls on subterms → guaranteed termination
    }
}
```

---

## Summary: Syntax Elegance Levels

| Level | Features | Example | Elegance |
|-------|----------|---------|----------|
| **Current** | AST matching | `App(Var("f"), [x])` | 5/10 |
| **Phase 1** | Multi-arg + quote | `quote { f($x) }` | 7/10 |
| **Phase 2A** | Pattern on syntax | `'f($x)' => 'g($x)'` | 9/10 |
| **Phase 2B** | + Ellipsis | `'f($xs...)' => ...` | 9.5/10 |
| **Phase 2C** | + Types | `'f($x:expr)' => ...` | 9.5/10 |
| **Phase 2D** | + Guards | `when is_pure(f)` | 10/10 |
| **Full** | All features | See complete example | **11/10** |

**With full features, Auric macros are MORE elegant than Lisp, with:**
- Type safety
- Totality
- Exhaustiveness
- Dependent types
- Better tooling

---

## Questions for You

1. **Which features are most important?** Guards? Ellipsis? Type annotations?

2. **Syntax preferences?**
   - `'pattern' => 'template'` vs `quote { pattern } => quote { template }`?
   - `$var` vs `,var` for unquote?
   - `$var...` vs `$var*` for ellipsis?

3. **Implicit vs explicit?**
   - Auto-quote RHS? Or always explicit `quote { }`?
   - Auto-unquote variables? Or explicit `$`?

4. **Multiple macro types?** (Like Nim)
   - Just `macro`?
   - Or also `template`, `rewrite`, etc.?

5. **How far to go?** Stop at Phase 2A? Or go all the way to guards?
