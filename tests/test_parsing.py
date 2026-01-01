#!/usr/bin/env python3
"""Unit tests for the parser, focusing on the new C-style syntax."""

import sys

sys.path.insert(0, "src")

from auric.lexer import Buf, lex
from auric.parser import _atom, _expr, parse, parse_expr


def test_lex_simple():
    """Test basic tokenization."""
    tokens = lex("identity(Nat, zero)")
    expected = ["identity", "(", "Nat", ",", "zero", ")"]
    assert tokens == expected, f"Got {tokens}, expected {expected}"


def test_atom_type_name():
    """Test that _atom accepts type names."""
    b = Buf(lex("Nat"))
    exp = _atom(b)
    assert exp.name == "Nat", f"Expected Var('Nat'), got {exp}"


def test_atom_term_name():
    """Test that _atom accepts term names."""
    b = Buf(lex("zero"))
    exp = _atom(b)
    assert exp.name == "zero", f"Expected Var('zero'), got {exp}"


def test_parse_expr_type_application():
    """Test parsing f(Nat) as type application."""
    exp = parse_expr("identity(Nat)")
    assert str(type(exp).__name__) == "TyAppE", f"Expected TyAppE, got {type(exp).__name__}"


def test_parse_simple_function():
    """Test parsing a simple function definition."""
    source = "const id = (x: Nat) -> Nat { x }"
    sigs, defs = parse(source)
    assert "id" in sigs, f"Expected 'id' in signatures, got {sigs.keys()}"
    assert "id" in defs, f"Expected 'id' in definitions, got {defs.keys()}"


def test_parse_polymorphic_function():
    """Test parsing polymorphic function."""
    source = "const identity = (T: Type, x: T) -> T { x }"
    sigs, defs = parse(source)
    assert "identity" in sigs, f"Expected 'identity' in signatures"
    assert "identity" in defs, f"Expected 'identity' in definitions"
    sig_str = str(sigs["identity"])
    assert "Forall" in sig_str, f"Expected Forall in signature, got {sig_str}"


def test_parse_function_call():
    """Test parsing function call with type argument."""
    source = """const identity = (T: Type, x: T) -> T { x }
const test1 : Nat = identity(Nat, zero)"""
    sigs, defs = parse(source)
    assert "identity" in defs, "Expected identity function"
    assert "test1" in defs, "Expected test1 definition"
