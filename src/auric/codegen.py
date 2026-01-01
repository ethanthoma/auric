"""C code generation from Auric expressions."""

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, List, Set

from auric.runtime import (
    App,
    Base,
    Case,
    Exp,
    Lam,
    Region,
    Shape,
    ShapeT,
    TyAbs,
    TyAppE,
    Type,
    Var,
    builtin_constructors,
    synth_with_region,
)


def is_tail_recursive_call(e: Exp, func_name: str) -> bool:
    """Check if expression contains a direct recursive call in tail position."""
    if isinstance(e, App):
        # Recursive call if function is the function name
        return isinstance(e.fn, Var) and e.fn.name == func_name
    if isinstance(e, Case):
        # Function is tail-recursive if ANY branch has a tail call
        return any(is_tail_recursive_call(body, func_name) for _, (_, body) in e.alts.items())
    return False


def analyze_var_usage(e: Exp) -> Dict[str, int]:
    """Count how many times each variable is used in expression.

    Returns dict mapping variable names to usage count.
    """
    usage: DefaultDict[str, int] = defaultdict(int)

    def count_vars(expr: Exp) -> None:
        if isinstance(expr, Var):
            usage[expr.name] += 1
        elif isinstance(expr, App):
            count_vars(expr.fn)
            for arg in expr.args:
                count_vars(arg)
        elif isinstance(expr, TyAbs):
            count_vars(expr.body)
        elif isinstance(expr, TyAppE):
            count_vars(expr.fn)
        elif isinstance(expr, Case):
            count_vars(expr.scr)
            for tag, (binds, body) in expr.alts.items():
                count_vars(body)

    count_vars(e)
    return dict(usage)


def collect_type_instantiations(e: Exp) -> Dict[str, Set[str]]:
    """Collect all type instantiations of polymorphic functions.

    Returns dict mapping function names to set of type names applied to them.
    E.g., if identity(Nat, x) and identity(Bool, y) are called, returns
    {'identity': {'Nat', 'Bool'}}
    """
    instantiations: DefaultDict[str, Set[str]] = defaultdict(set)

    def collect(expr: Exp) -> None:
        if isinstance(expr, App):
            fn = expr.fn
            # Check if function is a type-applied function
            if isinstance(fn, TyAppE) and isinstance(fn.fn, Var):
                func_name = fn.fn.name
                type_name = _type_to_str(fn.arg_ty)
                instantiations[func_name].add(type_name)
            collect(expr.fn)
            for arg in expr.args:
                collect(arg)
        elif isinstance(expr, TyAbs):
            collect(expr.body)
        elif isinstance(expr, TyAppE):
            collect(expr.fn)
        elif isinstance(expr, Case):
            collect(expr.scr)
            for tag, (binds, body) in expr.alts.items():
                collect(body)
        elif isinstance(expr, Lam):
            collect(expr.body)

    collect(e)
    return dict(instantiations)


def _type_to_str(ty: Type) -> str:
    """Convert a Type to a string representation for specialization names."""
    if isinstance(ty, ShapeT):
        if isinstance(ty.shape, Base):
            return ty.shape.name
        return "Type"
    return "Generic"


def function_needs_arena(e: Exp) -> bool:
    """Check if function allocates values (and thus needs arena parameter).

    Functions with Case expressions, App expressions, or constructors allocate.
    Pure variable returns don't allocate.
    """

    def has_allocation(expr: Exp) -> bool:
        if isinstance(expr, Var):
            return False
        elif isinstance(expr, Lam):
            return has_allocation(expr.body)
        elif isinstance(expr, TyAbs):
            return has_allocation(expr.body)
        elif isinstance(expr, TyAppE):
            return has_allocation(expr.fn)
        elif isinstance(expr, App):
            return True  # Function calls allocate
        elif isinstance(expr, Case):
            return True  # Cases allocate
        elif isinstance(expr, Base):
            return True  # Constructors allocate
        return False

    return has_allocation(e)


