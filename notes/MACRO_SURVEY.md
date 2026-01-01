# Survey of Macro Systems Across Languages

**Goal:** Understand different approaches to metaprogramming and identify ideas for Auric.

---

## Traditional S-Expression Macros

### Common Lisp
**Approach:** Untyped s-expressions with quasiquote

```lisp
(defmacro when (test &rest body)
  `(if ,test
       (progn ,@body)))
```

**Key features:**
- `` ` `` (backquote) for templates
- `,` (comma) for unquote
- `,@` (comma-at) for splicing
- Macroexpand for debugging
- Gensym for hygiene (manual)

**Power:** 10/10 - Can do anything
**Safety:** 3/10 - No hygiene, no types, runtime errors

### Scheme (syntax-case)
**Approach:** Hygienic macros with pattern matching

```scheme
(define-syntax when
  (syntax-rules ()
    [(when test body ...)
     (if test (begin body ...))]))
```

**Key features:**
- Pattern matching on syntax
- Automatic hygiene (no variable capture)
- `syntax-case` for complex macros
- Syntax objects (wrapped s-expressions)

**Power:** 9/10 - Very powerful, but hygiene adds complexity
**Safety:** 8/10 - Hygiene prevents most bugs

### Racket (syntax-parse)
**Approach:** Typed syntax with annotations

```racket
(define-syntax (when stx)
  (syntax-parse stx
    [(_ test:expr body:expr ...)
     #'(if test (begin body ...))]))
```

**Key features:**
- Syntax classes (`:expr`, `:id`, etc.)
- Pattern matching with types
- Excellent error messages
- `#lang` for embedded DSLs

**Power:** 10/10 - Most sophisticated Lisp macro system
**Safety:** 9/10 - Type checking + hygiene

---

## Token-Based Macros

### C Preprocessor
**Approach:** Text substitution before compilation

```c
#define MAX(a, b) ((a) > (b) ? (a) : (b))
```

**Key features:**
- Simple text replacement
- `##` for token pasting
- `#` for stringification
- No syntax awareness

**Power:** 3/10 - Very limited
**Safety:** 1/10 - Double evaluation, no hygiene

### Rust (macro_rules!)
**Approach:** Pattern matching on token trees

```rust
macro_rules! when {
    ($test:expr, $($body:expr),*) => {
        if $test {
            $($body)*
        }
    };
}
```

**Key features:**
- Pattern matching on token streams
- Fragment specifiers (`:expr`, `:ty`, `:ident`)
- Repetition with `$(...)*`
- Hygiene by default

**Power:** 7/10 - Powerful but limited to syntax
**Safety:** 9/10 - Hygienic + typed fragments

### Rust (Procedural Macros)
**Approach:** Functions on token streams (proc_macro)

```rust
#[proc_macro]
pub fn my_macro(input: TokenStream) -> TokenStream {
    // Parse input, generate output
    let ast = syn::parse(input).unwrap();
    // ...
    quote! { /* generated code */ }
}
```

**Key features:**
- Full Rust code for transformations
- `syn` for parsing, `quote` for generation
- Can call external tools
- Separate compilation

**Power:** 9/10 - Almost anything possible
**Safety:** 7/10 - Runtime errors in macro code

---

## Staged Metaprogramming

### MetaML / MetaOCaml
**Approach:** Explicit staging with brackets

```ocaml
let power n =
  .<fun x -> .~(
    let rec loop i acc =
      if i = 0 then acc
      else loop (i-1) .<.~acc *. x>.
    in loop n .<1.>
  )>.
```

**Key features:**
- `.<...>` for code quotation
- `.~` for code splicing
- Type-safe (quoted code is typed)
- Multi-stage computation

**Power:** 10/10 - Provably type-safe staging
**Safety:** 10/10 - Type preservation across stages

### Template Haskell
**Approach:** Quasiquotes with AST manipulation

