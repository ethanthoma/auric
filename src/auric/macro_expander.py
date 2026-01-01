"""Macro expansion for user-defined macros in Auric.

This module handles expansion of user-defined macros before type checking.
Macros are defined with:
    macro name = (params) => body

And invoked like function calls:
    macro_name(arg1, arg2)

Macros support compile-time evaluation (comptime):
- Macro bodies execute at expansion time
- Macro parameters hold AST values
- param() evaluates AST at compile-time
"""

from typing import Dict, List, Any
from auric.ast import (
    Exp, App, Var, Lam, TyAbs, TyAppE, Case, Perform, Handle,
    Record, Spread, FieldAccess, MacroInvocation, Const, Base, ShapeT,
    If, Seq, MacroDef, Let
)

# Compile-time builtin functions
COMPTIME_BUILTINS = {
    "repeat_expr",         # repeat_expr(n, body) - generate n copies of body in a sequence
    "seq_cons",            # seq_cons(expr, seq) - prepend expr to sequence
    # AST Construction
    "@var",                # @var(name_var) - create Var node (name_var should be a Var whose name is used)
    "@app",                # @app(fn, arg) - create App node
    "@lam",                # @lam(param_name_var, body) - create Lam node
    "@field_access",       # @field_access(record, field_name_var) - create FieldAccess node
    "@seq",                # @seq(list) - create Seq node from list of expressions
    "@macro_invocation",   # @macro_invocation(name_var, args_list) - create MacroInvocation node
    "@case",               # @case(scrutinee, pat1, expr1, pat2, expr2, ...) - create Case node with alternating patterns and branches
    # AST Inspection
    "@type",               # @type(expr) - get AST node type as Var (Record, App, Lam, etc.)
    "@is_record",          # @is_record(expr) - check if expr is Record (@true/@false)
    "@record_fields",      # @record_fields(record) - get list of field expressions (cons/nil)
    # AST Destructuring (Lisp-style)
    "@app-fn",             # @app-fn(app) - extract function from App node
    "@app-arg",            # @app-arg(app) - extract argument from App node
    "@lam-param",          # @lam-param(lam) - extract parameter name from Lam node
    "@lam-body",           # @lam-body(lam) - extract body from Lam node
    "@var-name",           # @var-name(var) - extract name from Var node
    "@case-scrutinee",     # @case-scrutinee(case) - extract scrutinee from Case node
    "@case-alts",          # @case-alts(case) - extract alternatives from Case node
    # Data Manipulation
    "@concat",             # @concat(str1, str2) - concatenate two variable names
    "@to_string",          # @to_string(nat) - convert nat to string (as Var)
    "@fold_right",         # @fold_right(list, init, fn) - right fold over list
    "@map",                # @map(list, fn) - map function over list
    "@list",               # @list(elem1, elem2, ...) - create cons/nil list from elements
}


def collect_macros(defs: Dict[str, Exp]) -> tuple[Dict[str, MacroDef], Dict[str, Exp]]:
    """Separate macro definitions from regular definitions.

    Returns: (macros, regular_defs)
    """
    macros = {}
    regular_defs = {}

    for name, expr in defs.items():
        if isinstance(expr, MacroDef):
            macros[name] = expr
        else:
            regular_defs[name] = expr

    return macros, regular_defs


def expand_macros(defs: Dict[str, Exp], macros: Dict[str, MacroDef]) -> Dict[str, Exp]:
    """Expand all macro invocations in definitions.

    This recursively expands macros until no more macro calls remain.
    """
    expanded = {}

    for name, expr in defs.items():
        expanded[name] = expand_expr(expr, macros)

    return expanded


