# Macro System Recommendations for Auric

**Based on survey of 25+ macro systems across languages**

---

## The Core Question

**Can we achieve s-expression elegance without s-expression syntax?**

**Answer: YES.** Proof: **Rhombus (Racket 2)**

---

## Key Insights from Survey

### 1. Rhombus: Non-S-Expression Power ⭐⭐⭐

```rhombus
// This is NOT s-expressions, but has full Lisp macro power:
macro 'when $test: $body':
  'if $test: $body'

// Entire OOP system built with macros:
class Point(x, y):
  method distance():
    math.sqrt(x*x + y*y)
```

**What Rhombus proves:**
- ✅ You DON'T need parentheses for macro power
- ✅ You DON'T need s-expressions
- ✅ You DO need: pattern matching + quasiquoting + hygiene

**The secret:**
- Parse to structured syntax trees (not s-expressions)
- Pattern match on surface syntax
- Template with quasiquoting
- Automatic hygiene

### 2. Scala 3: Macros During Elaboration ⭐⭐⭐

```scala
// Macros run DURING type checking:
inline def summon[T]: T =
  scala.compiletime.summonInline[T]

// Can query and influence types:
inline def power(x: Double, inline n: Int): Double =
  inline n match
    case 0 => 1.0
    case _ => x * power(x, n - 1)
```

**What Scala 3 shows:**
- ✅ Macros can access type information
- ✅ Macros can influence type inference
- ✅ Macros run during elaboration (not before)

**Perfect for dependent types!**

### 3. Nim: Multiple Tools ⭐⭐

```nim
template unless(cond, body): untyped =  # Simple substitution
  if not cond: body

macro transform(arg: untyped): untyped =  # AST transformation
  quote do: echo `arg`
```

**What Nim shows:**
- Different tools for different jobs
- `template` for simple cases
- `macro` for complex cases
- Don't need one monolithic system

### 4. What S-Expressions Actually Give You

From the survey, s-expressions provide:

1. **Uniform structure** - Every node is the same shape (list)
2. **Minimal notation** - Just `` ` , ,@ ``
3. **Trivial to parse** - Already structured
4. **Easy to build/destruct** - Same operations everywhere

**But you can get the same with:**
- Algebraic data types (variants) → Uniform operations
- Quasiquote syntax → Templates
- Pattern matching → Destructuring
- Automatic parsing to AST → Structured

---

## What Auric Currently Has

### ✅ Good Parts

1. **AST as variants** - Typed, pattern-matchable
2. **Pattern matching** - Exhaustive, type-safe
3. **Hygiene** - Automatic (like Rust/Scheme)
4. **Unified syntax** - Same at comptime/runtime (like Zig)
5. **Totality** - Termination guaranteed (UNIQUE!)

### ❌ Missing Parts

1. **Multi-arg App/Lam** - Currently binary: `App(App(App(f, x), y), z)`
2. **Quasiquote syntax** - No clean templates: `quote { f($x, $y) }`
3. **Pattern on surface syntax** - Match what user writes, not AST
4. **Type information** - Macros can't query types yet
5. **Splicing** - No `$..` for variable-length lists

---

## Concrete Recommendations

### Phase 1: Core Improvements (Essential)

#### 1.1. Multi-Argument App/Lam

**Change:**
```auric
// From:
type Expr =
    | App(fn: Expr, arg: Expr)           // Binary
    | Lam(param: Record[u8], body: Expr) // Single param

// To:
type Expr =
    | App(fn: Expr, args: Vec[Expr, n])        // Multiple args
    | Lam(params: Vec[Record[u8], n], body: Expr) // Multiple params
```

**Impact:**
```auric
// Before:
App(App(App(Var("f"), x), y), z) -> ...  // Nested