```haskell
makeLens ''Point

-- Or manual:
addOne = [| \x -> x + 1 |]
```

**Key features:**
- `[| ... |]` for quotation
- `$( ... )` for splicing
- `''Type` for reifying types
- Runs at compile time

**Power:** 9/10 - Very powerful, but complex
**Safety:** 9/10 - Type-checked, but Template Haskell code can fail

---

## Compile-Time Execution

### Zig
**Approach:** Same language at comptime and runtime

```zig
fn fibonacci(n: u32) u32 {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

const fib_10 = comptime fibonacci(10); // Computed at compile time
```

**Key features:**
- `comptime` keyword marks compile-time execution
- Same syntax as runtime code
- Can call any function at comptime
- `@` builtins for metaprogramming

**Power:** 9/10 - Very powerful, simple model
**Safety:** 5/10 - No termination checking, can hang compiler

### Nim 🌟
**Approach:** Multiple metaprogramming tools for different use cases

```nim
# 1. Template - Simple substitution
template unless(cond, body: untyped): untyped =
  if not cond:
    body

# 2. Macro - Full AST manipulation
macro myMacro(arg: untyped): untyped =
  quote do:
    echo `arg`
    `arg` + 1

# 3. Tree-rewrite procs - Pattern match on AST
proc optimize(node: NimNode): NimNode =
  case node.kind
  of nnkCall:
    if node[0].strVal == "not" and node[1][0].strVal == "not":
      return node[1][1]  # not(not(x)) → x
  else:
    return node

# 4. Proc overloading on literals
proc foo(x: int): string = "runtime: " & $x
proc foo(x: static[int]): string = "compile-time: " & $x

# 5. Pragmas - Annotations
{.pragma: myPragma.}
proc bar() {.myPragma.} = discard
```

**Key features:**
- **5 different metaprogramming mechanisms** (right tool for each job)
- `template` for simple cases (like C macros, but hygienic)
- `macro` for complex AST transformation
- Tree-rewrite procs for AST pattern matching
- `static[T]` for compile-time known values
- Pragmas for annotations
- `quote do:` for building AST
- Can run arbitrary Nim at compile time

**Notable:** Shows value of having multiple metaprogramming primitives instead of one

**Power:** 10/10 - Extremely flexible, many tools
**Safety:** 4/10 - Easy to hang compiler, poor error messages

### Terra
**Approach:** Lua metaprogramming for low-level code

```lua
terra saxpy(a : float, X : &float, Y : &float)
    return a*X + Y
end

-- Metaprogram:
local function generateSaxpy(N)
    return terra(a : float, X : &float, Y : &float)
        var result : float[N]
        for i = 0,N do
            result[i] = a*X[i] + Y[i]
        end
        return result
    end
end
```

**Key features:**
- Lua for metaprogramming
- Terra for low-level code
- Staged compilation (Lua → Terra → LLVM)
- Quote/escape with `quote ... end` and `[expr]`

**Power:** 10/10 - Full Lua available
**Safety:** 6/10 - Lua is dynamic, Terra is static

---

## AST Transformation (Typed)

### Elixir
**Approach:** Quoted AST with pattern matching

```elixir
defmacro when(test, do: body) do
  quote do
    if unquote(test) do
      unquote(body)
    end
  end
end
```

**Key features:**
- `quote` builds AST
- `unquote` splices values
- AST is just tuples: `{:+, [], [1, 2]}`
- Pattern match on AST

**Power:** 9/10 - Very flexible
**Safety:** 7/10 - Dynamic but hygienic

### Julia
**Approach:** Expression macros with @

```julia
macro assert(ex)
    return :($ex ? nothing : throw(AssertionError($(string(ex)))))
end

@assert 1 + 1 == 2
```

**Key features:**
- `:( ... )` quotes expressions
- `$` interpolates
- Macros prefixed with `@`
- AST is Expr objects

