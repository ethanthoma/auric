"""Type checking and inference for Auric."""

from __future__ import annotations

from typing import Dict, List, Optional

from auric.ast import (
    App,
    Arrow,
    Base,
    Case,
    Const,
    DepApp,
    Exp,
    FieldAccess,
    Forall,
    ForallIdx,
    Handle,
    IdxUnknown,
    IdxVar,
    IdxZero,
    Lam,
    Perform,
    Record,
    RecordT,
    ShapeT,
    Top,
    TyAppE,
    TyAbs,
    TyVar,
    Type,
    Var,
)
from auric.parser import parse
from auric.types import (
    ctors,
    is_subtype,
    is_subtype_shape,
    shape_of,
    split_app,
    subst,
    subst_index,
)

Env = Dict[str, any]


# Counter for generating fresh type variables
_fresh_counter = 0


def fresh_tyvar() -> str:
    """Generate a fresh type variable name."""
    global _fresh_counter
    _fresh_counter += 1
    return f"?{_fresh_counter}"


def instantiate(ty: Type) -> Type:
    """Instantiate a polymorphic type with fresh type variables.

    Forall T. Body  →  Body[T := ?fresh]
    ForallIdx n. Body  →  Body[n := _]  (unknown index)
    """
    if isinstance(ty, Forall):
        # Instantiate type variable with fresh unknown
        fresh = TyVar(fresh_tyvar())
        body = subst(ty.body, ty.tv, fresh)
        # Recursively instantiate if still polymorphic
        return instantiate(body)

    if isinstance(ty, ForallIdx):
        # Instantiate index variable with unknown
        body = subst_idx_in_type(ty.body, ty.idx_var, IdxUnknown())
        # Recursively instantiate if still polymorphic
        return instantiate(body)

    return ty


def subst_idx_in_type(ty: Type, idx_var: str, idx_val) -> Type:
    """Substitute index variable in a type."""
    if isinstance(ty, DepApp):
        new_indices = [subst_index(idx, idx_var, idx_val) for idx in ty.index_args]
        return DepApp(ty.base, ty.type_args, new_indices)
    if isinstance(ty, Arrow):
        return Arrow(
            subst_idx_in_type(ty.param, idx_var, idx_val),
            subst_idx_in_type(ty.ret, idx_var, idx_val),
            ty.effects
        )
    if isinstance(ty, ForallIdx):
        # Don't substitute if shadowed
        if ty.idx_var == idx_var:
            return ty
        return ForallIdx(
            ty.idx_var,
            ty.idx_kind,
            subst_idx_in_type(ty.body, idx_var, idx_val)
        )
    if isinstance(ty, Forall):
        return Forall(ty.tv, subst_idx_in_type(ty.body, idx_var, idx_val))
    return ty


def check(g: Dict[str, Type], e: Exp, t: Type) -> None:
    """Check that expression e has type t in context g.

    Uses bidirectional type checking: synthesizes type for most expressions,
    but uses the expected type for lambdas and type abstractions.
    """
    if isinstance(e, Lam) and isinstance(t, Arrow):
        # Check multi-arg lambda against nested Arrow types
        current_ty = t
        new_g = g.copy()
        for param in e.params:
            if not isinstance(current_ty, Arrow):
                raise TypeError(f"lambda has more parameters than expected Arrow type")
            new_g[param] = current_ty.param
            current_ty = current_ty.ret
        check(new_g, e.body, current_ty)
        return
    if isinstance(e, TyAbs) and isinstance(t, Forall):
        check(g, e.body, t.body)
        return
    actual = synth(g, e)
    if not is_subtype(actual, t):
        raise TypeError(f"wanted {t}, got {actual}")


