"""Runtime evaluation for Auric."""

from __future__ import annotations

import random as py_random
import time
from typing import Any, Dict

from auric.ast import (
    App,
    Base,
    Case,
    Const,
    DepApp,
    Exp,
    FieldAccess,
    ForallIdx,
    Handle,
    IdxSucc,
    IdxVar,
    IdxZero,
    If,
    Lam,
    Let,
    MacroDef,
    Perform,
    Record,
    Seq,
    ShapeT,
    TyAbs,
    TyAppE,
    TyVar,
    Type,
    Var,
)
from auric.memory import Heap, RefValue
from auric.parser import parse
from auric.type_checker import synth

Env = Dict[str, Any]


def eval_exp(e: Exp, env: Dict[str, RefValue]) -> RefValue:
    """Evaluate expression with reference counting."""
    if isinstance(e, Var):
        return Heap.clone(env[e.name])

    if isinstance(e, Lam):
        # Create nested closures for multi-arg lambda (supports partial application)
        def make_closure(params: List[str], body: Exp, captured_env: Env):
            if not params:
                return eval_exp(body, captured_env)
            param = params[0]
            remaining = params[1:]
            def closure(arg: RefValue) -> RefValue:
                new_env = {**captured_env, param: arg}
                if remaining:
                    return Heap.alloc(make_closure(remaining, body, new_env))
                else:
                    return eval_exp(body, new_env)
            return closure

        return Heap.alloc(make_closure(e.params, e.body, env))

    if isinstance(e, TyAbs):

        def ty_closure(_ty):
            return eval_exp(e.body, env)

        return Heap.alloc(ty_closure)

    if isinstance(e, App):
        # Apply multiple arguments in sequence
        fn = eval_exp(e.fn, env)
        for arg_expr in e.args:
            arg = eval_exp(arg_expr, env)
            result = fn.data(arg)
            Heap.drop(fn)
            fn = result
        return fn

    if isinstance(e, TyAppE):
        fn = eval_exp(e.fn, env)
        result = fn.data(e.arg_ty)
        Heap.drop(fn)
        return result

    if isinstance(e, Case):
        scr = eval_exp(e.scr, env)
        tag, *flds = scr.data
        names, body = e.alts[tag]

        new_env = env.copy()
        for n, v in zip(names, flds):
            if n != "_":
                new_env[n] = Heap.clone(v)

        result = eval_exp(body, new_env)
        Heap.drop(scr)

        return result

    if isinstance(e, Perform):
        # Perform an effect - builtin effects are resolved via environment
        arg = eval_exp(e.args, env)

        # Lookup the effect in environment
        if e.effect_name in env:
            effect_fn = env[e.effect_name]
            result = effect_fn.data(arg)
            Heap.drop(arg)
            return result

        raise NameError(f"Effect '{e.effect_name}' not handled")

    if isinstance(e, Handle):
        # Handle effects in an expression
        result = eval_exp(e.body, env)
        return result

    if isinstance(e, Record):
        # Evaluate record literal: .{ x = 1, y = 2 }
        # Store as a dictionary
        field_values = {}
        for field_name, field_expr in e.fields.items():
            field_values[field_name] = eval_exp(field_expr, env)
        return Heap.alloc(("record", field_values))

    if isinstance(e, FieldAccess):
        # Evaluate field access: rec.x
        record = eval_exp(e.record, env)
        if not isinstance(record.data, tuple) or record.data[0] != "record":
            raise TypeError(f"Cannot access field of non-record value: {record.data}")
        field_values = record.data[1]
        if e.field not in field_values:
            raise KeyError(f"Field {e.field} not found in record")
        result = Heap.clone(field_values[e.field])
        Heap.drop(record)
        return result

    # Constant literals (int, float, char, bool)
    if isinstance(e, Const):
        # Extract type suffix from ShapeT(Base(suffix))
        if isinstance(e.ty, ShapeT) and isinstance(e.ty.shape, Base):
            type_suffix = e.ty.shape.name
            # Handle different value types
            if isinstance(e.value, bool):
                # Boolean literals: @true/@false
                return Heap.alloc(("@true",) if e.value else ("@false",))
            elif isinstance(e.value, str):
                # Character literals (stored as u8 value)
                return Heap.alloc(("int", ord(e.value), type_suffix))
            elif isinstance(e.value, float):
                # Float literals
                return Heap.alloc(("float", e.value, type_suffix))
            elif isinstance(e.value, int):
                # Integer literals
                return Heap.alloc(("int", e.value, type_suffix))
        raise ValueError(f"Invalid Const node: {e}")

    # If expression
    if isinstance(e, If):
        cond = eval_exp(e.cond, env)
        # Evaluate condition - should be @true or @false
        # Check if it's a constructor tuple (tag, fields...)
        if isinstance(cond.data, tuple) and len(cond.data) > 0:
            tag = cond.data[0]
            is_true = tag == "@true"
        elif cond.data == "@true":
            is_true = True
        else:
            is_true = False

        if is_true:
            result = eval_exp(e.then_branch, env)
        else:
            result = eval_exp(e.else_branch, env)
        Heap.drop(cond)
        return result

    # Let binding: all bindings are recursive by default
    if isinstance(e, Let):
        # Evaluate in an environment where the name is bound to a placeholder
        # This allows self-reference (recursion)
        placeholder = Heap.alloc(("rec_placeholder", e.name))
        new_env = {**env, e.name: placeholder}
        val = eval_exp(e.value, new_env)

        # Replace the placeholder with the actual value
        Heap.drop(placeholder)
        new_env[e.name] = val

        # Evaluate body
        result = eval_exp(e.body, new_env)
        return result

    # Sequence expression
    if isinstance(e, Seq):
        result = None
        for expr in e.exprs:
            if result is not None:
                Heap.drop(result)
            result = eval_exp(expr, env)
        return result if result is not None else Heap.alloc(("unit",))

    # Macro definitions are not evaluated (handled at expansion time)
    if isinstance(e, MacroDef):
        return Heap.alloc(("macro", e.name))

    raise TypeError(f"cannot evaluate {type(e).__name__}")


