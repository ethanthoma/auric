# Making a Language

This is a collection of scribbles on a fake language with more unified
semantics. The moral of this story is that Haskell is goated.

## Notes on Gleam and other syntaxes

I dont like that gleam uses the same syntax `{}` for three distinct semantic
purposes: defining code blocks (for functions and other expressions), pattern
matching in `case` statements, and defining the fields of a record.

Here is an idea, functions as matches:

First, take a some fn:

```gleam
fn main() {
    ...
}
```

then we can convert it into a syntax similar to odin's unified syntax for
identities:

```rs
main :: fn() {  
    ...
}
```

then we can convert this into simpliy a match expression:

```rs
main :: Nil {
    _ -> ...
}
```

part of the issue is that main will be evaluated greedily (in a non-lazy lang).

If we make the language lazy, then functions can act as lazy matches. We can
define our case statement from

```rust
case x: T {
    _ -> ...
}: S
```

to

```rust
(x: T) -> S {
    _ -> ...
}(x:)
```

now we can take some simple Gleam:

```gleam
pub fn main() -> #(Int, String) {
    let x = int.random(5)

    let result = case x {
        // Match specific values
        0 -> "Zero"
        1 -> "One"

        // Match any other value
        _ -> "Other"
    }

    #(x, result)
}
```

and rewrite it as:

```rs
pub main :: () -> #(Int, String) {
    let x = int.random(5)

    let result = case x {
        0 -> "Zero"
        1 -> "One"

        // Match any other value
        _ -> "Other"
    }

    #(x, result)
}
```

I will drop the double colon for a single colon type annotation and rewrite the
case:

```rust
pub main: fn () -> #(Int, String) {
    let x = int.random(5)

    let result = (x) -> {
        0 -> "Zero"
        1 -> "One"

        // Match any other value
        _ -> "Other"
    }(x)

    #(x, result)
}
```

Finally, I will allow implicit anonymous tuples for returns when comma separated
since it cannot be anything else:

```rust
pub main: fn () -> Int, String {
    let x = int.random(5)

    let result = (x) -> {
        0 -> "Zero"
        1 -> "One"

        // Match any other value
        _ -> "Other"
    }(x)

    x, result
}
```

and without annotations for fn:

```rust
pub main() -> Int, String {
    let x = int.random(5)

    let result = (x) -> {
        0 -> "Zero"
        1 -> "One"

        // Match any other value
        _ -> "Other"
    }(x)

    x, result
}
```

## My Language Syntax

It will be immutable (although maybe with regions?) and it will be expression
based.

### Identities, Bindings, and Functions

First, functions:

```rs
pub main: fn = () -> {
    ...
}
```

Breaking down the syntax we have the accessibility (`pub`), identity (`main`),
type of (`:`) identity (`fn`), binding operator (`=`), params (none), and
expression `{...}`. Top level bindings can include consts as well:

```rs
pub SOME_CONST: Int = 123
```

Technically, all top level bindings are constants as the language is immutable.

### Expressions and Matches

Expression blocks are denoted with `{}`. They are actually syntax sugar for
match statements:

```rs
{
    ...
}

(_) -> {
 _ -> ...
}(_)
```

This means we can match like so:

```rs
pub is_even: fn = (value: Int) -> {
    0 -> True
    1 -> False
    _ -> is_even(value - 2)
}
```

Matching is done on the parameters as an implicit tuple:

```rs
pub is_auth: fn = (username: String, password: String) -> {
    "admin", "root" -> True
    _ -> False
}
```

We can write matches in our "expressions" like so:

```rs
pub make_response: fn = (request: Request) -> {
    let is_auth = (username, password) -> {
        "admin", "root" -> True
        _ -> False
    }(request.username, request.password)

    Response(200, [], f"Authorized: {is_auth}")    
}
```

which is a bit verbose. What makes it delayed is the function syntax of
`() -> ...`. We can get around this by unwrapping:

```rs
pub make_response: fn = (request: Request) -> {
    let is_auth = request.username, request.password -> {
        "admin", "root" -> True
        _ -> False
    }

    Response(200, [], f"Authorized: {is_auth}")    
}
```

