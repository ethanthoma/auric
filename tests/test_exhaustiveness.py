#!/usr/bin/env python3
"""Tests for exhaustive pattern matching enforcement."""

import sys

sys.path.insert(0, "src")

import pytest

from auric.parser import parse
from auric.evaluator import type_of


def test_exhaustive_nat_pattern():
    """Exhaustive pattern match on Nat is accepted."""
    src = """
const is_zero = (n: Nat) -> Bool {
  zero -> true;
  succ x -> false;
}
"""
    sigs, defs = parse(src)
    # Should not raise
    type_of(src, {})


def test_exhaustive_bool_pattern():
    """Exhaustive pattern match on Bool is accepted."""
    src = """
const is_true = (b: Bool) -> Bool {
  true -> true;
  false -> false;
}
"""
    sigs, defs = parse(src)
    # Should not raise
    type_of(src, {})


def test_non_exhaustive_nat_missing_zero():
    """Non-exhaustive pattern match on Nat is rejected."""
    src = """
const is_succ = (n: Nat) -> Bool {
  succ x -> true;
}
"""
    with pytest.raises(TypeError, match="non-exhaustive.*missing.*zero"):
        type_of(src, {})


def test_non_exhaustive_nat_missing_succ():
    """Non-exhaustive pattern match on Nat is rejected."""
    src = """
const is_only_zero = (n: Nat) -> Bool {
  zero -> true;
}
"""
    with pytest.raises(TypeError, match="non-exhaustive.*missing.*succ"):
        type_of(src, {})


def test_non_exhaustive_bool_missing_one():
    """Non-exhaustive pattern match on Bool is rejected."""
    src = """
const always_true = (b: Bool) -> Bool {
  true -> true;
}
"""
    with pytest.raises(TypeError, match="non-exhaustive.*missing.*false"):
        type_of(src, {})


def test_exhaustive_with_wildcards():
    """Pattern match with wildcards counts as exhaustive."""
    src = """
const always_true = (n: Nat) -> Bool {
  zero -> true;
  _ -> false;
}
"""
    sigs, defs = parse(src)
    # Should not raise
    type_of(src, {})


def test_all_wildcards_is_exhaustive():
    """Single wildcard pattern is exhaustive."""
    src = """
const ignore_nat = (n: Nat) -> Bool {
  _ -> true;
}
"""
    sigs, defs = parse(src)
    # Should not raise
    type_of(src, {})
