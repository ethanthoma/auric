"""Macro expansion for Auric.

Macros are syntax transformations that happen before type checking.
They allow convenient syntax sugar while keeping the core language simple.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from auric.ast import (
    App,
    Base,
    Case,
    Const,
    DepApp,
    Exp,
    FieldAccess,
    Handle,
    If,
    Index,
    Lam,
    Let,
    MacroInvocation,
    Perform,
    Record,
    RecordT,
    Seq,
    ShapeT,
    TyAbs,
    TyAppE,
    Type,
    Var,
)

# Type for macro expanders: takes arguments, returns expanded expression
MacroExpander = Callable[[List[Exp]], Exp]

# Type for type-level macro expanders: takes type args and index args, returns expanded type
TypeMacroExpander = Callable[[List[Type], List[Index]], Type]

# Global macro table
_macros: Dict[str, MacroExpander] = {}

# Global type macro table
_type_macros: Dict[str, TypeMacroExpander] = {}

# Counter for gensym
_gensym_counter = 0


def gensym(base: str = "tmp") -> str:
    """Generate unique variable name for hygiene."""
    global _gensym_counter
    _gensym_counter += 1
    return f"{base}${_gensym_counter}"


def register_macro(name: str, expander: MacroExpander) -> None:
    """Register a macro expander."""
    _macros[name] = expander


def register_type_macro(name: str, expander: TypeMacroExpander) -> None:
    """Register a type-level macro expander."""
    _type_macros[name] = expander


def expand_macros(e: Exp, const_defs: Dict[str, Exp] = None) -> Exp:
    """
    Recursively expand all macros in an expression.
    This runs BEFORE type checking.
    const_defs: Optional dictionary of const name -> Record definitions for inlining
    """
    if const_defs is None:
        const_defs = {}

    # Inline const record references for compile-time unrolling
    if isinstance(e, Var) and e.name in const_defs:
        const_val = const_defs[e.name]
        # Only inline if it's a Record (for compile-time unrolling)
        if isinstance(const_val, Record):
            return const_val

    # Expand macro invocations
    if isinstance(e, MacroInvocation):
        if e.macro_name not in _macros:
            raise NameError(f"Unknown macro: {e.macro_name}")

        # Expand arguments first (inside-out expansion)
        expanded_args = [expand_macros(arg, const_defs) for arg in e.args]

        # Apply macro expander
        result = _macros[e.macro_name](expanded_args)

        # Recursively expand result in case macro produces more macros
        # BUT: avoid infinite recursion if macro returns itself unchanged
        if isinstance(result, MacroInvocation) and result.macro_name == e.macro_name and result.args == expanded_args:
            # Macro couldn't expand - return as-is
            return result
        return expand_macros(result, const_defs)

    # Recognize App nodes as macro invocations if function is a registered macro
    # This handles: @when(x, y) which parses as App(Var("@when"), [x, y])
    if isinstance(e, App) and isinstance(e.fn, Var) and e.fn.name in _macros:
        # Convert to macro invocation and expand
        macro_name = e.fn.name
        expanded_args = [expand_macros(arg, const_defs) for arg in e.args]

        # Apply macro expander
        result = _macros[macro_name](expanded_args)

        # Recursively expand result
        return expand_macros(result, const_defs)

    # Recursively expand in subexpressions
    if isinstance(e, Lam):
        return Lam(e.params, expand_macros(e.body, const_defs))

    if isinstance(e, App):
        return App(expand_macros(e.fn, const_defs), [expand_macros(arg, const_defs) for arg in e.args])

    if isinstance(e, TyAbs):
        return TyAbs(e.tv, expand_macros(e.body, const_defs))

    if isinstance(e, TyAppE):
        return TyAppE(expand_macros(e.fn, const_defs), e.arg_ty)

    if isinstance(e, Case):
        return Case(
            expand_macros(e.scr, const_defs),
            {tag: (binds, expand_macros(rhs, const_defs)) for tag, (binds, rhs) in e.alts.items()},
        )

    if isinstance(e, Perform):
        return Perform(e.effect_name, expand_macros(e.args, const_defs))

    if isinstance(e, Handle):
        return Handle(
            expand_macros(e.body, const_defs),
            {
                eff: (binds, expand_macros(handler, const_defs))
                for eff, (binds, handler) in e.handlers.items()
            },
        )

    if isinstance(e, Record):
        return Record({name: expand_macros(val, const_defs) for name, val in e.fields.items()})

    if isinstance(e, FieldAccess):
        return FieldAccess(expand_macros(e.record, const_defs), e.field)

    if isinstance(e, If):
        return If(
            expand_macros(e.cond, const_defs),
            expand_macros(e.then_branch, const_defs),
            expand_macros(e.else_branch, const_defs)
        )

    if isinstance(e, Seq):
        return Seq([expand_macros(expr, const_defs) for expr in e.exprs])

    # Expand Let bindings (all bindings are recursive by default)
    if isinstance(e, Let):
        return Let(e.name, expand_macros(e.value, const_defs), expand_macros(e.body, const_defs))

    # Base case: Var and other literals
    return e


# ============================================================
# Built-in Macros
# ============================================================


def _expand_index(args: List[Exp]) -> Exp:
    """
    Expand array indexing: vec[i] → vec._i

    Only supports compile-time constant indices (numeric literals).
    The parser ensures index_expr is a Var with a numeric name.
    """
    if len(args) != 2:
        raise SyntaxError(f"index macro expects 2 arguments, got {len(args)}")

    vec_expr, index_expr = args

    # The parser guarantees this is a Var with a numeric name
    if isinstance(index_expr, Var):
        # vec[0] → vec._0
        return FieldAccess(vec_expr, f"_{index_expr.name}")

    # This should never happen if parser is correct
    raise SyntaxError(
        f"Internal error: expected Var index, got {type(index_expr).__name__}"
    )


def _expand_list(args: List[Exp]) -> Exp:
    """
    Expand list literal: [x, y, z] → cons(x, cons(y, cons(z, nil)))
    """
    # Build from right to left
    result = Var("nil")
    for elem in reversed(args):
        # cons(elem, result)
        result = App(App(Var("cons"), elem), result)
    return result


def _expand_for(args: List[Exp]) -> Exp:
    """
    Expand for loop: @for(vec, (i) => body)

    When vec is a compile-time known Record, unrolls the loop:
        for i = ..vec { body } → { body(vec._0); body(vec._1); ... }

    Otherwise, keeps the macro invocation for later expansion.
    """
    if len(args) != 2:
        raise SyntaxError(f"@for macro expects 2 arguments, got {len(args)}")

    iterable, lam = args

    # Extract binding and body from lambda
    if not isinstance(lam, Lam):
        raise SyntaxError(f"@for macro expects second argument to be lambda, got {type(lam).__name__}")

    if len(lam.params) != 1:
        raise SyntaxError(f"@for macro expects lambda with exactly one parameter, got {len(lam.params)}")

    binding = lam.params[0]
    body = lam.body

    # Check if iterable is a record literal (compile-time known)
    if isinstance(iterable, Record):
        # Compile-time unrolling!
        # Extract indexed fields: _0, _1, _2, ...
        fields = iterable.fields

        # Find all indexed fields and sort by index
        indexed_fields = []
        for field_name, field_expr in fields.items():
            if field_name.startswith("_") and field_name[1:].isdigit():
                idx = int(field_name[1:])
                indexed_fields.append((idx, field_expr))

        # Sort by index
        indexed_fields.sort(key=lambda x: x[0])

        if not indexed_fields:
            # Empty vector - return @zero
            return Var("@zero")

        # Generate unrolled iteration: { ((i) => body)(val0); ((i) => body)(val1); ... }
        iterations = []
        for _, field_val in indexed_fields:
            # ((i) => body)(field_val)
            iteration = App(Lam(binding, body), field_val)
            iterations.append(iteration)

        # Wrap in sequence
        if len(iterations) == 1:
            return iterations[0]
        else:
            return Seq(iterations)

    # Non-record iterable - return the macro invocation unchanged
    # This allows const propagation to inline Records in subsequent passes
    from auric.ast import MacroInvocation
    return MacroInvocation("@for", args)


def expand_type_macros(t: Type) -> Type:
    """
    Recursively expand all type-level macros in a type.
    This runs BEFORE type checking.
    """
    from auric.ast import Arrow, Forall, ForallIdx, ShapeT, TyApp, TyVar, RefT

    # Expand type macro invocations (DepApp nodes)
    if isinstance(t, DepApp):
        if t.base not in _type_macros:
            # Not a macro, keep as is (for other dependent types)
            return t

        # Apply type macro expander
        result = _type_macros[t.base](t.type_args, t.index_args)

        # Recursively expand result in case macro produces more macros
        return expand_type_macros(result)

    # Recursively expand in type substructures
    if isinstance(t, Arrow):
        return Arrow(
            expand_type_macros(t.param),
            expand_type_macros(t.ret),
            t.effects
        )

    if isinstance(t, Forall):
        return Forall(t.tv, expand_type_macros(t.body))

    if isinstance(t, ForallIdx):
        return ForallIdx(t.idx_var, t.idx_kind, expand_type_macros(t.body))

    if isinstance(t, TyApp):
        return TyApp(
            expand_type_macros(t.head),
            expand_type_macros(t.arg)
        )

    if isinstance(t, RecordT):
        return RecordT({
            name: expand_type_macros(field_ty)
            for name, field_ty in t.fields.items()
        })

    # Base cases: TyVar, ShapeT, RefT
    return t


# ============================================================
# Built-in Type Macros
# ============================================================


def _expand_vec(type_args: List[Type], index_args: List[Index]) -> Type:
    """
    Expand Vec[T, n] to a record type .{ _0: T, _1: T, ..., _(n-1): T }.

    Examples:
        Vec[Int, zero]                  -> .{}
        Vec[Int, succ(zero)]            -> .{ _0: Int }
        Vec[Int, succ(succ(zero))]      -> .{ _0: Int, _1: Int }
    """
    from auric.types import index_to_nat

    if len(type_args) != 1:
        raise TypeError(f"Vec expects 1 type argument, got {len(type_args)}")

    if len(index_args) != 1:
        raise TypeError(f"Vec expects 1 index argument, got {len(index_args)}")

    elem_ty = type_args[0]
    length_idx = index_args[0]

    # Convert index to concrete nat
    n = index_to_nat(length_idx)
    if n is None:
        # Unknown length - return empty record for now
        # TODO: Support polymorphic vectors with index variables
        return RecordT({})

    # Build record with n fields
    fields = {}
    for i in range(n):
        fields[f"_{i}"] = elem_ty
    return RecordT(fields)


# Register built-in macros
register_macro("index", _expand_index)
register_macro("list", _expand_list)
# NOTE: @for is now defined in std/builtins.au using compile-time primitives!
# register_macro("@for", _expand_for)

# Register built-in type macros
register_type_macro("Vec", _expand_vec)


# ============================================================
# Control Flow Macros
# ============================================================


def _expand_when(args: List[Exp]) -> Exp:
    """
    Expand when macro: @when(test, body) → test => { @true -> body; @false -> () }

    Lisp equivalent: (when test body) → (if test body nil)

    Examples:
        @when(x, Print("yes"))  →  x => { @true -> Print("yes"); @false -> () }
    """
    if len(args) != 2:
        raise SyntaxError(f"@when macro expects 2 arguments (condition, body), got {len(args)}")

    test, body = args

    # Generate: test => { @true -> body; @false -> () }
    # () represents the empty/unit value (no-op)
    empty_record = Record({})  # Empty record as unit value

    return Case(
        test,
        {
            "@true": ([], body),
            "@false": ([], empty_record),
        }
    )


def _expand_unless(args: List[Exp]) -> Exp:
    """
    Expand unless macro: @unless(test, body) → test => { @false -> body; @true -> () }

    Opposite of when - executes body if test is false.

    Examples:
        @unless(x, Print("no"))  →  x => { @false -> Print("no"); @true -> () }
    """
    if len(args) != 2:
        raise SyntaxError(f"@unless macro expects 2 arguments (condition, body), got {len(args)}")

    test, body = args

    # Generate: test => { @false -> body; @true -> () }
    empty_record = Record({})  # Empty record as unit value

    return Case(
        test,
        {
            "@false": ([], body),
            "@true": ([], empty_record),
        }
    )


def _expand_pipe(args: List[Exp]) -> Exp:
    """
    Expand pipe macro: @pipe(x, f) → f(x)

    Reverses function application for better readability.

    Examples:
        @pipe(5, double)      →  double(5)
        @pipe(x, f, g, h)     →  h(g(f(x)))  (chaining multiple functions)
    """
    if len(args) < 2:
        raise SyntaxError(f"@pipe macro expects at least 2 arguments (value, function, ...), got {len(args)}")

    # First arg is the value, rest are functions to apply
    value = args[0]
    functions = args[1:]

    # Chain applications: f(g(h(value)))
    result = value
    for fn in functions:
        result = App(fn, [result])

    return result


def _expand_inline(args: List[Exp]) -> Exp:
    """
    Expand inline macro: @inline(expr) → expr

    Currently a no-op that just returns the expression.
    In the future, could mark expressions for aggressive inlining.

    Examples:
        @inline(add(x, y))  →  add(x, y)
    """
    if len(args) != 1:
        raise SyntaxError(f"@inline macro expects 1 argument, got {len(args)}")

    # For now, just return the expression unchanged
    # In future: could add metadata for optimizer
    return args[0]


# Register control flow macros
register_macro("@when", _expand_when)
register_macro("@unless", _expand_unless)
register_macro("@pipe", _expand_pipe)
register_macro("@inline", _expand_inline)