**Power:** 9/10 - Full AST access
**Safety:** 6/10 - Runtime type errors possible

### Crystal
**Approach:** Typed macros with AST nodes

```crystal
macro debug(var)
  {{ puts "#{var} = " + var.stringify }}
end

debug(x + 1)  # Prints: x + 1 = <value>
```

**Key features:**
- `{{ }}` for macro code
- AST nodes have methods (`.stringify`, `.class_name`)
- Type information available
- Compile-time constants with `{% %}`

**Power:** 8/10 - Good but limited
**Safety:** 8/10 - Type-checked

---

## Unusual/Esoteric Approaches

### Red / Rebol
**Approach:** Dialects - every domain has its own syntax

```red
; CSS-like dialect
css: [
    body [
        background-color: white
        color: black
    ]
]

; Parse dialect
parse "hello world" [some [word! | space!]]
```

**Key features:**
- No macros - entire custom syntaxes
- `parse` is the metaprogramming tool
- Homoiconic (code is data)
- Extremely flexible

**Power:** 10/10 - Create entire languages
**Safety:** 3/10 - Very dynamic, few checks

### Factor
**Approach:** Parsing words (immediate mode)

```factor
: unless ( cond true-quot -- )
    swap [ ] [ call ] if ; inline

5 10 > [ "yes" ] [ "no" ] unless
```

**Key features:**
- Words can be `PARSING:` - run at compile time
- Quotations `[ ... ]` are first-class
- Stack-based, so no syntax needed
- Can parse arbitrary syntax

**Power:** 10/10 - Ultimate flexibility
**Safety:** 2/10 - Very easy to break

### Forth
**Approach:** Immediate words

```forth
: UNLESS POSTPONE IF POSTPONE NOT ; IMMEDIATE
```

**Key features:**
- `IMMEDIATE` makes words run at compile time
- `POSTPONE` delays execution
- No syntax, just words
- State machine compilation

**Power:** 10/10 - Lowest level possible
**Safety:** 1/10 - Nothing is checked

### Wren (No macros, but interesting)
**Approach:** Fiber-based metaprogramming

```wren
// No macros, but can manipulate execution
var fiber = Fiber.new {
    System.print("delayed")
}
// Run later
fiber.call()
```

**Key features:**
- No macros at all
- First-class functions + fibers
- Shows you can get far without macros

**Power:** 2/10 - No metaprogramming
**Safety:** 10/10 - No macro complexity

---

## Comparison Table

| Language | Approach | Power | Safety | Hygiene | Types | Notation |
|----------|----------|-------|--------|---------|-------|----------|
| Common Lisp | S-expr quasi | 10 | 3 | Manual | No | `` ` , ,@ `` |
| Scheme | Hygienic S-expr | 9 | 8 | Auto | No | `syntax-rules` |
| Racket | Typed syntax | 10 | 9 | Auto | Yes | `syntax-parse` |
| Rust (decl) | Token trees | 7 | 9 | Auto | Partial | `macro_rules!` |
| Rust (proc) | Token streams | 9 | 7 | Auto | Partial | `proc_macro` |
| MetaOCaml | Staging | 10 | 10 | N/A | Yes | `.<...>` `.~` |
| Template Haskell | Quasiquote | 9 | 9 | Auto | Yes | `[|...|]` `$()` |
| Zig | Comptime | 9 | 5 | Auto | Yes | `comptime` |
| Nim | AST macros | 10 | 4 | Partial | Partial | `quote do:` |
| Terra | Lua staging | 10 | 6 | N/A | Partial | Lua code |
| Elixir | Quote/unquote | 9 | 7 | Auto | No | `quote/unquote` |
| Julia | Expr macros | 9 | 6 | Auto | Partial | `:()` `$` `@` |
| Crystal | AST nodes | 8 | 8 | Auto | Yes | `{{ }}` |
| Red | Dialects | 10 | 3 | N/A | No | `parse` |
| Factor | Parsing words | 10 | 2 | Manual | No | Stack ops |
| C | Preprocessor | 3 | 1 | No | No | `#define` |
| **Auric (current)** | **Variants** | **8** | **9** | **Auto** | **Yes** | **Pattern match** |