def expand_expr(e: Exp, macros: Dict[str, MacroDef], const_defs: Dict[str, Exp] = None) -> Exp:
    """Recursively expand macros in an expression.

    Args:
        e: Expression to expand
        macros: User-defined macros
        const_defs: Optional dictionary of const name -> Record for inlining
    """
    if const_defs is None:
        const_defs = {}

    # Inline const record references for compile-time unrolling
    if isinstance(e, Var) and e.name in const_defs:
        const_val = const_defs[e.name]
        # Only inline if it's a Record (for compile-time unrolling)
        if isinstance(const_val, Record):
            return const_val

    # Check if this is a macro invocation
    if isinstance(e, App):
        # Collect the function and all arguments
        fn, args = collect_app_chain(e)

        # Check if fn is a macro
        if isinstance(fn, Var) and fn.name in macros:
            # This is a macro call!
            macro = macros[fn.name]

            # Expand the macro
            result = expand_macro_invocation(macro, args, macros)

            # Recursively expand result (in case it contains more macros)
            return expand_expr(result, macros, const_defs)

    # Recursively expand subexpressions
    if isinstance(e, Lam):
        return Lam(e.params, expand_expr(e.body, macros, const_defs))

    if isinstance(e, App):
        return App(expand_expr(e.fn, macros, const_defs), [expand_expr(arg, macros, const_defs) for arg in e.args])

    if isinstance(e, TyAbs):
        return TyAbs(e.tv, expand_expr(e.body, macros, const_defs))

    if isinstance(e, TyAppE):
        return TyAppE(expand_expr(e.fn, macros, const_defs), e.arg_ty)

    if isinstance(e, Case):
        return Case(
            expand_expr(e.scr, macros, const_defs),
            {tag: (binds, expand_expr(rhs, macros, const_defs)) for tag, (binds, rhs) in e.alts.items()}
        )

    if isinstance(e, Perform):
        return Perform(e.effect_name, expand_expr(e.args, macros, const_defs))

    if isinstance(e, Handle):
        return Handle(
            expand_expr(e.body, macros, const_defs),
            {eff: (binds, expand_expr(handler, macros, const_defs))
             for eff, (binds, handler) in e.handlers.items()}
        )

    if isinstance(e, Record):
        return Record({name: expand_expr(val, macros, const_defs) for name, val in e.fields.items()})

    if isinstance(e, FieldAccess):
        return FieldAccess(expand_expr(e.record, macros, const_defs), e.field)

    if isinstance(e, If):
        return If(
            expand_expr(e.cond, macros, const_defs),
            expand_expr(e.then_branch, macros, const_defs),
            expand_expr(e.else_branch, macros, const_defs)
        )

    if isinstance(e, Seq):
        return Seq([expand_expr(expr, macros, const_defs) for expr in e.exprs])

    # Handle MacroInvocation nodes (from special syntax like 'for' loops)
    if isinstance(e, MacroInvocation):
        if e.macro_name in macros:
            # Expand arguments first
            expanded_args = [expand_expr(arg, macros, const_defs) for arg in e.args]
            # Expand the macro
            result = expand_macro_invocation(macros[e.macro_name], expanded_args, macros)
            # Avoid infinite recursion if macro returns itself unchanged
            if isinstance(result, MacroInvocation) and result.macro_name == e.macro_name:
                # Check if args are structurally the same (can't use == due to AST structure)
                # For now, just return it as-is - const propagation will inline Records later
                return result
            # Recursively expand result
            return expand_expr(result, macros, const_defs)
        # If not in user-defined macros, keep as-is (might be Python-registered)
        return e

    # Base cases: Var, literals
    return e


def collect_app_chain(e: App) -> tuple[Exp, List[Exp]]:
    """Collect f(a, b, c) into (f, [a, b, c]).

    With multi-arg App, this is now straightforward - just return fn and args.
    We still support nested App if it appears (e.g., f(a, b)(c, d)).
    """
    all_args = []
    current = e

    while isinstance(current, App):
        # Prepend args from this App (they're in correct order)
        all_args = current.args + all_args
        current = current.fn

    return current, all_args


MAX_COMPTIME_DEPTH = 1000  # Maximum recursion depth for totality

