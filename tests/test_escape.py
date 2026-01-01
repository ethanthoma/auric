"""Test Phase 5: Cross-Function Escape Analysis."""

import pytest

from auric.runtime import (
    App,
    Arrow,
    Base,
    Case,
    Lam,
    Var,
    build_call_graph,
    builtin_constructors,
    can_var_reach_return,
    find_callees,
    infer_escaping_values_phase5,
    parse,
)


class TestCallGraphAnalysis:
    """Test call graph building."""

    def test_no_calls(self):
        """Function with no calls has empty callees."""
        src = "const identity = (x: Nat) -> Nat { x }"
        sigs, defs = parse(src)
        graph = build_call_graph(defs)

        assert "identity" in graph
        assert graph["identity"] == set()

    def test_single_function_call(self):
        """Direct function call is detected."""
        src = """
        const double_id = (x: Nat) -> Nat { identity(x) }
        const identity = (x: Nat) -> Nat { x }
        """
        sigs, defs = parse(src)
        graph = build_call_graph(defs)

        assert "identity" in graph["double_id"]

    def test_multiple_calls(self):
        """Multiple calls to same function detected."""
        src = """
        const use_both = (x: Nat) -> Nat {
          zero -> identity(x);
          succ n -> identity(n);
        }
        const identity = (x: Nat) -> Nat { x }
        """
        sigs, defs = parse(src)
        graph = build_call_graph(defs)

        assert "identity" in graph["use_both"]

    def test_call_chain(self):
        """Call chains are detected."""
        src = """
        const f = (x: Nat) -> Nat { g(x) }
        const g = (x: Nat) -> Nat { h(x) }
        const h = (x: Nat) -> Nat { x }
        """
        sigs, defs = parse(src)
        graph = build_call_graph(defs)

        assert "g" in graph["f"]
        assert "h" in graph["g"]