This may look weird but the laziness comes from `()` where `->` means mapping.
This makes functions a lazy mapping. You may then question why `{() -> ...}()`
unwraps it but you can think of it as opening and closing brackets. Prefix `()`
wraps and suffix `()` unwraps laziness.

### Types

#### Gleam Records Suck

First, Gleam records are kinda meh. A single variant record is super verbose:

```gleam
type Person {
    Person(name: String, age: Int, needs_glasses: Bool)
}
```

Flix kind of solves this:

```flix
enum Person(name: String, age: Int, needs_glasses: Bool)
```

which is arguably much nicer. Although Flix with unions are much worse (since
everything is prefixed with case). Gleam cannot do this since it uses the type
for generics. Flix uses `[]` for the polymorphism.

Another issue I have is that a singleton enum (as Flix calls it) is not much
different from tuples in Gleam. Worse yet, records can have unnamed fields,
meaning

```gleam
type Person = #(String, Int, Bool)

type Person {
    Person(String, Int, Bool)
}
```

are the same (especially at the JS level besides the constructor for
`instanceof`). The only REAL difference is that the record is distinct but the
tuple is not. There is no `distinct` in Gleam but if we had it, we could simply:

```rs
type Person = distinct #(String, Int, Bool)
```

Which is quite nice in my opinion. It also lets you create distinct primitives
which is awesome for type safety indexing. I am not a super fan of having to
write `distinct` though. Generally, if we binding a name, we probably want
distinct. So we we will assume so.

Furthermore, I actually prefer how Zig does it for their struct and tuple types.
The Zig structs have name parameters where their tuples do not but their syntax
is the same otherwise. So, our record types are:

```rs
Person: type = #(name: String, age: Int, needs_glasses: Bool)
```

However, this tuple syntax somewhat conflates with our thunkiness of `()`
syntax. Instead we will adopt the style of Zig more so:

```rs
Person: type = .{name: String, age: Int, needs_glasses: Bool}
// or
Person = type{name: String, age: Int, needs_glasses: Bool}
```

which, yes, mildly contends with expression syntax but I think its okay.

#### Zig Comptime for Generics

Gleam generics have two issues. One, they are quite limited compared to
something like Zig's. For example, to make sized vectors in Gleam, I wrote this:

```gleam
pub type One =
  fn() -> Nil

pub type Two =
  fn() -> fn() -> Nil

pub type Three =
  fn() -> fn() -> fn() -> Nil

pub opaque type Vector(f) {
  Vector(buffer: Buffer, get: fn(Int) -> Float)
}
```

The reason the types `One`, `Two`, and `Three` are all functions is for letting
me write a general accesor:

```gleam
pub fn x(vec: Vector(fn() -> f)) -> Float {
  vec.get(0)
}

pub fn y(vec: Vector(fn() -> fn() -> f)) -> Float {
  vec.get(1)
}

pub fn z(vec: Vector(fn() -> fn() -> fn() -> f)) -> Float {
  vec.get(2)
}
```

which was less than awesome. In Zig, you can simply do:

```zig
fn Vector(comptime size: usize) type {
    return struct {
        buffer: [size]i64,

        fn x(self: @This) -> i64 {
            return buffer[0];
        }

        ...
    };
}
```

there are ways to ensure `y` and `z` are defined only when `size >= 2` and `3`
respectively but I'm too lazy to write it out now.

Types in our language are simply functions that run during compile time. We can
modify the Gleam polymorphism to allow this:

```gleam
type Vector(size: Int) {
    Vector
}
```

Of course, this is not immediately useful. That's because Gleam tagged unions
are...very weird. First, you cannot access the tag, which is super annoying.
Second, the tag is actually the name of a function that produces the type.
Finally, if you think about what it does, all each variant does is turn the
input parameters into a distinct tuple. So we can actually define it like so:

```rs
Vector: fn = (size: Int, element_type: type) -> type {
    .{ buffer: Static_Array(size, element_type) }
}
```

we can drop the expression block (since it is equivalent):

```rs
Vector: fn = (size: Int, element_type: type) -> type{ buffer: Static_Array(size, element_type) }
```

We replace the `.` with `type` as `.` is inference for type anyways. We can use
this via:

```rs
set = (vec: Vector(n, t), index: Int, value: t) -> Vector(n, t) {
    let .{ buffer: } = vec
    let buffer = Static_Array.set(buffer, index, value)
    .{ buffer: }
}

Vec3f: alias = Vector(3, Float)
Vec16i: alias = Vector(16, Int)

let vec = Vec3f{} |> set(index: 0, value: 7.2)
```

#### Sets and Unions

Let's take some types with no definition:

```rs
Club: type = .{}
Diamonds: type = .{}
Hearts: type = .{}
Spades: type = .{}
```

These are identifiers with no value. We can make a set with these:

```rs
Suit: Set(type) = .{ 
    Club,
    Diamonds,
    Hearts,
    Spades,
}
```

and now we have an enum with compile time known tags. Awesome! Of course, this
is a bit verbose so lets allow inlining defintions. We can do this by making
definitions be initialized inside:

```rs
Suit: Set(type) = .{ 
    Club: type = .{},
    Diamonds: type = .{},
    Hearts: type = .{},
    Spades: type = .{},
}
```

We can use this for an union syntax:

```rs
Suit = Set(type){ 
    Student = .{String, Int},
    Teacher = .{String},
}
```

We can marry it with the polymorphism we introduced before:

```rs
Result: fn = (ok: type, err: type) -> Set(type){
    Ok: = .{ok}
    Err: = .{err}
}
```

(the curly braces are optional for expressions, they are just used for
matching).

Now we can create an error like so:

```rs
pub main = () -> Int, Result(String, Int) {
    let x = int.random(5)
    let result = x -> {
        0 -> Result.Ok("Zero")
        value -> Result.Err(value)
    }

    x, result
}
```

#### Naming

All types are capitalized and so are all functions that produce types. Types
that are multiple words will follow Odin's pattern: Word_Word_Word. That's it.

### Effects

Algebraic effects are super cool.

Flix uses a `\` to seperate return types and effects. We can use effects as a
way to mark function as pure, which means if we make a non-gc lang then we can
reap the benefits of value-lang.

Flix uses effects like so:

```flix
/// A pure function is annotated with `\ {}`.
def inc1(x: Int32): Int32 \ {} = x + 1

/// An impure function is annotated with `\ IO`.
def inc2(x: Int32): Int32 \ IO =
    println("x = ${x}");
    x + 1

def f(): Int32 \ IO =    // f is impure
    let r1 = inc1(123);   // pure
    let r2 = inc2(456);   // impure
    r1 + r2               // pure
```

Our language will look more like:

```rs
let AMOUNT: Int(32) = 1

pub let inc1: fn (x: Int(32)) -> Int(32) = x + AMOUNT

pub let inc2: fn (x: Int(32)) -> Int(32) with IO = {
    yield IO.println("{d}", .{x})
    x + AMOUNT
}

pub let f: fn () -> Int(32) with IO {
    let r1 = inc1(123)
    let r2 = inc2(456)
    r1 + r2
}
```

Flix handles the effects like so:

```flix
eff HourOfDay {
    def getCurrentHour(): Int32
}

def greeting(): String \ {HourOfDay} = 
    let h = HourOfDay.getCurrentHour();
    if (h <= 12) "Good morning"
    else if (h <= 18) "Good afternoon"
    else "Good evening"

def main(): Unit \ IO = 
    run {
        println(greeting())
    } with HourOfDay {
        def getCurrentHour(_, resume) = 
            let dt = LocalDateTime.now();
            resume(dt.getHour())
    }
```

Our lang looks like this:

```rs
let HourOfDay = effect{
    get_current_hour: = fn() -> Float(32)
}

let greeting: fn() -> String with HourOfDay {
    let h = yield HourOfDay.get_current_hour()
    h -> {
        h <= 12 -> "Good morning"
        h <= 18 -> "Good afternoon"
        _ -> "Good evening"
    } 
}

pub let main: fn() -> Nil with IO {
    use resume <- HourOfDay
    use <- HourOfDay.get_current_hour(
        () -> resume(LocalDateTime.now().getHour())
    )

    IO.println("{d}", .{greeting()})
}
```