---

## Key Insights

### What makes s-expressions elegant:

1. **Uniform structure** - Everything is the same shape (lists)
2. **Minimal notation** - Just `` ` , ,@ `` for templates
3. **Trivial to parse** - Already structured
4. **Easy to build/destruct** - Same operations everywhere

### What makes other systems powerful:

1. **Hygiene** (Scheme, Rust) - Prevent variable capture
2. **Types** (MetaOCaml, Racket) - Type-safe transformations
3. **Staging** (Terra, MetaOCaml) - Explicit evaluation phases
4. **Simplicity** (Zig) - Same language at comptime
5. **Dialects** (Red) - Custom syntax per domain

### What we're missing in Auric:

1. ❌ **Quasiquote syntax** - No clean template notation
2. ❌ **Multi-arg App** - Binary application is verbose
3. ❌ **Splicing** - No comma-at equivalent
4. ⚠️ **Macro debugging** - No macroexpand
5. ⚠️ **Hygiene** - Automatic but not controllable

### What we do well:

1. ✅ **Type safety** - Exhaustiveness checking on patterns
2. ✅ **Totality** - Termination guaranteed
3. ✅ **Unified syntax** - Same as runtime (like Zig)
4. ✅ **Hygiene** - Automatic (like Rust)
5. ✅ **Familiar** - Not s-expressions

---

## Recommendations for Auric

Based on this survey, I recommend:

### 1. Add Quasiquote Syntax (from Lisp/Elixir/Julia)

```auric
// Instead of:
App(App(Var("seq"), x), y)

// Write:
quote { seq($x, $y) }

// With splicing:
quote { f($..args) }
```

### 2. Multi-Argument App/Lam (from MetaOCaml/Terra)

```auric
// Change AST:
App(fn: Expr, args: Vec[Expr, n])

// Now match:
App(Var("f"), [x, y, z]) -> ...
```

### 3. Macro Debugging (from Lisp)

```auric
// Add macroexpand builtin:
macroexpand(quote { for x in list { body } })
// → Shows expanded AST
```

### 4. Staged Evaluation (from MetaOCaml)

```auric
// Already have this with macro vs runtime
// But could make it more explicit:
stage0 { ... }  // Compile-time
stage1 { ... }  // Runtime
```

### 5. Better Splicing (from Lisp/Rust)

```auric
// Handle variable-length sequences:
quote { f($..args) }
// → App(Var("f"), args)  // Spread into args vector
```

---

## Most Relevant Systems for Auric

**Top 5 to study:**

1. **Rhombus** ⭐ - **NON-S-EXPRESSION syntax with full Lisp macro power**
   - This is THE proof that it's possible
   - Entire OOP system built with macros
   - Pattern matching on non-S-expr syntax

2. **Scala 3** ⭐ - **Macros during type checking**
   - Can use type information in macros
   - Can influence types being inferred
   - Relevant to our dependent types goal

3. **MetaOCaml** - Type-safe staging, proves soundness
   - Multi-stage computation with types
   - Bracket/escape notation

4. **Lean 4** - Macros in dependent type theory
   - Syntax extensions
   - Can prove properties about macros

5. **Zig comptime** - Simplest unified model
   - Same language at comptime and runtime
   - No special macro syntax

**Key insight from Rhombus:**

```rhombus
// This is NOT s-expressions, but has s-expression power:
macro 'when $test: $body':
  'if $test: $body'
```

The secret: **Structured syntax with pattern matching**. You don't need parentheses, you need:
- Pattern matching on syntax trees
- Quasiquoting (templates)
- Hygiene

**Key insight from Scala 3:**

```scala
// Macros can use types:
inline def summon[T]: T =
  scala.compiletime.summonInline[T]