// After:
App(Var("f"), [x, y, z]) -> ...  // Flat
```

**Benefits:**
- ✅ S-expression-like flat structure
- ✅ Easier pattern matching
- ✅ More elegant
- ✅ Closer to surface syntax

**Tradeoff:**
- Dependent types for arg count: `Vec[Expr, n]`
- More complex initial implementation

**Priority:** HIGH - Foundation for everything else

#### 1.2. Quasiquote Syntax

**Add:**
```auric
quote { expr }   // Parse expr to AST
$var             // Splice variable
$..vec           // Splice vector (variadic)
```

**Examples:**
```auric
// Instead of:
App(Var("f"), [x, y])

// Write:
quote { f($x, $y) }

// With splicing:
quote { f($..args) }
```

**Implementation:**
- Parser recognizes `quote { }` blocks
- Inside quote: parse normally but build AST
- `$var` splices the value of var
- `$..vec` splices all elements of vec

**Benefits:**
- ✅ Clean template syntax (like Lisp backtick)
- ✅ More readable
- ✅ Less construction boilerplate

**Priority:** HIGH - Essential ergonomics

#### 1.3. Macroexpand Debugging

**Add:**
```auric
macroexpand(expr)   // Show expanded form
print_ast(expr)     // Show AST structure
```

**Usage:**
```auric
macroexpand(quote { for x in list { body } })
// → Shows: map((x) => body, list)
```

**Priority:** MEDIUM - Needed for development

---

### Phase 2: Advanced Features (Nice to Have)

#### 2.1. Pattern Matching on Surface Syntax (Rhombus-style)

**Add:**
```auric
// Match what user writes:
macro 'for $v in $lst { $body }' =>
  'map(($v) => $body, $lst)'

// Not what AST looks like:
macro for = (ast: Expr) => {
    ast => {
        App(Var("for"), [Var(v), lst, body]) -> ...
    }
}
```

**Benefits:**
- ✅ Much cleaner macro definitions
- ✅ Pattern matches surface syntax
- ✅ Less coupling to AST details

**Challenges:**
- Need to define syntax patterns
- How to handle ambiguity?
- Parser complexity

**Priority:** MEDIUM - Great ergonomics but complex

#### 2.2. Type-Aware Macros (Scala 3-style)

**Add:**
```auric
// Macro can query types:
macro inline = (f: Expr) => {
    let ty = type_of(f)  // Query type during elaboration
    ty => {
        Arrow(_, _) -> inline_function(f);
        _ -> f
    }
}
```

**Implementation:**
- Macros run during elaboration (not before)
- Can call `type_of(expr)` to query
- Can generate different code based on types

**Benefits:**
- ✅ Essential for dependent types
- ✅ Type-driven code generation
- ✅ More powerful macros

**Challenges:**
- Macros interleaved with type checking
- Expansion order matters
- Termination checking more complex

**Priority:** HIGH - Important for dependent types

#### 2.3. Multiple Macro Types (Nim-style)

**Add different tools for different jobs:**

```auric
// 1. Simple template (inline substitution)
template unless(test, body) =
    if !test { body }

// 2. Full macro (AST transformation)
macro for = (v, lst, body) => {
    quote { map(($v) => $body, $lst) }
}

// 3. Tree-rewrite (optimization pass)
rewrite optimize(ast: Expr) = {
    App(Var("not"), [App(Var("not"), [x])]) -> x;
    App(Var("id"), [x]) -> x;
    _ -> ast
}
```

**Benefits:**
- ✅ Right tool for each job
- ✅ Simpler tools for simple cases
- ✅ Templates don't need totality

**Challenges:**
- More concepts to learn
- When to use which?

**Priority:** LOW - Nice but not essential

---

### Phase 3: Polish (Future)

#### 3.1. Better Error Messages

- Show expansion trace (which macro expanded to what)
- Type errors show both original and expanded code
- Suggest fixes for common mistakes

#### 3.2. Gensym (if needed)

```auric
let x = gensym("x")  // Generate unique symbol
```

- For unhygienic macros (if we allow them)
- For generating fresh names

#### 3.3. Macro Contracts

```auric
macro for : (Expr -> Expr)
    requires { is_valid_for_syntax(ast) }
    ensures { preserves_type(ast, result) }