def eval_comptime(e: Exp, ast_env: Dict[str, Exp], macros: Dict[str, MacroDef], depth: int = 0) -> Exp:
    """Evaluate macro body at compile-time (comptime mode).

    In comptime mode:
    - Macro parameters are AST values (don't evaluate them)
    - param() calls force evaluation of the AST
    - If expressions evaluate their conditions
    - Everything else is AST construction

    Args:
        depth: Current recursion depth for totality checking

    Returns: AST to be spliced into the program

    Raises:
        RuntimeError: If recursion depth exceeds MAX_COMPTIME_DEPTH (non-total function)
    """

    # Totality enforcement: check recursion depth
    if depth > MAX_COMPTIME_DEPTH:
        raise RuntimeError(
            f"Compile-time evaluation exceeded maximum depth ({MAX_COMPTIME_DEPTH}). "
            f"Ensure recursive functions are total (terminate on all inputs)."
        )

    # If expression: evaluate condition at compile-time
    if isinstance(e, If):
        # Check if condition is a param() call
        cond_result = eval_comptime(e.cond, ast_env, macros, depth + 1)

        # If it's a simple AST, try to evaluate it
        needs_eval = needs_evaluation(cond_result, ast_env)
        if needs_eval:
            # Evaluate the condition to get a boolean
            bool_val = evaluate_to_bool(cond_result, ast_env)
            if bool_val:
                return eval_comptime(e.then_branch, ast_env, macros, depth + 1)
            else:
                return eval_comptime(e.else_branch, ast_env, macros, depth + 1)
        else:
            # Condition is not compile-time known, keep the if
            return If(
                cond_result,
                eval_comptime(e.then_branch, ast_env, macros, depth + 1),
                eval_comptime(e.else_branch, ast_env, macros, depth + 1)
            )

    # Variable: if it's a macro parameter, return the AST
    if isinstance(e, Var):
        if e.name in ast_env:
            # This is a macro parameter - return its AST
            return ast_env[e.name]
        # Check for compile-time builtins
        if e.name in COMPTIME_BUILTINS:
            # Return a special marker for the builtin
            return e
        # Regular variable - keep as is
        return e

    # Application: check for param() pattern, builtin calls, or macro calls
    if isinstance(e, App):
        # Check if this is param() where param is a macro parameter
        if isinstance(e.fn, Var) and e.fn.name in ast_env:
            # This is a call on a macro parameter!
            # Check if the argument is empty (unit) - this means ()
            if len(e.args) == 1 and isinstance(e.args[0], Var) and e.args[0].name == "()":
                # This is param() - evaluate the AST!
                ast_to_eval = ast_env[e.fn.name]
                return evaluate_ast_to_ast(ast_to_eval)

        # Check if this is a compile-time builtin call
        fn, args = collect_app_chain(e)
        if isinstance(fn, Var) and fn.name in COMPTIME_BUILTINS:
            # Call the builtin at compile-time!
            expanded_args = [eval_comptime(arg, ast_env, macros, depth + 1) for arg in args]
            return call_comptime_builtin(fn.name, expanded_args, ast_env, macros)

        # Check if this is a macro call
        if isinstance(fn, Var) and fn.name in macros:
            # This is a macro call within a macro body!
            # Expand it by recursively processing the arguments and invoking the macro
            expanded_args = [eval_comptime(arg, ast_env, macros, depth + 1) for arg in args]
            return expand_macro_invocation(macros[fn.name], expanded_args, macros)

        # Regular application - recurse
        return App(
            eval_comptime(e.fn, ast_env, macros, depth + 1),
            [eval_comptime(arg, ast_env, macros, depth + 1) for arg in e.args]
        )

    # Sequence: recurse on each expression
    if isinstance(e, Seq):
        return Seq([eval_comptime(expr, ast_env, macros, depth + 1) for expr in e.exprs])

    # Lambda: recurse on body (shadow parameters if needed)
    if isinstance(e, Lam):
        new_env = {k: v for k, v in ast_env.items() if k not in e.params}
        return Lam(e.params, eval_comptime(e.body, new_env, macros, depth + 1))

    # Case: try to evaluate pattern match at compile-time
    if isinstance(e, Case):
        # Evaluate the scrutinee
        scr_result = eval_comptime(e.scr, ast_env, macros, depth + 1)

        # Try to match at compile-time if scrutinee is simple enough
        matched_branch = try_match_pattern(scr_result, e.alts, ast_env, macros)
        if matched_branch is not None:
            # We matched! Return the evaluated branch
            return matched_branch

        # Can't match at compile-time, keep the Case
        new_alts = {}
        for tag, (binds, rhs) in e.alts.items():
            # Shadow bound variables
            new_env = {k: v for k, v in ast_env.items() if k not in binds}
            new_alts[tag] = (binds, eval_comptime(rhs, new_env, macros, depth + 1))
        return Case(scr_result, new_alts)

    # Record: recurse on fields and handle spread operator
    if isinstance(e, Record):
        # Check if any field is a Spread
        has_spread = any(key.startswith("__spread_") and isinstance(val, Spread) for key, val in e.fields.items())

        if has_spread:
            # Process record with spread - merge fields
            merged_fields = {}
            indexed_count = 0  # Track how many indexed fields we've added

            for key, val in e.fields.items():
                if key.startswith("__spread_") and isinstance(val, Spread):
                    # Evaluate spread expression
                    spread_result = eval_comptime(val.record, ast_env, macros, depth + 1)

                    if not isinstance(spread_result, Record):
                        raise TypeError(f"Spread operator requires record, got {type(spread_result).__name__}")

                    # Merge fields from spread_result
                    for spread_key, spread_val in spread_result.fields.items():
                        if spread_key.startswith("_") and spread_key[1:].isdigit():
                            # Indexed field - reindex it
                            merged_fields[f"_{indexed_count}"] = spread_val
                            indexed_count += 1
                        else:
                            # Named field - merge directly (later fields override)
                            merged_fields[spread_key] = spread_val
                else:
                    # Regular field
                    evaluated_val = eval_comptime(val, ast_env, macros, depth + 1)
                    if key.startswith("_") and key[1:].isdigit():
                        # Indexed field - reindex it
                        merged_fields[f"_{indexed_count}"] = evaluated_val
                        indexed_count += 1
                    else:
                        # Named field
                        merged_fields[key] = evaluated_val

            return Record(merged_fields)
        else:
            # No spread - just recurse on fields
            return Record({name: eval_comptime(val, ast_env, macros, depth + 1) for name, val in e.fields.items()})

    # Let binding: all bindings are recursive by default
    if isinstance(e, Let):
        # For recursive definitions, add the name to environment before evaluating value
        # This allows self-reference (the value can use the name)
        # We add the unevaluated value as a placeholder (works for lambda definitions)
        new_env = {**ast_env, e.name: e.value}
        val_result = eval_comptime(e.value, new_env, macros, depth + 1)
        # Update environment with evaluated value
        new_env[e.name] = val_result
        # Evaluate body
        return eval_comptime(e.body, new_env, macros, depth + 1)

    # Other forms: keep as-is (literals, etc.)
    return e