```

The secret: **Macros run during elaboration**, not before type checking. They can:
- Query types of expressions
- Generate different code based on types
- Influence type inference

This is EXACTLY what we want with dependent types!

**Honorable mentions:**

6. **Terra** - Shows how to separate meta-language from object-language
7. **Elixir** - Clean quote/unquote, pattern matching on AST
8. **Rust proc macros** - Industrial-strength macro system

---

## Additional Notable Systems

### Sweet.js (JavaScript)
**Approach:** Hygienic macros for JavaScript

```javascript
syntax when = function(ctx) {
  let test = ctx.next().value;
  let body = ctx.next().value;
  return #`if (${test}) { ${body} }`;
}

when (x > 0) { console.log("positive"); }
```

**Key features:**
- Pattern matching on syntax
- Hygienic by default
- `#` for template literals
- Works with existing JS

**Notable:** Shows macros can work in C-style syntax languages

### Scala 3 (inline + quotes)
**Approach:** Inline functions + quoted code

```scala
inline def assert(inline cond: Boolean): Unit =
  if !cond then throw AssertionError()

// Or with quotes:
def powerCode(n: Int): Expr[Double => Double] =
  '{ (x: Double) => ${ powerImpl('x, n) } }
```

**Key features:**
- `inline` for compile-time expansion
- `'{ }` for quotes
- `${ }` for splices
- Type-safe (Expr[T])

**Notable:** Type-safe macros in a mainstream language

### Haxe
**Approach:** Multiple macro types

```haxe
macro function when(cond, body) {
  return macro if ($cond) $body;
}

// Or build macros:
class MyBuilder {
  @:autoBuild(buildFields)
  interface Builder { }
}
```

**Key features:**
- Expression macros
- Build macros (for classes)
- Type macros
- Reification with `macro { }`

**Notable:** Multiple macro types for different purposes

### Dylan
**Approach:** Hygienic pattern-based macros

```dylan
define macro when
  { when (?test:expression) ?:body end }
    => { if (?test) ?body end }
end macro
```

**Key features:**
- Pattern-based like Scheme
- Hygienic
- Named pattern variables with `?`
- Auxiliary rules

**Notable:** Influenced Rust's macro_rules!

### Coconut (Python)
**Approach:** Compile-to-Python with pattern matching

```python
# Not exactly macros, but shows what's possible
match x:
    case (0, 0) -> "origin"
    case (x, 0) -> "x-axis"
    case (0, y) -> "y-axis"
```

**Notable:** Shows you can add syntax to Python (pre-3.10 match)

### Io
**Approach:** Message passing metaprogramming

```io
unless := method(condition, body,
  if(condition not, body)
)

unless(x > 0) then("negative")
```

**Key features:**
- Everything is messages
- Methods can access AST as messages
- `call message` gets the AST
- Extremely flexible

**Notable:** Message-passing gives Lisp-like power

### Nemerle
**Approach:** Typed macros with quasiquoting

```nemerle
macro when(cond, body) {
  <[ when ($cond) $body ]>
}
```

**Key features:**
- `<[ ]>` for quasiquotes
- `$` for splicing
- Type-safe
- Pattern matching on quoted code

**Notable:** Influenced C# (which has no macros!)

### Rhombus (Racket 2) 🌟
**Approach:** Non-S-expression syntax with Lisp-level macro power

```rhombus
// Custom syntax - not s-expressions!
macro 'when $test: $body':
  'if $test: $body'

// Entire OOP system built with macros:
class Point(x, y):
  method distance():
    math.sqrt(x*x + y*y)
// ^ This class syntax is ALL macros
```

**Key features:**
- **Non-S-expression syntax** (braces, indentation)
- Full Lisp macro power
- Pattern matching with `$` binding
- Entire language features built as macros
- `shrubbery` notation (tree structure with indentation)