def builtin_constructors() -> Dict[str, Type]:
    """Return types for built-in data constructors and effects."""
    from auric.ast import Arrow, Base, Forall, ShapeT, Top

    return {
        # Nat constructors
        "@zero": ShapeT(Base("@Nat")),
        "@succ": Arrow(ShapeT(Base("@Nat")), ShapeT(Base("@Nat"))),
        # Bool constructors
        "@true": ShapeT(Base("@Bool")),
        "@false": ShapeT(Base("@Bool")),
        # Vec is the only collection type - use record literals
        # Use record literals: .{ } for empty, .{ _0 = x, _1 = y } for vec
        # Builtin effects
        "@Print": Arrow(ShapeT(Top()), ShapeT(Base("@Unit"))),
        "@Read": Arrow(ShapeT(Base("@Unit")), ShapeT(Top())),
        "@Sleep": Arrow(ShapeT(Base("@Nat")), ShapeT(Base("@Unit"))),
        "@Random": Arrow(ShapeT(Base("@Nat")), ShapeT(Base("@Nat"))),
        # Runtime utilities
        "@seq": Arrow(ShapeT(Top()), Arrow(ShapeT(Top()), ShapeT(Top()))),
        "@fold": Arrow(ShapeT(Top()), Arrow(ShapeT(Top()), Arrow(ShapeT(Top()), ShapeT(Top())))),
    }


