#!/usr/bin/env python3
"""Tests for pattern matching and let binding."""

import sys

sys.path.insert(0, "src")

from auric.ast import App, Case, Lam, Var
from auric.parser import _parse_pattern, parse, parse_expr
from auric.evaluator import eval_exp


def test_pattern_parsing_zero():
    """Test extracting constructor and bindings from zero."""
    ctor, binds = _parse_pattern("zero")
    assert ctor == "zero" and binds == []


def test_pattern_parsing_succ():
    """Test extracting constructor and bindings from succ pattern."""
    ctor, binds = _parse_pattern("succ x")
    assert ctor == "succ" and binds == ["x"]


def test_pattern_parsing_cons():
    """Test extracting constructor and bindings from cons pattern."""
    ctor, binds = _parse_pattern("cons h t")
    assert ctor == "cons" and binds == ["h", "t"]


def test_pattern_block_single_line():
    """Test parsing single-line pattern block."""
    expr = parse_expr("{ zero -> true; succ x -> false; }")
    assert isinstance(expr, Case)
    assert "zero" in expr.alts
    assert "succ" in expr.alts


def test_pattern_block_bindings():
    """Test extracting bound variables from pattern block."""
    expr = parse_expr("{ zero -> true; succ x -> false; }")
    zero_binds, _ = expr.alts["zero"]
    succ_binds, _ = expr.alts["succ"]
    assert zero_binds == []
    assert succ_binds == ["x"]


def test_function_with_pattern_matching():
    """Test parsing function with pattern matching body."""
    src = """
const is_zero = (n: Nat) -> Bool {
  zero -> true;
  succ x -> false;
}
"""
    sigs, defs = parse(src)
    is_zero_def = defs.get("is_zero")
    assert is_zero_def is not None
    assert isinstance(is_zero_def, Lam)
    assert is_zero_def.arg == "n"
    assert isinstance(is_zero_def.body, Case)
    assert is_zero_def.body.scr.name == "n"


def test_let_block_single_binding():
    """Test parsing let block with single binding."""
    expr = parse_expr("{ let x = zero; return x }")
    assert isinstance(expr, App)


def test_let_block_multiple_bindings():
    """Test parsing let block with multiple bindings."""
    expr = parse_expr("{ let x = zero; let y = succ(zero); return x }")
    assert isinstance(expr, App)


def test_let_block_binding_variable():
    """Test let binding preserves variable names."""
    expr = parse_expr("{ let x = y; return x }")
    assert isinstance(expr, App)


def test_let_binding_in_function():
    """Test let binding in function body."""
    src = """
const test_let = (n: Nat) -> Nat {
  let x = n;
  x;
}
"""
    sigs, defs = parse(src)
    test_let_def = defs.get("test_let")
    assert test_let_def is not None
    assert isinstance(test_let_def, Lam)
    assert test_let_def.arg == "n"


def test_evaluate_let_binding_with_function():
    """Test evaluating let binding in function."""
    from auric.memory import Heap, RefValue

    src = """
const id_let = (n: Nat) -> Nat {
  let x = n;
  return x;
}
"""
    sigs, defs = parse(src)
    id_let_def = defs.get("id_let")
    assert id_let_def is not None
    zero = Heap.alloc(("zero",))
    env = {}
    fn = eval_exp(id_let_def, env)
    result = fn.data(zero)
    assert isinstance(result, RefValue)
    assert result.data == ("zero",)


def test_multiline_let_block():
    """Test parsing multiline let block with trailing semicolon."""
    expr_str = """{ let x = zero;
  let y = succ(zero);
  return x;
}"""
    expr = parse_expr(expr_str)
    assert isinstance(expr, App)