**Notable:** **PROOF that you can have s-expression power without s-expression syntax!**

This is EXACTLY what Auric wants to achieve.

### Scala 3 (Inline Macros) 🌟
**Approach:** Macros during type checking/elaboration

```scala
inline def power(x: Double, inline n: Int): Double =
  inline n match
    case 0 => 1.0
    case 1 => x
    case _ => x * power(x, n - 1)

// Macro that uses type information:
inline def summon[T]: T =
  scala.compiletime.summonInline[T]
```

**Key features:**
- Runs **during type checking** (not before/after)
- Can **use type information** in macro
- Can **influence types** being checked
- Pattern matching in macros
- Quotes `'{ }` and splices `${ }`

**Notable:** Macros have access to types, can generate different code based on types.

Similar to Auric's goal with dependent types!

### Lean 4 (Metaprogramming)
**Approach:** Theorem prover with syntax macros

```lean
macro "unless " c:term " then " t:term : term =>
  `(if ¬$c then $t else ())

-- Custom syntax:
syntax "repeat " term "times" term : term
macro_rules
  | `(repeat $n times $body) =>
    `(for _ in [0:$n] do $body)
```

**Key features:**
- Syntax extensions
- Pattern matching on syntax
- Hygiene by default
- Can prove properties of macros
- Notation system for custom operators

**Notable:** Macros in a dependently-typed language with proofs

### Tcl (String Evaluation)
**Approach:** Everything is a string, eval with scope control

```tcl
proc unless {condition body} {
    if {![uplevel 1 expr $condition]} {
        uplevel 1 $body
    }
}

unless {$x > 0} {
    puts "negative"
}
```

**Key features:**
- Everything is strings
- `uplevel` evaluates in caller's scope
- Can manipulate code as strings
- Dynamic scope control

**Notable:** Shows string-based can achieve Lisp-like power

### Prolog (Syntactic Homoiconicity)
**Approach:** Syntax constructors = data constructors

```prolog
% f(X, Y) is both code and data:
transform(f(X, Y), g(X, Y)).

% Pattern match on syntax:
optimize(not(not(X)), X).
optimize(or(X, false), X).
```

**Key features:**
- Every syntactic form is also a data term
- Unification works on code
- No separate AST representation
- Meta-predicates manipulate code

**Notable:** Different form of homoiconicity - unification-based

---

## Synthesis: What Makes a Great Macro System?

Based on this survey, great macro systems have:

### 1. **Clean Template Syntax**
- Lisp: `` ` , ,@ ``
- Elixir: `quote/unquote`
- Julia: `:() $`
- Scala 3: `'{ } ${ }`

**Lesson:** Need syntax for "this is code" vs "this is a value to splice"

### 2. **Hygiene (Automatic)**
- Scheme, Rust, Elixir do this right
- Lisp makes you use `gensym` manually
- C has no hygiene at all

**Lesson:** Automatic hygiene is essential

### 3. **Type Safety**
- MetaOCaml: Full type safety across stages
- Racket: Syntax classes
- Scala 3: Expr[T]
- Crystal: Type info in macros

**Lesson:** Types catch bugs at compile time

### 4. **Pattern Matching**
- Scheme: `syntax-rules`
- Rust: Fragment specifiers
- Dylan: Named patterns
- Elixir: Match on AST tuples

**Lesson:** Pattern matching > manual traversal

### 5. **Simplicity**
- Zig: Just mark it `comptime`
- Sweet.js: JavaScript + macros
- Io: Message passing is enough

**Lesson:** Don't over-complicate; use existing language features

### 6. **Debugging**
- Lisp: `macroexpand`
- Racket: Syntax error messages
- Rust: `cargo expand`

**Lesson:** Must be able to see expanded code

---

## Concrete Proposal for Auric

Based on this survey, here's what Auric should adopt:

### ✅ Keep (Already Good)

