#!/usr/bin/env python3
"""Tests for C code generation."""

import subprocess
import sys
import tempfile

sys.path.insert(0, "src")

from auric.codegen import codegen_to_c


def test_codegen_simple_constants():
    """Test codegen for simple constants."""
    src = """
const x = zero
const y = true
"""
    c_code = codegen_to_c(src)
    assert "#include <stdint.h>" in c_code
    assert "Value *eval_x()" in c_code
    assert "Value *eval_y()" in c_code
    assert "make_zero()" in c_code
    assert "make_true()" in c_code


def test_codegen_case_expression():
    """Test codegen for case expressions."""
    src = """
const is_zero = (n: Nat) -> Bool {
  zero -> true;
  succ x -> false;
}
"""
    c_code = codegen_to_c(src)
    assert "switch" in c_code
    assert "case 0:" in c_code
    assert "case 1:" in c_code


def test_codegen_compiles():
    """Test that generated C code compiles with gcc."""
    import shutil

    src = """
const x = zero
const y = true
"""
    c_code = codegen_to_c(src)

    # Skip test if gcc is not available
    if shutil.which("gcc") is None:
        import pytest

        pytest.skip("gcc not available in environment")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
        f.write(c_code)
        c_file = f.name

    try:
        result = subprocess.run(["gcc", "-c", c_file, "-o", c_file + ".o"], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"
    finally:
        import os

        if os.path.exists(c_file):
            os.unlink(c_file)
        if os.path.exists(c_file + ".o"):
            os.unlink(c_file + ".o")
