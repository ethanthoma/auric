from auric import Env, elaborate, evaluate, type_of

code = """
nonNilHead xs =
  case xs of
    cons x _ -> x
"""

# constructors as pure tuple makers
env: Env = {
    "nil": ("nil",),
    "cons": lambda h, t: ("cons", h, t),
}

print("Type signatures:", type_of(code, env))

core = elaborate(code)
fn = evaluate(core, env)["nonNilHead"]

sample = env["cons"](42, env["nil"])
print("Result:", fn(sample))  # → 42