def call_comptime_builtin(name: str, args: List[Exp],
                          ast_env: Dict[str, Exp], macros: Dict[str, MacroDef]) -> Exp:
    """Call a compile-time builtin function."""

    if name == "repeat_expr":
        # repeat_expr(n, body) - generate n copies of body
        if len(args) != 2:
            raise TypeError(f"repeat_expr expects 2 arguments, got {len(args)}")

        n_ast, body_ast = args

        # Evaluate n to get the count
        from auric.evaluator import eval_exp, Heap
        env = make_comptime_env()
        result = eval_exp(n_ast, env)

        # Convert to integer
        count = value_to_int(result.data)
        Heap.drop(result)

        if count < 0:
            raise ValueError(f"repeat_expr count must be non-negative, got {count}")

        # Generate count copies of body
        if count == 0:
            # Empty sequence - return zero as a placeholder
            return Var("@zero")
        elif count == 1:
            return body_ast
        else:
            # Build a Seq with count copies
            return Seq([body_ast for _ in range(count)])

    elif name == "seq_cons":
        # seq_cons(expr, rest) - prepend expr to a sequence
        if len(args) != 2:
            raise TypeError(f"seq_cons expects 2 arguments, got {len(args)}")

        expr_ast, rest_ast = args

        # If rest is a Seq, prepend to it
        if isinstance(rest_ast, Seq):
            return Seq([expr_ast] + rest_ast.exprs)
        elif isinstance(rest_ast, Var) and rest_ast.name == "()":
            # Empty sequence - just return expr
            return expr_ast
        else:
            # Make a 2-element sequence
            return Seq([expr_ast, rest_ast])

    # ============================================================
    # AST Construction Primitives
    # ============================================================

    elif name == "@var":
        # @var(name_var) - create Var node using the name from name_var
        if len(args) != 1:
            raise TypeError(f"@var expects 1 argument, got {len(args)}")
        name_var = args[0]
        if isinstance(name_var, Var):
            # Create new Var with this name
            return Var(name_var.name)
        else:
            raise TypeError(f"@var expects Var argument, got {type(name_var).__name__}")

    elif name == "@app":
        # @app(fn, arg) - create App node
        if len(args) != 2:
            raise TypeError(f"@app expects 2 arguments, got {len(args)}")
        fn_expr, arg_expr = args
        return App(fn_expr, arg_expr)

    elif name == "@lam":
        # @lam(param_name_var, body) - create Lam node
        if len(args) != 2:
            raise TypeError(f"@lam expects 2 arguments, got {len(args)}")
        param_var, body_expr = args
        if isinstance(param_var, Var):
            return Lam(param_var.name, body_expr)
        else:
            raise TypeError(f"@lam expects Var as first argument, got {type(param_var).__name__}")

    elif name == "@field_access":
        # @field_access(record, field_name_var) - create FieldAccess node
        if len(args) != 2:
            raise TypeError(f"@field_access expects 2 arguments, got {len(args)}")
        record_expr, field_var = args
        if isinstance(field_var, Var):
            return FieldAccess(record_expr, field_var.name)
        else:
            raise TypeError(f"@field_access expects Var as second argument, got {type(field_var).__name__}")

    elif name == "@seq":
        # @seq(list) - create Seq node from list of expressions
        if len(args) != 1:
            raise TypeError(f"@seq expects 1 argument, got {len(args)}")
        list_expr = args[0]
        # Convert cons/nil list to Python list
        exprs = list_to_python(list_expr)
        if len(exprs) == 0:
            return Var("@zero")  # Empty sequence
        elif len(exprs) == 1:
            return exprs[0]
        else:
            return Seq(exprs)

    elif name == "@macro_invocation":
        # @macro_invocation(name_var, args_list) - create MacroInvocation node
        if len(args) != 2:
            raise TypeError(f"@macro_invocation expects 2 arguments, got {len(args)}")
        name_var, args_list = args
        if not isinstance(name_var, Var):
            raise TypeError(f"@macro_invocation expects Var as first argument, got {type(name_var).__name__}")
        # Convert cons/nil list to Python list
        macro_args = list_to_python(args_list)
        return MacroInvocation(name_var.name, macro_args)

    elif name == "@case":
        # @case(scrutinee, pat1, expr1, pat2, expr2, ...) - create Case node
        # Takes scrutinee followed by alternating pattern names (as Vars) and branch expressions
        # Bindings are assumed to be empty for all patterns
        if len(args) < 3 or len(args) % 2 != 1:
            raise TypeError(f"@case expects odd number of arguments (scrutinee + pairs of pattern/expr), got {len(args)}")
        scrutinee = args[0]
        from auric.ast import Case
        alts = {}
        # Process pairs of (pattern, expr)
        for i in range(1, len(args), 2):
            pattern_var = args[i]
            expr = args[i + 1]
            if not isinstance(pattern_var, Var):
                raise TypeError(f"@case pattern must be a Var, got {type(pattern_var).__name__}")
            alts[pattern_var.name] = ([], expr)
        return Case(scrutinee, alts)

    # ============================================================
    # AST Inspection Primitives
    # ============================================================

    elif name == "@type":
        # @type(expr) - return the AST node type as a Var
        if len(args) != 1:
            raise TypeError(f"@type expects 1 argument, got {len(args)}")
        expr = args[0]
        # Return the class name as a Var
        type_name = type(expr).__name__
        return Var(type_name)

    elif name == "@is_record":
        # @is_record(expr) - check if expr is Record
        if len(args) != 1:
            raise TypeError(f"@is_record expects 1 argument, got {len(args)}")
        expr = args[0]
        if isinstance(expr, Record):
            return Var("@true")
        else:
            return Var("@false")

    elif name == "@record_fields":
        # @record_fields(record) - get list of field values (just values, not pairs) as cons/nil
        if len(args) != 1:
            raise TypeError(f"@record_fields expects 1 argument, got {len(args)}")
        record_expr = args[0]

        # Return empty list if not a Record (allows graceful handling in macros)
        if not isinstance(record_expr, Record):
            return Var("nil")

        # Extract indexed fields (_0, _1, _2, ...) and sort by index
        indexed_fields = []
        for field_name, field_expr in record_expr.fields.items():
            if field_name.startswith("_") and field_name[1:].isdigit():
                idx = int(field_name[1:])
                indexed_fields.append((idx, field_expr))

        indexed_fields.sort(key=lambda x: x[0])

        # Build cons/nil list of field values
        result = Var("nil")
        for _, field_expr in reversed(indexed_fields):
            # cons(field_expr, result)
            result = App(App(Var("cons"), field_expr), result)

        return result

    # ============================================================
    # Data Manipulation Primitives
    # ============================================================

    elif name == "@concat":
        # @concat(var1, var2) - concatenate two variable names
        if len(args) != 2:
            raise TypeError(f"@concat expects 2 arguments, got {len(args)}")
        var1, var2 = args
        if isinstance(var1, Var) and isinstance(var2, Var):
            # Concatenate the names
            return Var(var1.name + var2.name)
        else:
            raise TypeError(f"@concat expects Var arguments, got {type(var1).__name__} and {type(var2).__name__}")

    elif name == "@to_string":
        # @to_string(nat) - convert nat to string representation (as Var)
        if len(args) != 1:
            raise TypeError(f"@to_string expects 1 argument, got {len(args)}")
        nat_expr = args[0]

        # Evaluate the nat to get its value
        from auric.evaluator import eval_exp, Heap
        env = make_comptime_env()
        result = eval_exp(nat_expr, env)
        count = value_to_int(result.data)
        Heap.drop(result)

        # Return as Var with the number as a string
        return Var(str(count))

    elif name == "@fold_right":
        # @fold_right(list, init, fn) - right fold over list
        if len(args) != 3:
            raise TypeError(f"@fold_right expects 3 arguments, got {len(args)}")
        list_expr, init_expr, fn_expr = args

        # Convert cons/nil list to Python list
        elements = list_to_python(list_expr)

        # Fold from right to left
        acc = init_expr
        for elem in reversed(elements):
            # Apply fn to elem and acc: fn(elem)(acc)
            acc = App(App(fn_expr, elem), acc)

        return acc

    elif name == "@map":
        # @map(list, fn) - map function over list
        if len(args) != 2:
            raise TypeError(f"@map expects 2 arguments, got {len(args)}")
        list_expr, fn_expr = args

        # Convert cons/nil list to Python list
        elements = list_to_python(list_expr)

        # Map fn over each element
        mapped = []
        for elem in elements:
            # Apply fn to elem: fn(elem)
            mapped.append(App(fn_expr, elem))

        # Convert back to cons/nil list
        result = Var("nil")
        for elem in reversed(mapped):
            result = App(App(Var("cons"), elem), result)

        return result

    elif name == "@list":
        # @list(elem1, elem2, ...) - create cons/nil list from elements
        # Build cons/nil list from arguments
        result = Var("nil")
        for elem in reversed(args):
            result = App(App(Var("cons"), elem), result)
        return result

    else:
        raise ValueError(f"Unknown compile-time builtin: {name}")