= ...
```

- Pre/post conditions on macros
- Can prove properties about transformations

---

## Recommended Immediate Action Plan

### Step 1: Multi-Arg App/Lam (Week 1)

1. Update AST definition in `ast.py`:
   ```python
   @dataclass
   class App:
       fn: Exp
       args: List[Exp]  # Was: arg: Exp
   ```

2. Update parser to collect arguments
3. Update type checker
4. Update evaluator

**Expected result:**
```auric
// Can now write:
App(Var("f"), [x, y, z])
// Instead of:
App(App(App(Var("f"), x), y), z)
```

### Step 2: Quasiquote Syntax (Week 2)

1. Add `quote` keyword to lexer
2. Parser: inside `quote { }`, build AST instead of normal parse
3. Handle `$var` for splicing
4. Handle `$..vec` for variadic splicing

**Expected result:**
```auric
// Can now write:
quote { f($x, $y) }
// Instead of:
App(Var("f"), [x, y])
```

### Step 3: Update Examples (Week 3)

Rewrite all macro examples to use new syntax:

```auric
// Old (verbose):
macro for = (ast: Expr) => {
    ast => {
        App(Var("for"), [Var(v), lst, body]) -> {
            App(Var("map"), [Lam([v], body), lst])
        };
        _ -> unreachable
    }
}

// New (elegant):
macro for = (v: Record[u8], lst: Expr, body: Expr) => {
    quote { map(($v) => $body, $lst) }
}
```

### Step 4: Macroexpand Tool (Week 4)

Add debugging utilities:
```auric
macroexpand(expr)  // Show expanded form
print_ast(expr)    // Show AST structure
```

---

## Expected Elegance Level

**After Phase 1 (multi-arg + quasiquote):**

**Current Auric:**
```auric
macro optimize = (ast: Expr) => {
    ast => {
        App(App(Var("not"), App(Var("not"), x))) -> optimize(x);
        App(Var("id"), x) -> optimize(x);
        App(f, a) -> App(optimize(f), optimize(a));
        _ -> ast
    }
}
```

**Improved Auric:**
```auric
macro optimize = (ast: Expr) => {
    ast => {
        quote { not(not($x)) } -> optimize(x);
        quote { id($x) } -> optimize(x);
        quote { $f($..args) } -> quote { $(optimize(f))($..map(optimize, args)) };
        _ -> ast
    }
}
```

**Common Lisp (for comparison):**
```lisp
(defun optimize (ast)
  (match ast
    (`(not (not ,x)) (optimize x))
    (`(id ,x) (optimize x))
    (`(,f . ,args) `(,(optimize f) ,@(mapcar #'optimize args)))
    (_ ast)))
```

**Elegance comparison:**
- Lisp: 10/10 (baseline)
- Current Auric: 5/10
- Improved Auric: 9/10

**We get 90% of Lisp elegance with:**
- ✅ Type safety
- ✅ Totality
- ✅ Rust-like syntax
- ✅ Exhaustiveness checking

---

## Open Questions for Discussion

1. **Multi-arg App:** Should we support both curried and multi-arg? Or only multi-arg?

2. **Quote syntax:** Is `quote { }` good? Or prefer `` `{ }` `` (backtick)? Or `'{ }` (tick)?

3. **Splice syntax:** Is `$var` good? Or prefer `,var` (comma) or `~var` (tilde)?

4. **Pattern on syntax:** Worth the complexity? Or just use quasiquote?

5. **Type-aware macros:** Essential? Or can wait?

6. **Multiple macro types:** One unified system or multiple tools (template/macro/rewrite)?

---

## Summary

**Three changes make Auric macros as elegant as s-expressions:**

1. **Multi-arg App/Lam** - Flat structure
2. **Quasiquote syntax** - Clean templates
3. **Pattern matching** - Already have it!

**With these, we achieve:**
- S-expression elegance (Rhombus proof)
- Type safety (Scala 3 style)
- Totality (unique to Auric!)
- Rust-like syntax (no parens soup)

**Rhombus proved it's possible. Now Auric can do it better with totality.**