def synth(g: Dict[str, Type], e: Exp) -> Type:
    """Synthesize (infer) the type of expression e in context g."""
    if isinstance(e, Var):
        ty = g[e.name]
        # Automatically instantiate polymorphic types
        return instantiate(ty)

    if isinstance(e, App):
        fn_ty = synth(g, e.fn)
        # Instantiate if still polymorphic after initial synth
        fn_ty = instantiate(fn_ty)
        # Type check each argument in sequence (multi-arg application)
        current_ty = fn_ty
        for arg in e.args:
            if not isinstance(current_ty, Arrow):
                raise TypeError(f"apply non-function (expected Arrow, got {current_ty})")
            check(g, arg, current_ty.param)
            current_ty = current_ty.ret
        return current_ty

    if isinstance(e, TyAppE):
        fn_ty = synth(g, e.fn)
        if not isinstance(fn_ty, Forall):
            raise TypeError(f"type-apply non-generic value: {fn_ty} (expr: {e.fn})")
        return subst(fn_ty.body, fn_ty.tv, e.arg_ty)

    if isinstance(e, Case):
        scr_ty = synth(g, e.scrut)
        scr_shape = shape_of(scr_ty)
        if scr_shape is None:
            raise TypeError("case scrutinee must have a data-constructor shape")

        # Check exhaustiveness: all constructors in shape must be covered
        shape_ctors = ctors(scr_shape)
        alt_ctors = set(e.alts.keys())
        # Wildcard '_' matches all remaining constructors
        has_wildcard = "_" in alt_ctors
        if not has_wildcard:
            missing = shape_ctors - alt_ctors
            if missing:
                raise TypeError(f"non-exhaustive pattern match, missing: {', '.join(sorted(missing))}")

        res_ty: Optional[Type] = None
        for tag, (binds, rhs) in e.alts.items():
            # Skip validation for wildcard pattern
            if tag != "_" and tag not in ctors(scr_shape):
                raise TypeError(f"constructor {tag} not in {scr_shape}")

            loc = g.copy()

            # Try to infer parameter types for bound variables
            if tag in g:
                ctor_ty = g[tag]
                # Instantiate polymorphic constructors
                ctor_ty = instantiate(ctor_ty)
                # Extract parameter types from constructor type
                param_types: List[Type] = []
                current = ctor_ty
                while isinstance(current, Arrow):
                    param_types.append(current.param)
                    current = current.ret

                # Bind pattern variables to parameter types
                for i, name in enumerate(binds):
                    if i < len(param_types) and name != "_":
                        loc[name] = param_types[i]

            # Special handling for cons with type parameters
            if tag == "cons":
                base, *rest = binds
                shape_info = split_app(scr_ty)
                if shape_info:
                    base_shape, [elem_ty] = shape_info
                    if isinstance(base_shape, Base) and base_shape.name == "List":
                        if base != "_":
                            loc[base] = elem_ty
                        if rest and rest[0] != "_":
                            loc[rest[0]] = scr_ty

            # Ensure all bound variables have a type
            for n in binds:
                loc.setdefault(n, ShapeT(Top()))

            branch_ty = synth(loc, rhs)

            if res_ty is None:
                res_ty = branch_ty
            elif branch_ty != res_ty:
                raise TypeError("branch result types differ")

        assert res_ty is not None
        return res_ty

    if isinstance(e, Perform):
        # Effect invocation: Print("hello"), Read(), etc
        # Look up the effect in the context
        if e.effect_name not in g:
            raise TypeError(f"Unknown effect: {e.effect_name}")
        effect_ty = g[e.effect_name]
        if not isinstance(effect_ty, Arrow):
            raise TypeError(f"{e.effect_name} is not an effect")
        # Check the argument type
        arg_ty = synth(g, e.args)
        if not is_subtype(arg_ty, effect_ty.param):
            raise TypeError(f"Effect {e.effect_name} expects {effect_ty.param}, got {arg_ty}")
        # Return the effect's return type
        return effect_ty.ret

    if isinstance(e, Handle):
        # Handle expression: handle expr { Effect(...) -> handler; ... }
        # Type of handle expression is the type of the body expression
        # (handlers don't change the type, they just implement effects)
        body_ty = synth(g, e.body)

        # Verify that all handlers have consistent types
        for effect_name, (binds, handler_body) in e.handlers.items():
            if effect_name not in g:
                raise TypeError(f"Unknown effect in handler: {effect_name}")
            effect_ty = g[effect_name]
            if not isinstance(effect_ty, Arrow):
                raise TypeError(f"{effect_name} is not an effect")

            # Build context for handler with bound variables
            handler_ctx = g.copy()

            # The bound variables in the handler pattern should match the effect param
            # For now, just bind them to Top() to be permissive
            for bind in binds:
                if bind != "_":
                    handler_ctx[bind] = ShapeT(Top())

            # Handler body should return the same type as the handled body
            # (the resume continuation returns this type)
            handler_ty = synth(handler_ctx, handler_body)
            # Handler return type should be compatible with body type
            # (it's what gets returned when the effect is handled)

        return body_ty

    if isinstance(e, Record):
        # Synthesize type for record literal
        field_types = {}
        for field_name, field_expr in e.fields.items():
            field_types[field_name] = synth(g, field_expr)
        return RecordT(field_types)

    if isinstance(e, FieldAccess):
        # Synthesize type for field access
        from auric.types import normalize_type

        record_ty = synth(g, e.record)
        # Normalize Vec to RecordT if possible
        record_ty = normalize_type(record_ty)

        if not isinstance(record_ty, RecordT):
            raise TypeError(f"Cannot access field of non-record type: {record_ty}")
        if e.field not in record_ty.fields:
            raise TypeError(f"Field {e.field} not found in record type {record_ty}")
        return record_ty.fields[e.field]

    # Constant literals (int, float, char, bool)
    if isinstance(e, Const):
        # Type is already explicit in the Const node
        return e.ty

    raise TypeError("need annotation")