1. **Variants for AST** - Like Elixir/Julia, but typed
2. **Pattern matching** - Like Scheme/Rust
3. **Hygiene** - Automatic like Rust
4. **Unified syntax** - Like Zig (comptime = runtime)
5. **Totality** - UNIQUE (no other language has this!)

### 🔧 Add (Missing Features)

1. **Multi-arg App/Lam** (from MetaOCaml)
   ```auric
   App(fn: Expr, args: Vec[Expr, n])
   ```

2. **Quasiquote syntax** (from Lisp/Elixir/Scala)
   ```auric
   quote { f($x, $..args) }
   // → App(Var("f"), [x, ..args])
   ```

3. **Macroexpand** (from Lisp)
   ```auric
   macroexpand(expr)  // Show expanded form
   ```

4. **Better splicing** (from Lisp's ,@)
   ```auric
   $..vec  // Splice vector into argument list
   ```

5. **AST pretty-printer** (from Rust's cargo expand)
   ```auric
   print_ast(expr)  // Show AST structure
   ```

### 🚫 Don't Add (Complexity)

1. ❌ **Multiple macro types** (Haxe) - One system is enough
2. ❌ **Unhygienic mode** (Common Lisp) - Always hygienic
3. ❌ **Token-level** (C preprocessor) - AST-level is better
4. ❌ **Separate macro language** (Template Haskell) - Unified is simpler
5. ❌ **Dialects** (Red) - Too complex for now

---

## Recommended Syntax (Rhombus-Inspired)

Combining the best ideas from **Rhombus**, **Scala 3**, and **Elixir**:

**Current (verbose - too low-level):**
```auric
macro for = (ast: Expr) => {
    ast => {
        App(App(App(Var("for"), Var(v)), lst), body) -> {
            App(App(Var("map"), Lam(v, body)), lst)
        };
        _ -> unreachable
    }
}
```

**Improved Option 1: Multi-arg + Quasiquote (Elixir-style)**
```auric
macro for = (v: Record[u8], lst: Expr, body: Expr) => {
    quote { map(($v) => $body, $lst) }
}
```

**Improved Option 2: Pattern on Syntax (Rhombus-style) ⭐**
```auric
// Match on SURFACE SYNTAX, not AST:
macro 'for $v in $lst { $body }' =>
  'map(($v) => $body, $lst)'

// Multiple patterns:
macro 'when $test { $body }' => 'if $test { $body }'
macro 'unless $test { $body }' => 'if !($test) { $body }'
```

**Improved Option 3: Hybrid (Pattern + AST access)**
```auric
// Pattern match on syntax, return AST:
macro expand = {
    'for $v in $lst { $body }' => {
        // Can manipulate AST here if needed:
        let optimized_body = optimize($body)
        quote { map(($v) => $optimized_body, $lst) }
    };

    'when $test { $body }' =>
        quote { if $test { $body } };

    _ => ast  // Fallthrough
}
```

**With Scala 3's type awareness:**
```auric
// Macro can query types during elaboration:
macro inline = (f: Expr) => {
    let f_type = type_of(f)  // Query type!
    f_type => {
        Arrow(_, _) -> inline_function(f);
        _ -> f  // Not a function, leave as-is
    }
}
```

This combines:
- ✅ **Rhombus**: Pattern match on surface syntax (not low-level AST)
- ✅ **Scala 3**: Type information during elaboration
- ✅ **Elixir**: Clean quasiquote with `quote`/`$`
- ✅ **Auric**: Type safety + totality + exhaustiveness
- ✅ **Elegance**: Almost as clean as Lisp

---

## Open Questions

1. **Should we support dialects like Red?** Custom syntax per domain?
2. **Do we need gensym?** Or is lexical scoping + hygiene enough?
3. **Should macros have access to type information?** (Like Crystal)
4. **Multi-stage computation?** Beyond just comptime vs runtime?
5. **Can users define new AST nodes?** Or is Expr fixed?