def list_to_python(list_expr: Exp) -> List[Exp]:
    """Convert a cons/nil list AST to a Python list of expressions."""
    elements = []
    current = list_expr

    while True:
        if isinstance(current, Var) and current.name == "nil":
            # End of list
            break
        elif isinstance(current, App):
            # Check if this is cons(elem, rest) in multi-arg form
            if isinstance(current.fn, Var) and current.fn.name == "cons":
                # Extract element and rest from multi-arg cons
                if len(current.args) == 2:
                    elem = current.args[0]
                    rest = current.args[1]
                    elements.append(elem)
                    current = rest
                    continue

            # Not a cons list - bail out
            raise TypeError(f"Expected cons/nil list, got {type(current).__name__}")
        else:
            raise TypeError(f"Expected cons/nil list, got {type(current).__name__}")

    return elements


def value_to_int(val: Any) -> int:
    """Convert a runtime value to an integer."""
    # Handle Peano numerals
    if val == "@zero" or (isinstance(val, tuple) and val[0] == "@zero"):
        return 0
    if val == "zero" or (isinstance(val, tuple) and val[0] == "zero"):
        return 0
    if isinstance(val, tuple) and len(val) >= 2:
        tag = val[0]
        if tag == "@succ" or tag == "succ":
            # Recursive succ
            return 1 + value_to_int(val[1])
        if tag == "int":
            # Integer literal
            return val[1]

    # Handle direct integers
    if isinstance(val, int):
        return val

    raise TypeError(f"Cannot convert value to int: {val}")


