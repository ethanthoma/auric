from auric import Env, elaborate, evaluate, type_of

code = """
non_nil_head : ∀a. List a -> a
non_nil_head[a] xs =
  case xs of
    cons x _ -> x
"""

env: Env = {
    "nil": ("nil",),
    "cons": lambda h, t: ("cons", h, t),
}

core = elaborate(code)
fn = evaluate(core, env)["non_nil_head"]
print(fn)

sample = env["cons"](42, env["nil"])
# retuned function is polymorphic over type
print(fn(None)(sample))  # 42