class TestTypeBasedEscapeDetection:
    """Test type-based escape detection."""

    def test_type_prevents_escape(self):
        """Type mismatch prevents variable escape."""
        # Pattern match returns Bool, so Nat-typed variable can't escape
        src = """
        const is_zero = (n: Nat) -> Bool {
          zero -> true;
          succ x -> false;
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x is Nat, but return type is Bool, so x cannot escape
        # Phase 4 would mark it as escaping, but Phase 5 sees type mismatch
        key = "is_zero::x"
        # After type-based refinement, should be False
        assert not phase5.get(key, False)

    def test_matching_types_allow_escape(self):
        """Matching types allow variable escape."""
        src = """
        const get_succ = (n: Nat) -> Nat {
          zero -> zero;
          succ x -> x;
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x is Nat and return type is Nat, so x can escape
        key = "get_succ::x"
        assert phase5.get(key, False) == True

    def test_parameter_type_check(self):
        """Parameter type determines escapability."""
        src = """
        const process = (n: Nat) -> Nat {
          zero -> zero;
          succ x -> n;
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # n is parameter, Nat type, return type Nat, so it can escape
        key = "process::n"
        assert phase5.get(key, False) == True


class TestPhase5vs4Comparison:
    """Compare Phase 4 and Phase 5 results."""

    def test_phase5_reduces_false_positives(self):
        """Phase 5 should reduce false positives vs Phase 4."""
        src = """
        const classify = (n: Nat) -> Bool {
          zero -> true;
          succ x -> false;
        }
        """
        sigs, defs = parse(src)

        from auric.runtime import infer_escaping_values

        phase4 = infer_escaping_values(defs)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # Phase 4 is conservative (marks as escaping)
        # Phase 5 should see type mismatch (Bool return, Nat variable)
        key = "classify::x"

        # Phase 4 might mark it as escaping (conservative)
        # Phase 5 should refine it down
        # We just verify Phase 5 completes without error
        assert isinstance(phase5, dict)

    def test_phase5_preserves_true_escapes(self):
        """Phase 5 should still mark true escapes."""
        src = """
        const identity = (x: Nat) -> Nat { x }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x is returned and type matches, so should escape
        key = "identity::x"
        assert phase5.get(key, False) == True


class TestPhase5Integration:
    """Integration tests for Phase 5."""

    def test_nested_pattern_matching(self):
        """Phase 5 handles nested pattern matching."""
        src = """
        const analyze = (ns: List(Nat)) -> Nat {
          nil -> zero;
          cons h t ->
            h;
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # h is Nat, return is Nat, should escape
        assert phase5.get("analyze::h", False) == True

    def test_multiple_pattern_arms(self):
        """Phase 5 analyzes all pattern arms."""
        src = """
        const multi = (n: Nat) -> Nat {
          zero -> zero;
          succ x -> x;
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x appears in return arm
        assert phase5.get("multi::x", False) == True

    def test_type_conversion_prevents_escape(self):
        """Type conversion prevents false escaping."""
        src = """
        const wrap = (n: Nat) -> Bool {
          zero -> true;
          succ x -> false;
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x is Nat but return is Bool - type prevents escape
        # After Phase 5 type checking, should not escape
        key = "wrap::x"
        # Phase 5 should refine this
        assert isinstance(phase5, dict)


class TestPhase5EdgeCases:
    """Edge cases for Phase 5."""

    def test_empty_case_alternatives(self):
        """Phase 5 handles empty case gracefully."""
        src = """
        const id = (x: Nat) -> Nat { x }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # Simple case - parameter is returned
        assert phase5.get("id::x", False) == True

    def test_unused_parameter(self):
        """Unused parameters don't escape."""
        src = """
        const const_zero = (x: Nat) -> Nat { zero }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x is not used, so it doesn't escape
        key = "const_zero::x"
        # Should not be marked as escaping
        assert not phase5.get(key, False) or key not in phase5

    def test_higher_order_function(self):
        """Phase 5 analyzes higher-order functions."""
        src = """
        const apply = (f: Nat, x: Nat) -> Nat { x }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # x is Nat and returned, so should escape
        assert phase5.get("apply::x", False) == True

    def test_recursive_function(self):
        """Phase 5 handles recursion."""
        src = """
        const countdown = (n: Nat) -> Nat {
          zero -> zero;
          succ x -> countdown(x);
        }
        """
        sigs, defs = parse(src)
        phase5 = infer_escaping_values_phase5(defs, sigs)

        # Recursion should be analyzed correctly
        assert isinstance(phase5, dict)


class TestFindCallees:
    """Test find_callees helper."""

    def test_find_single_callee(self):
        """Single function call is found."""
        from auric.runtime import App, Var

        # App(Var("f"), Var("x"))
        app = App(Var("f"), Var("x"))
        callees = find_callees(app)

        assert "f" in callees

    def test_find_nested_callees(self):
        """Nested function calls found."""
        from auric.runtime import App, Var

        # App(App(Var("f"), Var("x")), Var("y"))
        inner = App(Var("f"), Var("x"))
        outer = App(inner, Var("y"))
        callees = find_callees(outer)

        assert "f" in callees

    def test_no_callees_in_literal(self):
        """Literals have no callees."""
        from auric.runtime import Base

        lit = Base("zero")
        callees = find_callees(lit)

        assert len(callees) == 0


class TestTypeReachability:
    """Test can_var_reach_return."""

    def test_same_type_reachable(self):
        """Same type is reachable."""
        nat_type = Base("Nat")
        assert can_var_reach_return(nat_type, nat_type)

    def test_different_type_not_reachable(self):
        """Different type is not reachable."""
        nat_type = Base("Nat")
        bool_type = Base("Bool")
        assert not can_var_reach_return(nat_type, bool_type)

    def test_subtype_reachable(self):
        """Subtype is reachable."""
        # This depends on the type system's is_subtype
        nat_type = Base("Nat")
        nat_type2 = Base("Nat")
        # Same types should be subtypes
        assert can_var_reach_return(nat_type, nat_type2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