def try_match_pattern(scr: Exp, alts: Dict[str, tuple[List[str], Exp]],
                      ast_env: Dict[str, Exp], macros: Dict[str, MacroDef]) -> Exp | None:
    """Try to match scrutinee against patterns at compile-time.

    Returns the evaluated branch if we can match, None otherwise.
    """

    # Extract the constructor tag from scrutinee
    tag = None
    bound_values = []

    if isinstance(scr, Var):
        # Simple constructor: zero, true, false
        tag = scr.name
        bound_values = []
    elif isinstance(scr, App):
        # Constructor application: succ(n), Cons(h, t)
        # Extract tag and arguments
        tag, bound_values = extract_constructor(scr)

    if tag is None:
        # Can't match at compile-time
        return None

    # Look for matching alternative
    if tag not in alts:
        return None

    binds, rhs = alts[tag]

    # Check that we have the right number of bound values
    if len(binds) != len(bound_values):
        return None

    # Create new environment with pattern bindings
    new_env = {**ast_env}
    for bind_name, bind_value in zip(binds, bound_values):
        new_env[bind_name] = bind_value

    # Evaluate the right-hand side with the new bindings
    return eval_comptime(rhs, new_env, macros, depth + 1)


def extract_constructor(e: Exp) -> tuple[str | None, List[Exp]]:
    """Extract constructor tag and arguments from an expression.

    Examples:
        zero -> ("zero", [])
        succ(zero) -> ("succ", [zero])
        succ(succ(x)) -> ("succ", [succ(x)])
    """
    if isinstance(e, Var):
        return (e.name, [])

    if isinstance(e, App):
        # Get the function (should be a constructor)
        if isinstance(e.fn, Var):
            # Constructor application: succ(x) or cons(x, y)
            # With multi-arg, all arguments are in the args list
            return (e.fn.name, e.args)

    return (None, [])


