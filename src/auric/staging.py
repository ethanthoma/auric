"""Automatic staging: evaluate const definitions at compile-time.

This module implements "normalization by evaluation" - running code at compile-time
and converting results back to AST for inlining.
"""

from typing import Dict, Optional
from auric.ast import Exp, Var, App, Record
from auric.evaluator import eval_exp, builtin_values
from auric.memory import Heap, RefValue


def value_to_ast(value: RefValue) -> Optional[Exp]:
    """Convert a runtime value back to AST.

    This enables inlining of compile-time evaluated values.
    Returns None if the value can't be represented as AST.
    """
    # Get the data from the RefValue
    data = value.data

    # Handle tuples (constructor applications and records)
    if isinstance(data, tuple):
        if not data:
            return None

        tag = data[0]

        # Record: ("record", {field_name: RefValue})
        if tag == "record" and len(data) == 2:
            field_values = data[1]
            if not isinstance(field_values, dict):
                return None

            # Convert each field value back to AST
            field_asts = {}
            for field_name, field_value in field_values.items():
                field_ast = value_to_ast(field_value)
                if field_ast is None:
                    return None
                field_asts[field_name] = field_ast

            return Record(field_asts)

        # Nullary constructors: @zero, @true, @false, nil, etc.
        if len(data) == 1:
            return Var(tag)

        # Unary constructors: @succ(n), Some(x)
        if len(data) == 2:
            arg_ast = value_to_ast(data[1])
            if arg_ast is None:
                return None
            return App(Var(tag), arg_ast)

        # Binary constructors: cons(h, t), Pair(a, b)
        if len(data) == 3:
            arg1_ast = value_to_ast(data[1])
            arg2_ast = value_to_ast(data[2])
            if arg1_ast is None or arg2_ast is None:
                return None
            # cons(h, t) → (cons h) t
            return App(App(Var(tag), arg1_ast), arg2_ast)

    # Can't convert functions, effects, or other runtime values
    return None


def try_eval_at_comptime(expr: Exp, comptime_env: Dict[str, RefValue]) -> Optional[Exp]:
    """Try to evaluate an expression at compile-time and convert back to AST.

    If successful, returns the normalized AST for inlining.
    If evaluation fails or result can't be converted, returns None.
    """
    try:
        # Try to evaluate
        result = eval_exp(expr, comptime_env)

        # Convert result back to AST
        ast = value_to_ast(result)

        # Clean up
        Heap.drop(result)

        return ast
    except Exception as e:
        # Evaluation failed (runtime dependencies, unknown functions, etc.)
        # Uncomment for debugging:
        # print(f"DEBUG: Failed to evaluate at comptime: {e}")
        return None


def evaluate_consts_at_comptime(defs: Dict[str, Exp]) -> Dict[str, Exp]:
    """Evaluate const definitions at compile-time and inline results.

    This implements automatic staging:
    - Const values that can be fully evaluated are normalized
    - Subsequent consts can use these normalized values
    - Creates a seamless compile-time/runtime boundary

    Returns: Dictionary mapping names to potentially optimized AST
    """
    # Start with builtin values in the environment
    comptime_env = builtin_values()
    optimized_defs = {}
    comptime_count = 0

    for name, expr in defs.items():
        # Try to evaluate at compile-time
        normalized = try_eval_at_comptime(expr, comptime_env)

        if normalized is not None:
            # Successfully evaluated! Use normalized AST
            optimized_defs[name] = normalized
            comptime_count += 1

            # Add to environment for subsequent definitions
            # Re-evaluate to get the runtime value
            try:
                val = eval_exp(normalized, comptime_env)
                comptime_env[name] = val
            except:
                # If re-evaluation fails, just use original
                optimized_defs[name] = expr
        else:
            # Can't evaluate at compile-time, keep original
            optimized_defs[name] = expr

            # Try to evaluate anyway for environment
            # (might work at runtime with more context)
            try:
                val = eval_exp(expr, comptime_env)
                comptime_env[name] = val
            except:
                pass

    if comptime_count > 0:
        print(f"✓ Normalized {comptime_count} definitions at compile-time")

    return optimized_defs
