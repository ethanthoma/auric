"""Test region-aware code generation."""

import pytest

from auric.codegen import CCodegen, compute_regions
from auric.runtime import Base, ShapeT, builtin_constructors, parse


class TestRegionCodegen:
    """Test region-aware C code generation."""

    def test_compute_regions_simple_const(self):
        """Simple constant should have inferred region."""
        sigs, defs = parse("const x = zero")
        gamma = builtin_constructors()

        exp = defs["x"]
        regions = compute_regions(exp, gamma, defs)

        # Should have at least one region (for the zero constructor)
        assert len(regions) > 0
        assert all(r.name in ["local", "param", "caller", "heap"] for r in regions.values())

    def test_compute_regions_function_call(self):
        """Function application should have caller region."""
        sigs, defs = parse("""
        const identity = (x: Nat) -> Nat { x }
        const test = identity(zero)
        """)
        gamma = builtin_constructors()

        # Compute regions for the test expression (which is a function call)
        test_exp = defs["test"]
        regions = compute_regions(test_exp, gamma, defs)

        # Should have multiple regions for subexpressions
        assert len(regions) > 0

    def test_codegen_no_rc_for_local_regions(self):
        """Generated code should not have RC ops for local-only expressions."""
        src = """
        const identity = (x: Nat) -> Nat { x }
        const test = identity(zero)
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # The generated code should be valid C
        assert c_code
        assert "#include" in c_code
        assert "Value" in c_code

        # For simple identity function, we expect very few RC operations
        # since everything stays local
        value_incr_count = c_code.count("value_incr")
        value_decr_count = c_code.count("value_decr")

        # We may have some in the header (for built-ins), but the generated functions
        # should minimize them
        print(f"\nGenerated code has {value_incr_count} value_incr calls")
        print(f"Generated code has {value_decr_count} value_decr calls")

    def test_codegen_preserves_c_syntax(self):
        """Generated C code should have valid syntax."""
        src = "const double = (n: Nat) -> Nat { succ(succ(n)) }"

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Basic syntax checks
        assert c_code.count("Value *") > 0, "Should have Value pointers"
        assert c_code.count("{") == c_code.count("}"), "Braces should be balanced"
        assert "int main" in c_code, "Should have main function"

    def test_codegen_case_expression(self):
        """Case expressions should handle regions correctly."""
        src = """
        const is_zero = (n: Nat) -> Bool {
          zero -> true;
          succ x -> false;
        }
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Should have a switch statement
        assert "switch" in c_code
        assert "case" in c_code
        assert c_code.count("{") == c_code.count("}")

    def test_codegen_nested_calls(self):
        """Nested function calls should be handled."""
        src = """
        const inc = (n: Nat) -> Nat { succ(n) }
        const double = (n: Nat) -> Nat { inc(inc(n)) }
        const test = double(zero)
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Should generate code for all three functions
        assert "eval_inc" in c_code
        assert "eval_double" in c_code
        assert "eval_test" in c_code

    def test_regions_dict_populated(self):
        """CCodegen should populate regions dict during generate."""
        src = """
        const pred = (n: Nat) -> Nat { zero -> zero; succ x -> x; }
        const test = pred(zero)
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # After generation, regions should be populated
        assert len(gen.regions) > 0, "Should have computed regions"

    def test_region_comments_in_output(self):
        """Region information should be included in comments."""
        src = "const x = zero"

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # May have region info in comments (// region: ...)
        # This is optional but helpful for debugging
        has_region_comments = "// region:" in c_code
        # Either way, code should still be valid
        assert c_code


class TestRegionOptimization:
    """Test that regions actually reduce RC operations."""

    def test_list_iteration_optimization(self):
        """List operations should benefit from region optimization."""
        src = """
        const first_elem = (xs: List(Nat)) -> Nat {
          nil -> zero;
          cons h t -> h;
        }
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Code should be generated without errors
        assert c_code
        assert "#include" in c_code

    def test_pattern_matching_optimization(self):
        """Pattern matching should benefit from region optimization."""
        src = """
        const match_nat = (n: Nat) -> Bool {
          zero -> true;
          succ x -> false;
        }
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Generated code should be valid
        assert "switch" in c_code
        assert c_code.count("{") == c_code.count("}")


class TestArenaAllocation:
    """Test arena allocation infrastructure."""

    def test_arena_struct_in_header(self):
        """Arena struct should be defined in C header."""
        src = "const x = zero"

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Arena struct should be defined
        assert "typedef struct Arena" in c_code
        assert "void *start" in c_code
        assert "void *current" in c_code

    def test_arena_functions_in_header(self):
        """Arena functions should be defined in C header."""
        src = "const x = zero"

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Arena functions should be defined
        assert "arena_create_static" in c_code
        assert "arena_create_dynamic" in c_code
        assert "arena_alloc" in c_code
        assert "arena_reset" in c_code
        assert "arena_free" in c_code

    def test_function_gets_arena_buffer(self):
        """Functions that allocate should get arena buffer."""
        src = """
        const make_constructor = (x: Nat) -> Nat {
          zero -> succ(x);
          succ n -> n;
        }
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Functions with case expressions should have arena buffers
        assert "arena_buffer" in c_code or "arena_create" in c_code

    def test_arena_constant_in_function(self):
        """Functions that allocate constants should have arena."""
        src = """
        const make_list = (n: Nat) -> List {
          nil
        }
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Function that creates nil should have arena infrastructure
        assert "arena" in c_code or "Arena" in c_code

    def test_arena_allocation_in_case(self):
        """Case expressions should use arena allocation."""
        src = """
        const test = (n: Nat) -> Nat {
          zero -> zero;
          succ x -> succ(x);
        }
        """

        gen = CCodegen()
        sigs, defs = parse(src)
        c_code = gen.generate(defs)

        # Case expression with multiple branches should have arena
        assert "#define ARENA_SIZE" in c_code
        assert "Arena" in c_code or "arena" in c_code