def needs_evaluation(e: Exp, ast_env: Dict[str, Exp]) -> bool:
    """Check if an expression needs compile-time evaluation."""
    # Simple heuristic: if it's a macro parameter or contains param() calls
    if isinstance(e, Var) and e.name in ast_env:
        return True
    if isinstance(e, App) and isinstance(e.fn, Var) and e.fn.name in ast_env:
        return True
    # Also evaluate builtin constructors like @true, @false, @zero, nil
    if isinstance(e, Var) and e.name in ("@true", "@false", "@zero", "nil", "()", "true", "false"):
        return True
    return False


def evaluate_to_bool(e: Exp, ast_env: Dict[str, Exp]) -> bool:
    """Evaluate an AST expression to a boolean value at compile-time."""
    from auric.evaluator import eval_exp, Heap

    # Create environment with basic constructors
    env = make_comptime_env()

    # Evaluate the AST
    result = eval_exp(e, env)

    # Check if it's a boolean constructor
    if isinstance(result.data, tuple) and len(result.data) > 0:
        tag = result.data[0]
        Heap.drop(result)
        return tag == "@true" or tag == "true"
    elif isinstance(result.data, str):
        is_true = result.data == "@true" or result.data == "true"
        Heap.drop(result)
        return is_true
    else:
        Heap.drop(result)
        raise TypeError(f"Expected boolean at compile-time, got {result.data}")


def evaluate_ast_to_ast(ast: Exp) -> Exp:
    """Evaluate an AST expression at compile-time and convert result back to AST."""
    from auric.evaluator import eval_exp, Heap

    # Create environment with basic constructors
    env = make_comptime_env()

    # Evaluate the AST
    result = eval_exp(ast, env)

    # Convert the result back to AST
    ast_result = value_to_ast(result.data)

    # Clean up
    Heap.drop(result)

    return ast_result


def make_comptime_env():
    """Create a compile-time environment with basic constructors."""
    from auric.evaluator import Heap

    env = {}

    # @zero constructor
    env["@zero"] = Heap.alloc(("@zero",))

    # @succ constructor
    def succ_fn(n):
        return Heap.alloc(("@succ", n))
    env["@succ"] = Heap.alloc(succ_fn)

    # @true/@false constructors
    env["@true"] = Heap.alloc(("@true",))
    env["@false"] = Heap.alloc(("@false",))

    # nil/cons constructors for lists
    env["nil"] = Heap.alloc(("nil",))

    def cons_fn(x):
        def cons_fn2(xs):
            return Heap.alloc(("cons", x, xs))
        return Heap.alloc(cons_fn2)
    env["cons"] = Heap.alloc(cons_fn)

    # unit constructor
    env["()"] = Heap.alloc(("unit",))

    return env


