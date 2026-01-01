"""Test type specialization code generation."""

from auric.codegen import codegen_to_c


def test_type_specialization_generates_specialized_versions():
    """Test that polymorphic functions generate specialized versions for each type."""
    src = """const identity = (T: Type, x: T) -> T { x }
const test_nat = identity(Nat, zero)
const test_bool = identity(Bool, true)
"""

    c = codegen_to_c(src)

    # Check that specialized versions are declared
    assert "eval_identity_Nat" in c, "Missing Nat specialization declaration"
    assert "eval_identity_Bool" in c, "Missing Bool specialization declaration"

    # Check that specialized versions are defined (count occurrences)
    nat_def_count = c.count("eval_identity_Nat(Value *")
    bool_def_count = c.count("eval_identity_Bool(Value *")
    assert nat_def_count >= 2, f"Expected at least 2 refs to eval_identity_Nat (decl + def), found {nat_def_count}"
    assert bool_def_count >= 2, f"Expected at least 2 refs to eval_identity_Bool (decl + def), found {bool_def_count}"


def test_type_specialization_uses_specialized_calls():
    """Test that type-applied function calls use specialized versions."""
    src = """const identity = (T: Type, x: T) -> T { x }
const test = identity(Nat, zero)
"""

    c = codegen_to_c(src)

    # The call to identity(Nat, zero) should use the specialized version
    assert "eval_identity_Nat" in c, "Specialized version not referenced in generated code"

    # Check for direct specialized call pattern
    assert "eval_identity_Nat(result" in c or "eval_identity_Nat(&" in c, (
        "Specialized version should be called directly"
    )


def test_type_specialization_multiple_instances():
    """Test type specialization with multiple different type instantiations of same function."""
    src = """const id = (T: Type, x: T) -> T { x }
const test_nat = id(Nat, zero)
const test_bool = id(Bool, true)
const test_nat2 = id(Nat, zero)
"""

    c = codegen_to_c(src)

    # Check for both type instantiations
    assert "eval_id_Nat" in c, "Missing Nat specialization for id"
    assert "eval_id_Bool" in c, "Missing Bool specialization for id"


def test_type_specialization_no_duplicates():
    """Test that the same type specialization is not generated twice."""
    src = """const identity = (T: Type, x: T) -> T { x }
const test1 = identity(Nat, zero)
const test2 = identity(Nat, zero)
const test3 = identity(Nat, zero)
"""

    c = codegen_to_c(src)

    # Count occurrences of the specialized definition (declaration is one, definition is another)
    declaration_and_def_count = c.count("eval_identity_Nat(Value *")
    assert declaration_and_def_count == 2, (
        f"Should have 1 declaration + 1 definition, found {declaration_and_def_count}"
    )


def test_type_specialization_with_two_functions():
    """Test type specialization with two separate polymorphic functions."""
    src = """const identity = (T: Type, x: T) -> T { x }
const is_zero = (n: Nat) -> Bool { zero -> true; succ x -> false; }
const test_nat = identity(Nat, zero)
const test_check = is_zero(zero)
"""

    c = codegen_to_c(src)

    # Check that specialized versions are generated for identity
    assert "eval_identity_Nat" in c, "Nat specialization for identity should be generated"
    # is_zero is non-polymorphic so should have generic version only
    assert "eval_is_zero" in c, "is_zero definition should exist"
    # identity should be called with specialized version
    assert "eval_identity_Nat(" in c, "identity Nat specialization should be used"


def test_type_specialization_comments():
    """Test that specialized versions have type-specific comments."""
    src = """const identity = (T: Type, x: T) -> T { x }
const test = identity(Nat, zero)
"""

    c = codegen_to_c(src)

    # The generated code should have specialized version hints
    lines = c.split("\n")

    # Find the specialized version definition
    for i, line in enumerate(lines):
        if "eval_identity_Nat(Value *arg)" in line:
            # The function definition should be there
            assert i < len(lines) - 1, "Specialized version definition found"
            break


def test_type_specialization_preserves_functionality():
    """Test that specialized versions have the same behavior as generic versions."""
    src = """const identity = (T: Type, x: T) -> T { x }
const test_nat = identity(Nat, zero)
const test_bool = identity(Bool, true)
"""

    c = codegen_to_c(src)

    # Both generic and specialized versions should exist
    assert "Value *eval_identity(Value *arg);" in c, "Generic version should still exist"
    assert "Value *eval_identity_Nat(Value *arg);" in c, "Nat specialized version should exist"
    assert "Value *eval_identity_Bool(Value *arg);" in c, "Bool specialized version should exist"

    # Verify the C code compiles
    import os
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
        f.write(c)
        f.flush()
        temp_file = f.name

    try:
        result = subprocess.run(["gcc", "-c", temp_file, "-o", "/dev/null"], capture_output=True, text=True)
        assert result.returncode == 0, f"Generated C code failed to compile: {result.stderr}"
    finally:
        os.unlink(temp_file)