def compute_regions(e: Exp, g: Dict[str, Type], all_defs: Dict[str, Exp] = None) -> Dict[int, Region]:
    """Compute regions for all subexpressions.

    Args:
        e: Expression to analyze
        g: Type context (environment)
        all_defs: All function definitions (for infer_region)

    Returns:
        Dict mapping expression id to Region
    """
    if all_defs is None:
        all_defs = {}

    regions: Dict[int, Region] = {}

    def visit(expr: Exp) -> Region:
        """Visit expression, compute its region, return region."""
        try:
            _, region = synth_with_region(g, expr, all_defs)
            regions[id(expr)] = region
            return region
        except Exception:
            # If region inference fails, default to local
            regions[id(expr)] = Region("local")
            return Region("local")

    def walk(expr: Exp) -> None:
        """Walk through all subexpressions."""
        visit(expr)

        if isinstance(expr, Var):
            pass
        elif isinstance(expr, Lam):
            # Add parameters to context for body analysis
            new_g = g.copy()
            for param in expr.params:
                new_g[param] = g.get(param, ShapeT(Base("Unknown")))
            walk_with_env(expr.body, new_g)
        elif isinstance(expr, TyAbs):
            walk(expr.body)
        elif isinstance(expr, TyAppE):
            walk(expr.fn)
        elif isinstance(expr, App):
            walk(expr.fn)
            for arg in expr.args:
                walk(arg)
        elif isinstance(expr, Case):
            walk(expr.scr)
            for tag, (binds, body) in expr.alts.items():
                # Create new context with bound variables
                new_g = g.copy()
                for bind in binds:
                    if bind != "_":
                        new_g[bind] = ShapeT(Base("Unknown"))
                walk_with_env(body, new_g)

    def walk_with_env(expr: Exp, env: Dict[str, Type]) -> None:
        """Walk with updated environment."""
        try:
            _, region = synth_with_region(env, expr, all_defs)
            regions[id(expr)] = region
        except Exception:
            regions[id(expr)] = Region("local")

        if isinstance(expr, Var):
            pass
        elif isinstance(expr, Lam):
            new_g = env.copy()
            for param in expr.params:
                new_g[param] = env.get(param, ShapeT(Base("Unknown")))
            walk_with_env(expr.body, new_g)
        elif isinstance(expr, TyAbs):
            walk_with_env(expr.body, env)
        elif isinstance(expr, TyAppE):
            walk_with_env(expr.fn, env)
        elif isinstance(expr, App):
            walk_with_env(expr.fn, env)
            for arg in expr.args:
                walk_with_env(arg, env)
        elif isinstance(expr, Case):
            walk_with_env(expr.scr, env)
            for tag, (binds, body) in expr.alts.items():
                new_g = env.copy()
                for bind in binds:
                    if bind != "_":
                        new_g[bind] = ShapeT(Base("Unknown"))
                walk_with_env(body, new_g)

    walk(e)
    return regions