def value_to_ast(val: Any) -> Exp:
    """Convert a runtime value back to AST representation."""

    # Tuple with tag (constructor application)
    if isinstance(val, tuple) and len(val) > 0:
        tag = val[0]

        # Boolean constructors
        if tag == "@true" or tag == "true":
            return Var("@true")
        if tag == "@false" or tag == "false":
            return Var("@false")

        # Natural number constructors
        if tag == "@zero" or tag == "zero":
            return Var("@zero")
        if tag == "@succ" or tag == "succ":
            # @succ(n)
            inner = value_to_ast(val[1]) if len(val) > 1 else Var("@zero")
            return App(Var("@succ"), inner)

        # Integer literal
        if tag == "int":
            value, type_suffix = val[1], val[2]
            return Const(value, ShapeT(Base(type_suffix)))

        # Float literal
        if tag == "float":
            value, type_suffix = val[1], val[2]
            return Const(value, ShapeT(Base(type_suffix)))

        # Unknown constructor - try to preserve
        raise TypeError(f"Cannot convert value to AST: {val}")

    # String value
    if isinstance(val, str):
        # Try as constructor
        return Var(val)

    # Integer
    if isinstance(val, int):
        return Const(val, ShapeT(Base("i64")))

    # Float
    if isinstance(val, float):
        return Const(val, ShapeT(Base("f64")))

    raise TypeError(f"Cannot convert value to AST: {val}")


def expand_macro_invocation(macro: MacroDef, args: List[Exp], macros: Dict[str, MacroDef]) -> Exp:
    """Expand a single macro invocation.

    This is where the magic happens:
    1. Arguments are quoted (become AST values)
    2. Macro body is evaluated at compile-time (comptime)
    3. param() calls force evaluation of AST
    4. Result is the generated AST
    """
    if len(args) != len(macro.params):
        raise TypeError(f"Macro {macro.name} expects {len(macro.params)} arguments, got {len(args)}")

    # Create environment mapping param names to their AST values
    ast_env = {}
    for param, arg in zip(macro.params, args):
        ast_env[param] = arg

    # Evaluate the macro body at compile-time (comptime mode)
    # This allows the macro to execute code, evaluate conditions, etc.
    result = eval_comptime(macro.body, ast_env, macros, 0)

    # If the result is a MacroInvocation, return it as-is (it will be expanded in the next pass)
    # This handles cases like @for macro that defers expansion via @macro_invocation
    if isinstance(result, MacroInvocation):
        return result

    # Expand any macros in the result
    return expand_expr(result, macros)


def substitute(e: Exp, subst: Dict[str, Exp]) -> Exp:
    """Substitute variables in an expression.

    This implements the AST construction mode where:
    - References to macro parameters are replaced with their argument ASTs
    - Everything else is left as-is (it constructs AST)
    """

    if isinstance(e, Var):
        if e.name in subst:
            # This is a macro parameter - substitute it
            return subst[e.name]
        return e

    if isinstance(e, Lam):
        # Don't substitute bound variables (shadow any params in subst)
        params_in_subst = [p for p in e.params if p in subst]
        if params_in_subst:
            # Shadow the substitutions for bound parameters
            new_subst = {k: v for k, v in subst.items() if k not in e.params}
            return Lam(e.params, substitute(e.body, new_subst))
        return Lam(e.params, substitute(e.body, subst))

    if isinstance(e, App):
        return App(substitute(e.fn, subst), [substitute(arg, subst) for arg in e.args])

    if isinstance(e, TyAbs):
        return TyAbs(e.tv, substitute(e.body, subst))

    if isinstance(e, TyAppE):
        return TyAppE(substitute(e.fn, subst), e.arg_ty)

    if isinstance(e, Case):
        # Handle bound variables in patterns
        new_alts = {}
        for tag, (binds, rhs) in e.alts.items():
            # Remove bound variables from substitution (they shadow macro params)
            new_subst = {k: v for k, v in subst.items() if k not in binds}
            new_alts[tag] = (binds, substitute(rhs, new_subst))
        return Case(substitute(e.scr, subst), new_alts)

    if isinstance(e, Perform):
        return Perform(e.effect_name, substitute(e.args, subst))

    if isinstance(e, Handle):
        return Handle(
            substitute(e.body, subst),
            {eff: (binds, substitute(handler, subst))
             for eff, (binds, handler) in e.handlers.items()}
        )

    if isinstance(e, Record):
        return Record({name: substitute(val, subst) for name, val in e.fields.items()})

    if isinstance(e, FieldAccess):
        return FieldAccess(substitute(e.record, subst), e.field)

    if isinstance(e, If):
        return If(
            substitute(e.cond, subst),
            substitute(e.then_branch, subst),
            substitute(e.else_branch, subst)
        )

    if isinstance(e, Seq):
        return Seq([substitute(expr, subst) for expr in e.exprs])

    # Base cases: literals, etc.
    return e