def builtin_values() -> Dict[str, RefValue]:
    """Evaluation-time values for built-in constructors and effects."""

    def print_effect(s_val):
        """Print effect - outputs to stdout"""
        if isinstance(s_val, RefValue):
            s = s_val.data
        else:
            s = s_val
        print(s, end="")
        return Heap.alloc(("@unit",))

    def read_effect(_val):
        """Read effect - reads from stdin"""
        try:
            line = input()
            return Heap.alloc(line)
        except EOFError:
            return Heap.alloc("")

    def sleep_effect(ms_val):
        """Sleep effect - pauses execution"""
        if isinstance(ms_val, RefValue):
            ms_data = ms_val.data
        else:
            ms_data = ms_val

        # Extract integer from Nat representation
        if isinstance(ms_data, tuple):
            ms_num = 0
            current = ms_data
            while isinstance(current, tuple) and current[0] == "@succ":
                ms_num += 1
                current = current[1] if len(current) > 1 else None
        else:
            ms_num = int(ms_data)

        time.sleep(ms_num / 1000.0)
        return Heap.alloc(("@unit",))

    def random_effect(max_val):
        """Random effect - generates random number"""
        if isinstance(max_val, RefValue):
            max_num_data = max_val.data
        else:
            max_num_data = max_val

        # Extract integer from Nat representation
        if isinstance(max_num_data, tuple):
            max_num = 0
            current = max_num_data
            while isinstance(current, tuple) and current[0] == "@succ":
                max_num += 1
                current = current[1] if len(current) > 1 else None
        else:
            max_num = int(max_num_data)

        # Generate random number
        result = py_random.randint(0, max(0, max_num - 1))
        # Convert back to Nat
        nat_result = ("@zero",)
        for _ in range(result):
            nat_result = ("@succ", nat_result)
        return Heap.alloc(nat_result)

    def seq_effect(a_val):
        """Sequence effect - evaluate a, then return b"""
        # Force evaluation of a (for side effects)
        if isinstance(a_val, RefValue):
            _ = a_val.data
        return Heap.alloc(lambda b_val: b_val)

    def fold_effect(record_val):
        """Fold over a record's fields with a function (acc, field_value) => acc'"""
        def with_init(init_val):
            def with_fn(fn_val):
                # Extract record fields
                if isinstance(record_val, RefValue):
                    record_data = record_val.data
                else:
                    record_data = record_val

                # Start with init accumulator
                acc = init_val

                # If it's a record, fold over its fields
                if isinstance(record_data, tuple) and record_data[0] == "record":
                    fields = record_data[1]
                    for field_name, field_val in fields.items():
                        # Apply fn to (acc, field_value)
                        # fn_val should be a callable (lambda)
                        if isinstance(fn_val, RefValue):
                            fn = fn_val.data
                        else:
                            fn = fn_val

                        # Call fn(acc) to get partial application
                        if callable(fn):
                            partial_ref = fn(acc)
                            # Dereference if needed
                            if isinstance(partial_ref, RefValue):
                                partial = partial_ref.data
                            else:
                                partial = partial_ref

                            # Call partial(field_val) to get new accumulator
                            if callable(partial):
                                result_ref = partial(Heap.alloc(field_val))
                                # Dereference the result
                                if isinstance(result_ref, RefValue):
                                    acc = result_ref
                                else:
                                    acc = Heap.alloc(result_ref)
                            else:
                                acc = partial_ref
                        else:
                            acc = fn_val

                return acc
            return Heap.alloc(with_fn)
        return Heap.alloc(with_init)

    return {
        "@zero": Heap.alloc(("@zero",)),
        "@succ": Heap.alloc(lambda n: Heap.alloc(("@succ", n))),
        "@true": Heap.alloc(("@true",)),
        "@false": Heap.alloc(("@false",)),
        # Vec is record-based - use .{ } syntax
        # Builtin effects
        "@Print": Heap.alloc(print_effect),
        "@Read": Heap.alloc(read_effect),
        "@Sleep": Heap.alloc(sleep_effect),
        "@Random": Heap.alloc(random_effect),
        # Runtime utilities
        "@seq": Heap.alloc(seq_effect),
        "@fold": Heap.alloc(fold_effect),
    }


def type_of(src: str, _env: Env) -> Dict[str, Type]:
    """Type check source code and return types for all definitions."""
    from auric.macros import expand_macros
    from auric.type_checker import check

    sigs, defs = parse(src)

    # MACRO EXPANSION: Expand all macros before type checking
    expanded_defs = {name: expand_macros(expr) for name, expr in defs.items()}

    gamma = builtin_constructors()  # Start with built-in constructors
    gamma.update(sigs)  # Add user-defined signatures

    for n, e in expanded_defs.items():
        if n in sigs:
            check(gamma, e, sigs[n])
            gamma[n] = sigs[n]
        else:
            gamma[n] = synth(gamma, e)
    return {k: gamma[k] for k in expanded_defs}


def unwrap_value(v: RefValue) -> Any:
    """Convert RefValue back to displayable form."""
    if isinstance(v.data, tuple):
        tag, *fields = v.data
        if not fields:
            return tag
        return (tag, *[unwrap_value(f) if isinstance(f, RefValue) else f for f in fields])
    return v.data


def evaluate(core: Dict[str, Exp], env: Env) -> Dict[str, Any]:
    """Evaluate definitions in order with built-in constructors available."""
    env.update(builtin_values())
    result = {}

    for k, v in core.items():
        result[k] = eval_exp(v, env)
        env[k] = result[k]

    return {k: unwrap_value(v) if isinstance(v, RefValue) else v for k, v in result.items()}