@dataclass
class CCodegen:
    """Generate C code from Auric AST."""

    def __init__(self):
        self.code: List[str] = []
        self.functions: Set[str] = set()
        self.indent_level = 0
        self.defined_funcs: Set[str] = set()  # Track defined functions for forward refs
        self.type_specializations: Dict[str, Set[str]] = {}  # func_name -> set of type names
        self.regions: Dict[int, Region] = {}  # Expression id -> Region
        self.in_arena_context: bool = False  # Whether we're in a function with arena allocation

    def emit(self, line: str) -> None:
        """Emit a line of C code."""
        self.code.append("  " * self.indent_level + line)

    def emit_header(self) -> str:
        """Generate C header with types and forward declarations."""
        header = """#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct Value {
    uint32_t rc;       // Reference count
    uint32_t tag;      // Constructor tag
    void *data[3];     // Up to 3 fields
} Value;

// Arena allocator for region-based allocation
#define ARENA_SIZE 65536  // 64KB local arena
typedef struct Arena {
    void *start;
    void *current;
    void *end;
    int is_dynamic;     // Flag: is this a dynamic (malloc'd) arena?
} Arena;

Arena arena_create_static(void *buffer, size_t size) {
    Arena a;
    a.start = buffer;
    a.current = buffer;
    a.end = (char*)buffer + size;
    a.is_dynamic = 0;
    return a;
}

Arena arena_create_dynamic(size_t size) {
    Arena a;
    a.start = malloc(size);
    a.current = a.start;
    a.end = (char*)a.start + size;
    a.is_dynamic = 1;
    return a;
}

Value *arena_alloc(Arena *a, uint32_t tag) {
    if ((char*)a->current + sizeof(Value) > (char*)a->end) {
        // Arena overflow - fall back to malloc (with RC)
        Value *v = malloc(sizeof(Value));
        v->rc = 1;
        v->tag = tag;
        return v;
    }
    Value *v = (Value*)a->current;
    a->current = (char*)a->current + sizeof(Value);
    v->rc = UINT32_MAX;  // Mark as arena-allocated (immortal)
    v->tag = tag;
    return v;
}

void arena_reset(Arena *a) {
    a->current = a->start;
}

void arena_free(Arena *a) {
    if (a->is_dynamic) {
        free(a->start);
    }
    // Stack-allocated arenas are freed automatically
}

// Traditional malloc-based allocation (for RC-managed values)
Value *value_alloc(uint32_t tag) {
    Value *v = malloc(sizeof(Value));
    v->rc = 1;
    v->tag = tag;
    return v;
}

// Stack allocation: static constants for zero-arity constructors
static Value zero_value = {.rc = UINT32_MAX, .tag = 0};
static Value true_value = {.rc = UINT32_MAX, .tag = 0};
static Value false_value = {.rc = UINT32_MAX, .tag = 1};
static Value nil_value = {.rc = UINT32_MAX, .tag = 0};

void value_incr(Value *v) {
    if (v && v->rc != UINT32_MAX) v->rc++;  // Don't incr immortal constants
}

void value_decr(Value *v) {
    if (!v || v->rc == UINT32_MAX) return;  // Don't decr immortal constants
    v->rc--;
    if (v->rc == 0) free(v);
}

// Built-in constructors (stack-allocated constants)
Value *make_zero() {
    return &zero_value;  // Stack allocated constant
}

Value *make_succ(Value *n) {
    Value *v = value_alloc(1);  // tag 1 = succ (heap allocated)
    v->data[0] = n;
    return v;
}

Value *make_true() {
    return &true_value;  // Stack allocated constant
}

Value *make_false() {
    return &false_value;  // Stack allocated constant
}

Value *make_nil() {
    return &nil_value;  // Stack allocated constant
}

Value *make_cons(Value *h, Value *t) {
    Value *v = value_alloc(1);  // tag 1 = cons (heap allocated)
    v->data[0] = h;
    v->data[1] = t;
    return v;
}

"""
        return header

    def emit_footer(self) -> str:
        """Generate C footer with main function."""
        return """
int main() {
    // Test code will go here
    return 0;
}
"""

    def codegen_exp(self, e: Exp, env: Dict[str, str], usage: Dict[str, int] = None) -> str:
        """Generate C code to evaluate an expression.

        Args:
            e: Expression to generate code for
            env: Environment mapping variable names to C variable names
            usage: Dict mapping variable names to usage count (for clone elision)

        Returns variable name holding the result.
        """
        if usage is None:
            usage = {}

        if isinstance(e, Var):
            # Check if it's a variable in the environment
            if e.name in env:
                var_name = env[e.name]
                # Clone elision: only increment rc if variable is used multiple times
                # AND the region is not local
                need_incr = usage.get(e.name, 1) > 1
                region = self.regions.get(id(e), Region("local"))
                need_incr = need_incr and not region.is_local()
                result_var = f"result_{id(e)}"
                self.emit(f"Value *{result_var} = {var_name};")
                if need_incr:
                    self.emit(f"value_incr({result_var});  // region: {region}")
                return result_var

            # Check if it's a defined function (forward reference support)
            if e.name in self.defined_funcs:
                return f"(Value *)&eval_{e.name}"

            # Check if it's a built-in 0-arity constructor
            ctor_map = {
                "zero": "make_zero()",
                "true": "make_true()",
                "false": "make_false()",
                "nil": "make_nil()",
            }
            if e.name in ctor_map:
                result_var = f"result_{id(e)}"
                self.emit(f"Value *{result_var} = {ctor_map[e.name]};")
                return result_var

            # Check if it's a multi-argument constructor reference (will be applied later)
            multi_arg_ctors = {"cons", "succ"}
            if e.name in multi_arg_ctors:
                # Return a function pointer (for now, just the constructor name)
                return f"(Value *){hex(hash(e.name))}"

            raise NameError(f"Undefined variable: {e.name}")

        if isinstance(e, Lam):
            # Nested lambdas (closures) not yet supported
            raise TypeError("Nested lambda compilation not yet implemented")

        if isinstance(e, TyAbs):
            # Type abstraction - compile away at type level
            return self.codegen_exp(e.body, env, usage)

        if isinstance(e, TyAppE):
            # Type application - compile away at type level
            return self.codegen_exp(e.exp, env, usage)

        if isinstance(e, App):
            # Check if this is a call to a type-specialized function
            # Pattern: App(TyAppE(Var(func_name), type), [arg])
            if isinstance(e.fn, TyAppE) and isinstance(e.fn.fn, Var) and len(e.args) == 1:
                func_name = e.fn.fn.name
                type_name = _type_to_str(e.fn.arg_ty)
                # Check if we have a specialized version for this type
                if func_name in self.type_specializations and type_name in self.type_specializations[func_name]:
                    # Use specialized version
                    arg_var = self.codegen_exp(e.args[0], env, usage)
                    result_var = f"result_{id(e)}"
                    specialized_name = f"eval_{func_name}_{type_name}"
                    self.emit(f"Value *{result_var} = {specialized_name}({arg_var});")
                    return result_var

            # Default: generic function call with multi-arg support
            # Apply arguments sequentially: f(x, y, z) becomes ((f(x))(y))(z)
            fn_var = self.codegen_exp(e.fn, env, usage)
            result_var = fn_var  # Track result through iterations

            for i, arg_expr in enumerate(e.args):
                arg_var = self.codegen_exp(arg_expr, env, usage)
                new_result = f"result_{id(e)}_{i}"

                # Generate: result = fn(arg)
                # The arg is passed to fn which will decrement it when done
                # The fn pointer itself is also consumed by the call
                self.emit(f"Value *{new_result} = ((Value*(*)(Value*)){result_var})({arg_var});")

                # For intermediate results, need to track and potentially decrement
                if i > 0:
                    # Previous result was an intermediate closure, might need cleanup
                    self.emit(f"// Intermediate application step {i}")

                result_var = new_result

            # Only decrement original fn if it's not in a local region
            fn_region = self.regions.get(id(e.fn), Region("local"))
            if not fn_region.is_local():
                self.emit(f"// Note: fn consumed by first application")

            return result_var

        if isinstance(e, Case):
            # Check if scrutinee is a simple variable (to avoid decrementing parameters)
            is_param = isinstance(e.scr, Var) and e.scr.name in env

            scr_var = self.codegen_exp(e.scr, env, usage)
            result_var = f"result_{id(e)}"

            self.emit(f"Value *{result_var};")
            self.emit(f"switch ({scr_var}->tag) {{")
            self.indent_level += 1

            for tag, (binds, body) in e.alts.items():
                tag_num = self._tag_number(tag)
                self.emit(f"case {tag_num}:")
                self.indent_level += 1

                # Analyze usage in body for clone elision
                body_usage = analyze_var_usage(body)

                # Bind fields from scrutinee
                new_env = env.copy()
                for i, bind in enumerate(binds):
                    if bind != "_":
                        var_name = f"{bind}_{id(e)}"
                        self.emit(f"Value *{var_name} = (Value*){scr_var}->data[{i}];")
                        # Clone elision: only incr if used multiple times AND not in local region
                        if body_usage.get(bind, 0) > 1:
                            bind_region = self.regions.get(id(e.scr), Region("local"))
                            if not bind_region.is_local():
                                self.emit(f"value_incr({var_name});  // region: {bind_region}")
                        new_env[bind] = var_name

                # Evaluate body with usage info
                body_result = self.codegen_exp(body, new_env, body_usage)
                self.emit(f"{result_var} = {body_result};")
                self.emit(f"break;")

                self.indent_level -= 1

            self.emit("}")
            self.indent_level -= 1

            # Only decrement scrutinee if it's not a borrowed parameter AND not in local region
            scr_region = self.regions.get(id(e.scr), Region("local"))
            if not is_param and not scr_region.is_local():
                self.emit(f"value_decr({scr_var});  // scrutinee is consumed, region: {scr_region}")

            return result_var

        if isinstance(e, Base):
            # Built-in constructor (zero, true, false, nil, etc)
            ctor_map = {
                "zero": "make_zero()",
                "succ": None,  # needs argument
                "true": "make_true()",
                "false": "make_false()",
                "nil": "make_nil()",
                "cons": None,  # needs arguments
            }
            if e.name in ctor_map and ctor_map[e.name]:
                result_var = f"result_{id(e)}"
                self.emit(f"Value *{result_var} = {ctor_map[e.name]};")
                return result_var

        raise TypeError(f"Cannot codegen {type(e).__name__}")

    def _tag_number(self, tag: str) -> int:
        """Map tag names to numbers."""
        mapping = {
            "zero": 0,
            "succ": 1,
            "true": 0,
            "false": 1,
            "nil": 0,
            "cons": 1,
        }
        return mapping.get(tag, 0)

    def generate(self, defs: Dict[str, Exp]) -> str:
        """Generate complete C program."""
        self.code = []
        self.indent_level = 0
        self.defined_funcs = set(defs.keys())  # Track all defined functions
        self.type_specializations = {}  # Reset specializations
        self.regions = {}  # Reset regions

        # First pass: collect all type instantiations
        for name, exp in defs.items():
            insts = collect_type_instantiations(exp)
            for func_name, type_set in insts.items():
                if func_name not in self.type_specializations:
                    self.type_specializations[func_name] = set()
                self.type_specializations[func_name].update(type_set)

        # Second pass: compute regions for all expressions
        gamma = builtin_constructors()
        for name, exp in defs.items():
            try:
                regions = compute_regions(exp, gamma, defs)
                self.regions.update(regions)
            except Exception:
                # If region computation fails, continue with default regions
                pass

        # Emit header with type definitions and built-in functions
        self.code.append(self.emit_header())

        # Emit forward declarations for all functions (enables forward references)
        self.code.append("// Forward declarations")
        for name, exp in defs.items():
            # Unwrap TyAbs to check if it's a function
            unwrapped = exp
            while isinstance(unwrapped, TyAbs):
                unwrapped = unwrapped.body

            # Functions take an argument, constants don't
            if isinstance(unwrapped, Lam):
                self.code.append(f"Value *eval_{name}(Value *arg);")
                # Emit forward declarations for type specializations
                if name in self.type_specializations:
                    for type_name in sorted(self.type_specializations[name]):
                        self.code.append(f"Value *eval_{name}_{type_name}(Value *arg);")
            else:
                self.code.append(f"Value *eval_{name}(void);")
        self.code.append("")

        # Generate function definitions
        for name, exp in defs.items():
            self._codegen_def(name, exp)
            self.code.append("")
            # Generate specialized versions
            if name in self.type_specializations:
                for type_name in sorted(self.type_specializations[name]):
                    self._codegen_def_specialized(name, exp, type_name)
                    self.code.append("")

        # Emit footer with main function
        self.code.append(self.emit_footer())

        return "\n".join(self.code)

    def _codegen_def(self, name: str, exp: Exp) -> None:
        """Generate a function definition."""
        # Unwrap TyAbs to get to the actual function/constant
        unwrapped_exp = exp
        while isinstance(unwrapped_exp, TyAbs):
            unwrapped_exp = unwrapped_exp.body

        if isinstance(unwrapped_exp, Lam):
            # Function definition: extract params and body
            # Multi-param lambdas: generate nested single-param C functions
            # For now, handle only the first parameter at top level
            if len(unwrapped_exp.params) > 1:
                # TODO: Generate nested closures for multi-param functions
                # For now, we'll just handle the first param and the body should
                # contain nested lambdas for the rest
                first_param = unwrapped_exp.params[0]
                # Create nested lambda for remaining params
                inner_lam = Lam(unwrapped_exp.params[1:], unwrapped_exp.body)
                effective_body = inner_lam
                param = first_param
            else:
                param = unwrapped_exp.params[0]
                effective_body = unwrapped_exp.body

            # Analyze usage for clone elision (excluding the parameter itself - it's borrowed)
            body_usage = analyze_var_usage(effective_body)
            # Don't apply clone elision to parameter - it's borrowed from caller
            # Remove parameter from usage analysis
            body_usage.pop(param, None)

            # Check if function is tail-recursive for optimization opportunities
            is_tail_recursive = is_tail_recursive_call(effective_body, name)

            # Check if function needs arena allocation
            needs_arena = function_needs_arena(effective_body)

            self.code.append(f"Value *eval_{name}(Value *{param}) {{")
            self.indent_level = 1

            if needs_arena:
                # Create a local arena for allocations in this function
                self.emit("static char arena_buffer[ARENA_SIZE];  // Local arena for this function")
                self.emit("Arena arena = arena_create_static(arena_buffer, ARENA_SIZE);")
                self.in_arena_context = True

            if is_tail_recursive:
                self.emit("// Tail-recursive function - candidate for TCO")

            result = self.codegen_exp(effective_body, {param: param}, body_usage)

            if needs_arena:
                # Note: arena_free is a no-op for static arenas, but marks cleanup point
                self.emit("arena_reset(&arena);  // Prepare arena for next call")
                self.in_arena_context = False

            # Don't decrement the borrowed parameter
            self.emit(f"return {result};")
            self.indent_level = 0
            self.code.append("}")
        else:
            # Constant definition
            self.code.append(f"Value *eval_{name}() {{")
            self.indent_level = 1

            # Check if constant needs arena allocation
            needs_arena = function_needs_arena(exp)

            if needs_arena:
                self.emit("static char arena_buffer[ARENA_SIZE];  // Local arena for this constant")
                self.emit("Arena arena = arena_create_static(arena_buffer, ARENA_SIZE);")
                self.in_arena_context = True

            result = self.codegen_exp(unwrapped_exp, {}, {})

            if needs_arena:
                self.emit("arena_reset(&arena);  // Prepare arena for next call")
                self.in_arena_context = False

            self.emit(f"return {result};")
            self.indent_level = 0
            self.code.append("}")

    def _codegen_def_specialized(self, name: str, exp: Exp, type_name: str) -> None:
        """Generate a specialized version of a function for a concrete type.

        This creates eval_name_Type variants that can be optimized for specific types.
        Currently generates the same code, but with a specialized name and call site
        optimizations would be added here.
        """
        # Unwrap TyAbs to get to the actual function/constant
        unwrapped_exp = exp
        while isinstance(unwrapped_exp, TyAbs):
            unwrapped_exp = unwrapped_exp.body

        if isinstance(unwrapped_exp, Lam):
            # Function definition: extract params and body
            # Multi-param lambdas: generate nested single-param C functions
            if len(unwrapped_exp.params) > 1:
                first_param = unwrapped_exp.params[0]
                inner_lam = Lam(unwrapped_exp.params[1:], unwrapped_exp.body)
                effective_body = inner_lam
                param = first_param
            else:
                param = unwrapped_exp.params[0]
                effective_body = unwrapped_exp.body

            body_usage = analyze_var_usage(effective_body)
            body_usage.pop(param, None)

            # Check if function is tail-recursive
            is_tail_recursive = is_tail_recursive_call(effective_body, name)

            # Check if function needs arena allocation
            needs_arena = function_needs_arena(effective_body)

            # Generate specialized version with type-specific name
            specialized_name = f"eval_{name}_{type_name}"
            self.code.append(f"Value *{specialized_name}(Value *{param}) {{")
            self.indent_level = 1

            if needs_arena:
                self.emit("static char arena_buffer[ARENA_SIZE];  // Local arena for this specialized function")
                self.emit("Arena arena = arena_create_static(arena_buffer, ARENA_SIZE);")
                self.in_arena_context = True

            if is_tail_recursive:
                self.emit(f"// Specialized {type_name} version - candidate for TCO")

            result = self.codegen_exp(effective_body, {param: param}, body_usage)

            if needs_arena:
                self.emit("arena_reset(&arena);  // Prepare arena for next call")
                self.in_arena_context = False

            self.emit(f"return {result};")
            self.indent_level = 0
            self.code.append("}")
        else:
            # Constant definition (shouldn't be specialized, but handle gracefully)
            specialized_name = f"eval_{name}_{type_name}"
            self.code.append(f"Value *{specialized_name}() {{")
            self.indent_level = 1

            needs_arena = function_needs_arena(exp)
            if needs_arena:
                self.emit("static char arena_buffer[ARENA_SIZE];  // Local arena for this specialized constant")
                self.emit("Arena arena = arena_create_static(arena_buffer, ARENA_SIZE);")
                self.in_arena_context = True

            result = self.codegen_exp(unwrapped_exp, {}, {})

            if needs_arena:
                self.emit("arena_reset(&arena);  // Prepare arena for next call")
                self.in_arena_context = False

            self.emit(f"return {result};")
            self.indent_level = 0
            self.code.append("}")


def codegen_to_c(src: str) -> str:
    """Compile Auric source to C code."""
    from auric.runtime import parse

    sigs, defs = parse(src)
    gen = CCodegen()
    return gen.generate(defs)
