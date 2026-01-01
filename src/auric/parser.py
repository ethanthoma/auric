"""Parser for Auric source code."""

from __future__ import annotations

from typing import Dict, List, Optional

from auric.ast import (
    App,
    Arrow,
    Base,
    Bot,
    Case,
    Diff,
    Exp,
    FieldAccess,
    Forall,
    Handle,
    Inter,
    Lam,
    Perform,
    Record,
    RecordT,
    RefT,
    ShapeT,
    TyApp,
    TyAppE,
    TyAbs,
    TyVar,
    Top,
    Type,
    Union,
    Var,
    Shape,
)
from auric.lexer import Buf, lex, TYPE_ID, VAR_ID


def parse_type(src: str) -> Type:
    b = Buf(lex(src))
    t = _ty(b)
    if b.peek() is not None:
        raise SyntaxError("junk in type")
    return t


def _ty(b: Buf, minp=0) -> Type:
    lhs = _ty_atom(b)
    # collect postfix type-application  (left-assoc)
    while True:
        nxt = b.peek()
        if nxt is None or nxt in {")", "]", "->", ",", "|", "}"}:
            break
        arg = _ty_atom(b)
        lhs = TyApp(lhs, arg)
    # right-assoc, lowest prec
    while b.peek() == "->" and minp <= 1:
        b.pop()
        rhs = _ty(b, 1)
        lhs = Arrow(lhs, rhs)
    return lhs


def _shape_expr(b: Buf, minp=0) -> Shape:
    lhs = _shape_atom(b)
    prec = lambda op: 1 if op == "∪" else 2 if op == "∩" else 0
    while b.peek() in {"∪", "∩"} and prec(b.peek()) >= minp:
        op = b.pop()
        rhs = _shape_expr(b, prec(op) + 1)
        lhs = Union(lhs, rhs) if op == "∪" else Inter(lhs, rhs)
    return lhs


def shape_of(ty: Type) -> Optional[Shape]:
    """Return the top-level Shape constructor of a type, if any."""
    from auric.ast import DepApp, Base

    if isinstance(ty, ShapeT):
        return ty.shape
    if isinstance(ty, TyApp):
        return shape_of(ty.head)
    if isinstance(ty, RefT):
        return ty.shape
    if isinstance(ty, DepApp):
        return Base(ty.base)
    return None


def _shape_atom(b: Buf) -> Shape:
    t = b.pop()
    if t == "⊤":
        return Top()
    if t == "⊥":
        return Bot()
    if t == "(":
        s = _shape_expr(b)
        b.pop()
        return s
    if b.peek() == "\\":
        b.pop()
        return Diff(Base(t), b.pop())
    # Handle builtin types (@Nat, @Bool, etc.) and regular types
    if t.startswith("@") or TYPE_ID.match(t):
        return Base(t)
    raise SyntaxError("bad shape token " + t)


def split_app(t: Type) -> tuple[Shape, List[Type]] | None:
    """
    Decompose a fully-applied data type into

        (base_shape, [arg1, arg2, …])

    e.g.   List a       →  (Base("List"), [TyVar("a")])
           Map k v      →  (Base("Map"),  [k, v])
    """
    args: List[Type] = []
    while isinstance(t, TyApp):
        args.append(t.arg)
        t = t.head
    if isinstance(t, ShapeT):
        return (t.shape, list(reversed(args)))
    return None


def _parse_index(b: Buf) -> "Index":
    """Parse a type-level index: @zero, @succ(idx), n, _, or integer literal

    Examples:
        @zero          -> IdxZero()
        @succ(@zero)   -> IdxSucc(IdxZero())
        3             -> IdxSucc(IdxSucc(IdxSucc(IdxZero())))
        n             -> IdxVar("n")
        _             -> IdxUnknown()
    """
    from auric.ast import IdxZero, IdxSucc, IdxVar, IdxUnknown

    tok = b.peek()
    if tok is None:
        raise SyntaxError("Expected index")

    if tok == "@zero":
        b.pop()
        return IdxZero()
    elif tok == "@succ":
        b.pop()
        if b.pop() != "(":
            raise SyntaxError("Expected '(' after @succ")
        # Recursively parse nested index
        inner_idx = _parse_index(b)
        if b.pop() != ")":
            raise SyntaxError("Expected ')' after @succ index")
        return IdxSucc(inner_idx)
    elif tok == "_":
        b.pop()
        return IdxUnknown()
    elif tok.isdigit():
        # Integer literal: convert to Peano numeral
        # 0 -> @zero, 1 -> @succ(@zero), 2 -> @succ(@succ(@zero)), etc.
        b.pop()
        n = int(tok)
        result = IdxZero()
        for _ in range(n):
            result = IdxSucc(result)
        return result
    elif VAR_ID.match(tok):
        b.pop()
        return IdxVar(tok)
    else:
        raise SyntaxError(f"Invalid index: {tok}")


def _ty_atom(b: Buf) -> Type:
    t = b.pop()
    if t in {"∀", "Lambda"}:
        tv = b.pop()
        if not VAR_ID.match(tv):
            raise SyntaxError("type var lower-case")
        if b.pop() != ".":
            raise SyntaxError("need '.' after ∀")
        return Forall(tv, _ty(b))
    if t == "(":
        inner = _ty(b)
        b.pop()
        return inner
    if t == ".":
        # Record type: .{ x: Int, y: String } or .{ Int, String }
        if b.peek() != "{":
            raise SyntaxError(f"Expected '{{' after '.', got {b.peek()}")
        b.pop()  # consume "{"

        fields = {}
        field_index = 0

        while b.peek() != "}":
            # Check if this is labeled or unlabeled
            # Peek ahead to see if there's a ":"
            field_tokens = []
            while b.peek() not in {",", "}", None}:
                field_tokens.append(b.pop())

            if not field_tokens:
                raise SyntaxError("Empty field in record type")

            # Check if it's labeled (contains ":")
            if ":" in field_tokens:
                colon_idx = field_tokens.index(":")
                field_name = "".join(field_tokens[:colon_idx]).strip()
                type_tokens = field_tokens[colon_idx + 1:]
                field_type = _ty(Buf(type_tokens))
            else:
                # Unlabeled - use _0, _1, _2, ...
                field_name = f"_{field_index}"
                field_type = _ty(Buf(field_tokens))
                field_index += 1

            fields[field_name] = field_type

            # Check for comma
            if b.peek() == ",":
                b.pop()

        b.pop()  # consume "}"
        return RecordT(fields)
    if t == "{":
        shp = _shape_expr(b)
        b.pop()
        pred = []
        while b.peek() != "}":
            pred.append(b.pop())
        b.pop()
        return RefT(shp, " ".join(pred))
    # Handle builtin type constructors (@Nat, @Bool, etc.) and regular types
    if t.startswith("@") or TYPE_ID.match(t):
        # Check for dependent type application: F[T, n] (e.g., Vec[Int, 3])
        # This is a generic construct that can be used for any dependent type
        if b.peek() == "[":
            from auric.ast import DepApp, IdxZero, IdxSucc, IdxVar, IdxUnknown

            b.pop()  # consume "["

            # Parse arguments until ]
            type_args = []
            index_args = []

            while b.peek() != "]":
                # Check if this is an index (number or identifier starting with lowercase)
                tok = b.peek()

                if tok is None:
                    raise SyntaxError(f"Unexpected end of input in {t}[...] type")

                # Try to parse as index first (for Nat-level values)
                if tok in {"@zero", "@succ", "_"} or (VAR_ID.match(tok) if tok else False):
                    # Parse as index using helper
                    idx = _parse_index(b)
                    index_args.append(idx)
                else:
                    # Parse as type
                    ty = _ty_atom(b)
                    type_args.append(ty)

                # Check for comma
                if b.peek() == ",":
                    b.pop()

            b.pop()  # consume "]"

            return DepApp(t, type_args, index_args)
        return ShapeT(Base(t))
    if VAR_ID.match(t):
        return TyVar(t)
    raise SyntaxError("bad type token " + t)


def parse_expr(src: str) -> Exp:
    return _expr(Buf(lex(src)))


def _expr(b: Buf) -> Exp:
    lhs = _atom(b)
    while True:
        nxt = b.peek()

        # Handle function calls with parenthesized arguments: f(arg1, arg2, ...)
        if nxt == "(":
            b.pop()  # consume "("
            # Parse comma-separated arguments until we hit ")"
            # All arguments in (...) are values, not types
            # Use [...] for type application instead
            args = []
            while b.peek() != ")":
                # Parse term argument expression
                # Collect tokens for this argument (until comma or close paren)
                arg_tokens = []
                paren_depth = 0
                while True:
                    tok = b.peek()
                    if tok is None:
                        break
                    if paren_depth == 0 and tok in {",", ")"}:
                        break
                    arg_tokens.append(b.pop())
                    if tok == "(":
                        paren_depth += 1
                    elif tok == ")":
                        paren_depth -= 1

                # Parse the collected tokens as an expression
                if arg_tokens:
                    arg = _expr(Buf(arg_tokens))
                    args.append(arg)

                # Check for comma separator
                if b.peek() == ",":
                    b.pop()  # consume ","

            b.pop()  # consume ")"
            # Create single multi-arg App node
            if args:
                lhs = App(lhs, args)
            continue

        # Handle field access: rec.field
        if nxt == ".":
            b.pop()  # consume "."
            field_name = b.peek()
            if field_name is None:
                raise SyntaxError("Expected field name after '.'")
            # Check if it's a field name (either VAR_ID or _N pattern)
            if VAR_ID.match(field_name) or field_name.startswith("_"):
                b.pop()
                lhs = FieldAccess(lhs, field_name)
                continue
            else:
                raise SyntaxError(f"Invalid field name: {field_name}")

        # Handle array indexing: vec[i] → MacroInvocation("index", [vec, i])
        # For now, only support simple numeric indices: vec[0], vec[1], etc.
        if nxt == "[":
            from auric.ast import MacroInvocation, Var

            b.pop()  # consume "["
            index_tok = b.peek()
            if index_tok is None or index_tok == "]":
                raise SyntaxError("Empty index in []")

            # For now, only support single-token numeric indices
            if not index_tok.isdigit():
                raise SyntaxError(f"Array indices must be numeric literals, got: {index_tok}")

            b.pop()  # consume index
            if b.peek() != "]":
                raise SyntaxError(f"Expected ']' after index, got: {b.peek()}")
            b.pop()  # consume "]"

            # Create a special Var with the index value
            # The macro expander will convert this to field access
            index_var = Var(index_tok)
            lhs = MacroInvocation("index", [lhs, index_var])
            continue

            # Handle pattern matching: value => { pattern -> expr; ... }
        if nxt == "=>":
            # Peek ahead to see if this is a pattern match (=> {) or end of expression
            b.pop()  # consume "=>"
            if b.peek() == "{":
                # Pattern match: value => { pattern -> expr }
                b.pop()  # consume "{"

                # Collect all tokens inside the braces
                brace_tokens = []
                brace_depth = 1
                while brace_depth > 0:
                    tok = b.peek()
                    if tok is None:
                        raise SyntaxError("Unclosed '{' in pattern match")
                    if tok == "{":
                        brace_depth += 1
                        brace_tokens.append(b.pop())
                    elif tok == "}":
                        brace_depth -= 1
                        if brace_depth > 0:
                            brace_tokens.append(b.pop())
                        else:
                            b.pop()  # consume final "}"
                    else:
                        brace_tokens.append(b.pop())

                # Parse the pattern block
                case_expr = _parse_pattern_block(brace_tokens, is_multiline=True)

                # Replace the placeholder scrutinee with the actual value
                # The _parse_pattern_block returns Case(Var("_scrutinee"), alts)
                # We need to replace it with Case(lhs, alts)
                if isinstance(case_expr, Case):
                    lhs = Case(lhs, case_expr.alts)
                else:
                    raise SyntaxError("Internal error: expected Case from pattern block")
                continue
            else:
                # Not a pattern match, this is the end of expression
                raise SyntaxError("Pattern match requires braces: use 'value => { pattern -> expr }'")

        if nxt and nxt not in {")", "]", "->", "=>", "of", "\n", ","} and nxt != "}":
            # Check if next token is a type constructor (for C-style type arguments in implicit application)
            if TYPE_ID.match(nxt):
                # Type argument - likely from space-separated application like f Nat x
                type_token = b.pop()
                type_tokens = [type_token]
                # Handle generic type arguments
                while b.peek() == "(":
                    paren_depth = 1
                    type_tokens.append(b.pop())  # Add "("
                    while paren_depth > 0:
                        tok = b.pop()
                        type_tokens.append(tok)
                        if tok == "(":
                            paren_depth += 1
                        elif tok == ")":
                            paren_depth -= 1
                ty = parse_type(" ".join(type_tokens))
                lhs = TyAppE(lhs, ty)
                continue
            # Regular term argument (space-separated application: f x)
            lhs = App(lhs, [_atom(b)])
            continue
        if nxt == "[":
            b.pop()
            tokens = []
            depth = 1
            while depth:
                tok = b.pop()
                if tok == "[":
                    depth += 1
                elif tok == "]":
                    depth -= 1
                if depth:
                    tokens.append(tok)
            lhs = TyAppE(lhs, parse_type(" ".join(tokens)))
            continue
        break
    return lhs


def _parse_block(tokens: List[str]) -> tuple[Exp, bool]:
    """Parse a block expression { ... } and detect its type."""
    if not tokens or (len(tokens) == 1 and tokens[0] == ""):
        raise SyntaxError("Empty block")

    is_multiline = "\n" in " ".join(tokens)
    tokens_no_newlines = [t for t in tokens if t != "\n"]

    if not tokens_no_newlines:
        raise SyntaxError("Empty block")

    has_arrow = "->" in tokens_no_newlines
    has_let_return = "let" in tokens_no_newlines or "return" in tokens_no_newlines

    is_record = False
    if not has_arrow and not has_let_return and tokens_no_newlines:
        first = tokens_no_newlines[0]
        if (VAR_ID.match(first) or first == "_") and len(tokens_no_newlines) > 1:
            if tokens_no_newlines[1] in {":", "="}:
                is_record = True

    if has_arrow:
        return _parse_pattern_block(tokens, is_multiline), is_multiline
    elif has_let_return:
        return _parse_let_return_block(tokens, is_multiline), is_multiline
    elif is_record:
        return _parse_record_block(tokens, is_multiline), is_multiline
    else:
        return _expr(Buf(tokens)), is_multiline


def _parse_pattern(pattern_str: str) -> tuple[str, List[str]]:
    """Extract constructor name and bound variables from a pattern string.

    Examples:
        "zero" -> ("zero", [])
        "succ x" -> ("succ", ["x"])
        "succ ( x )" -> ("succ", ["x"])
        "Cons h t" -> ("Cons", ["h", "t"])
        "Cons ( h ) ( t )" -> ("Cons", ["h", "t"])
    """
    tokens = pattern_str.split()
    if not tokens:
        raise SyntaxError("Empty pattern")

    ctor = tokens[0]
    binds = []

    # Filter out parentheses and commas, collect variable names
    for tok in tokens[1:]:
        if tok not in {"(", ")", ","}:
            binds.append(tok)

    return ctor, binds


def _fix_scrutinee(exp: Exp, old_var: str, new_var: str) -> Exp:
    """Replace variable references in an expression (for fixing pattern match scrutinees)."""
    if isinstance(exp, Var):
        return Var(new_var) if exp.name == old_var else exp
    if isinstance(exp, Lam):
        if new_var in exp.params:
            return exp
        return Lam(exp.params, _fix_scrutinee(exp.body, old_var, new_var))
    if isinstance(exp, App):
        return App(_fix_scrutinee(exp.fn, old_var, new_var), [_fix_scrutinee(arg, old_var, new_var) for arg in exp.args])
    if isinstance(exp, TyAbs):
        return TyAbs(exp.tv, _fix_scrutinee(exp.body, old_var, new_var))
    if isinstance(exp, TyAppE):
        return TyAppE(_fix_scrutinee(exp.fn, old_var, new_var), exp.arg_ty)
    if isinstance(exp, Case):
        return Case(
            _fix_scrutinee(exp.scr, old_var, new_var),
            {tag: (binds, _fix_scrutinee(body, old_var, new_var)) for tag, (binds, body) in exp.alts.items()},
        )
    return exp


def _parse_pattern_block(tokens: List[str], is_multiline: bool) -> Exp:
    """Parse pattern matching block: { pattern -> expr; pattern -> expr }"""
    tokens = [t for t in tokens if t != "\n"]

    if not tokens:
        raise SyntaxError("Empty pattern block")

    alts = {}
    i = 0

    while i < len(tokens):
        if tokens[i] == "}":
            break

        pattern_tokens = []
        while i < len(tokens) and tokens[i] != "->":
            pattern_tokens.append(tokens[i])
            i += 1

        if i >= len(tokens):
            raise SyntaxError("Expected '->' in pattern match")

        i += 1

        expr_tokens = []
        while i < len(tokens) and tokens[i] not in {";", "}"}:
            expr_tokens.append(tokens[i])
            i += 1

        pattern_str = " ".join(pattern_tokens).strip()
        ctor, binds = _parse_pattern(pattern_str)
        expr = _expr(Buf(expr_tokens)) if expr_tokens else Var("()")

        alts[ctor] = (binds, expr)

        has_trailing_sep = i < len(tokens) and tokens[i] == ";"
        is_last_clause = i + 1 >= len(tokens) or tokens[i + 1] == "}"

        if is_multiline and is_last_clause and not has_trailing_sep:
            raise SyntaxError("Multiline pattern block requires trailing ';' after last clause")

        if i < len(tokens) and tokens[i] == ";":
            i += 1

    if not alts:
        raise SyntaxError("Empty pattern block")

    return Case(Var("_scrutinee"), alts)


def _parse_let_return_block(tokens: List[str], is_multiline: bool) -> Exp:
    """Parse let/return block: { let x = expr; let y = expr; return expr }"""
    tokens = [t for t in tokens if t != "\n"]

    bindings = []
    result_expr = None
    i = 0

    while i < len(tokens):
        if tokens[i] == "}":
            break

        if tokens[i] == "let":
            i += 1
            if i >= len(tokens):
                raise SyntaxError("Expected binding name after 'let'")

            name = tokens[i]
            i += 1

            if i >= len(tokens) or tokens[i] != "=":
                raise SyntaxError(f"Expected '=' after binding name '{name}'")

            i += 1

            expr_tokens = []
            while i < len(tokens) and tokens[i] not in {";", "}", "return"}:
                expr_tokens.append(tokens[i])
                i += 1

            bound_expr = _expr(Buf(expr_tokens)) if expr_tokens else Var(name)
            bindings.append((name, bound_expr))

            if i < len(tokens) and tokens[i] == ";":
                i += 1

        elif tokens[i] == "return":
            i += 1
            expr_tokens = []
            while i < len(tokens) and tokens[i] not in {";", "}"}:
                expr_tokens.append(tokens[i])
                i += 1

            result_expr = _expr(Buf(expr_tokens)) if expr_tokens else Var("()")

            if is_multiline and i < len(tokens) and tokens[i] != ";":
                if tokens[i] == "}":
                    raise SyntaxError("Multiline let/return block requires trailing ';' after last statement")

            if i < len(tokens) and tokens[i] == ";":
                i += 1
        else:
            i += 1

    if result_expr is None:
        result_expr = Var("()")

    current_expr = result_expr
    for name, value_expr in reversed(bindings):
        current_expr = Lam([name], current_expr)

    for name, value_expr in bindings:
        current_expr = App(current_expr, [value_expr])

    return current_expr


def _parse_record_block(tokens: List[str], is_multiline: bool) -> Exp:
    """Parse record literal: { x: T, y: T } or { x = val, y = val }"""
    tokens = [t for t in tokens if t != "\n"]
    # TODO: Implement full record support
    return _expr(Buf(tokens))


def _atom(b: Buf) -> Exp:
    t = b.pop()
    if t == "(":
        e = _expr(b)
        b.pop()
        return e

    # Let binding: let name = value; body or let rec name = value; body
    if t == "let":
        from auric.ast import Let

        # Parse binding name
        name = b.peek()
        if not name or not name.isidentifier():
            raise SyntaxError(f"Expected identifier after 'let', got {name}")
        b.pop()  # consume name

        # Expect '='
        if b.peek() != "=":
            raise SyntaxError(f"Expected '=' after 'let {name}', got {b.peek()}")
        b.pop()  # consume '='

        # Parse value expression (until ';')
        value_tokens = []
        brace_depth = 0
        paren_depth = 0
        while b.peek() is not None:
            tok = b.peek()
            # Stop at top-level ';'
            if tok == ";" and brace_depth == 0 and paren_depth == 0:
                break
            # Track nesting
            if tok == "{":
                brace_depth += 1
            elif tok == "}":
                brace_depth -= 1
            elif tok == "(":
                paren_depth += 1
            elif tok == ")":
                paren_depth -= 1
            value_tokens.append(b.pop())

        if b.peek() != ";":
            raise SyntaxError("Expected ';' after let value")
        b.pop()  # consume ';'

        # Parse body (rest of expression)
        body = _atom(b)

        # Parse value and body
        value = _expr(Buf(value_tokens))

        # All let bindings are recursive by default
        return Let(name, value, body)

    # Brace block: could be sequence { expr; expr } or pattern match { pat -> expr }
    if t == "{":
        # Peek ahead to see if this is a pattern match (contains ->) or sequence
        # Collect all tokens until closing }
        # Note: The '{' was already popped by _atom(), so we start from current position
        brace_depth = 1
        tokens_inside = []

        while brace_depth > 0:
            tok = b.peek()
            if tok is None:
                raise SyntaxError("Unclosed '{'")
            if tok == "{":
                brace_depth += 1
                tokens_inside.append(b.pop())
            elif tok == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    b.pop()  # consume the closing '}'
                    break
                else:
                    tokens_inside.append(b.pop())
            else:
                tokens_inside.append(b.pop())

        # Check if this contains -> (pattern match) or not (sequence)
        has_arrow = "->" in tokens_inside

        if has_arrow:
            # This is a pattern match body - delegate to existing pattern match parser
            return _parse_pattern_block(tokens_inside, is_multiline=True)
        else:
            # This is a sequence
            from auric.ast import Seq

            exprs = []
            expr_tokens = []

            for tok in tokens_inside:
                if tok == ";":
                    if expr_tokens:
                        exprs.append(_expr(Buf(expr_tokens)))
                        expr_tokens = []
                else:
                    expr_tokens.append(tok)

            # Handle last expression (no trailing semicolon)
            if expr_tokens:
                exprs.append(_expr(Buf(expr_tokens)))

            if len(exprs) == 0:
                return Var("()")
            elif len(exprs) == 1:
                return exprs[0]
            else:
                return Seq(exprs)

    if t == ".":
        # Record literal: .{ x = 1, y = 2 } or .{ 1, 2 }
        if b.peek() != "{":
            raise SyntaxError(f"Expected '{{' after '.', got {b.peek()}")
        b.pop()  # consume "{"

        fields = {}
        field_index = 0
        spread_index = 0  # For tracking spread operators

        while b.peek() != "}":
            # Check for spread operator: ..expr
            if b.peek() == "..":
                # Spread operator: ..expr
                from auric.ast import Spread
                b.pop()  # consume ".."

                # Collect tokens for spread expression until we hit "," or "}"
                spread_tokens = []
                brace_depth = 0
                paren_depth = 0
                while True:
                    tok = b.peek()
                    if tok is None:
                        raise SyntaxError("Unexpected end in spread expression")
                    if brace_depth == 0 and paren_depth == 0 and tok in {",", "}"}:
                        break
                    if tok == "{":
                        brace_depth += 1
                    elif tok == "}":
                        brace_depth -= 1
                    elif tok == "(":
                        paren_depth += 1
                    elif tok == ")":
                        paren_depth -= 1
                    spread_tokens.append(b.pop())

                if not spread_tokens:
                    raise SyntaxError("Expected expression after '..'")

                spread_expr = _expr(Buf(spread_tokens))
                # Store spread with special key
                fields[f"__spread_{spread_index}"] = Spread(spread_expr)
                spread_index += 1

                # Check for comma
                if b.peek() == ",":
                    b.pop()
                continue

            # Regular field parsing
            # Collect tokens for this field until we hit "," or "}"
            field_tokens = []
            brace_depth = 0
            while True:
                tok = b.peek()
                if tok is None:
                    raise SyntaxError("Unexpected end in record literal")
                if brace_depth == 0 and tok in {",", "}"}:
                    break
                if tok == "{":
                    brace_depth += 1
                elif tok == "}":
                    brace_depth -= 1
                field_tokens.append(b.pop())

            if not field_tokens:
                raise SyntaxError("Empty field in record literal")

            # Check if it's labeled (contains "=")
            if "=" in field_tokens:
                eq_idx = field_tokens.index("=")
                field_name = "".join(field_tokens[:eq_idx]).strip()
                value_tokens = field_tokens[eq_idx + 1:]
                field_value = _expr(Buf(value_tokens))
            else:
                # Unlabeled - use _0, _1, _2, ...
                field_name = f"_{field_index}"
                field_value = _expr(Buf(field_tokens))
                field_index += 1

            fields[field_name] = field_value

            # Check for comma
            if b.peek() == ",":
                b.pop()

        b.pop()  # consume "}"
        return Record(fields)
    if t == "Λ":
        tv = b.pop()
        b.pop()
        return TyAbs(tv, _expr(b))
    if t == "handle":
        # handle expr { Effect(pattern) -> handler; ... }
        # Collect tokens for body expression until we hit '{'
        body_tokens = []
        paren_depth = 0
        while True:
            tok = b.peek()
            if tok is None:
                raise SyntaxError("Expected '{' in handle expression")
            if tok == "{" and paren_depth == 0:
                break
            if tok == "(":
                paren_depth += 1
            elif tok == ")":
                paren_depth -= 1
            body_tokens.append(b.pop())

        body = _expr(Buf(body_tokens))
        if b.peek() != "{":
            raise SyntaxError(f"Expected '{{' in handle expression, got {b.peek()}")
        b.pop()  # consume "{"

        handlers = {}
        while b.peek() != "}":
            while b.peek() == "\n":
                b.pop()
            if b.peek() == "}":
                break

            # Parse effect name and pattern: EffectName(pattern) or EffectName()
            effect_name = b.pop()
            if not effect_name[0].isupper():
                raise SyntaxError(f"Effect name must be capitalized: {effect_name}")

            if b.peek() != "(":
                raise SyntaxError(f"Expected '(' after effect name {effect_name}")
            b.pop()  # consume "("

            # Parse pattern parameters
            binds = []
            while b.peek() != ")":
                binds.append(b.pop())
            b.pop()  # consume ")"

            if b.peek() != "->":
                raise SyntaxError(f"Expected '->' in handler")
            b.pop()  # consume "->"

            # Parse handler body (until ; or })
            rhs = []
            while b.peek() not in {None, ";", "}"}:
                rhs.append(b.pop())

            handlers[effect_name] = (binds, _expr(Buf(rhs)))

            if b.peek() == ";":
                b.pop()  # consume ";"
            while b.peek() == "\n":
                b.pop()

        b.pop()  # consume "}"
        return Handle(body, handlers)
    # Character literal: 'a'
    if t.startswith("'") and t.endswith("'") and len(t) >= 3:
        from auric.ast import Const, ShapeT, Base
        # Handle escape sequences
        char_content = t[1:-1]
        if char_content.startswith("\\"):
            # Escape sequence
            escape_map = {"\\n": "\n", "\\t": "\t", "\\r": "\r", "\\\\": "\\", "\\'": "'"}
            if char_content in escape_map:
                char_content = escape_map[char_content]
            else:
                raise SyntaxError(f"Unknown escape sequence: {char_content}")
        if len(char_content) != 1:
            raise SyntaxError(f"Character literal must contain exactly one character: {t}")
        return Const(char_content, ShapeT(Base("u8")))

    # Float literal: 3.14, 3.14f32, 2.5e10
    from auric.lexer import FLOAT_LIT
    if FLOAT_LIT.match(t):
        from auric.ast import Const, ShapeT, Base
        # Check for type suffix
        if t.endswith("f32"):
            value = float(t[:-3])
            type_suffix = "f32"
        elif t.endswith("f64"):
            value = float(t[:-3])
            type_suffix = "f64"
        else:
            # Default to f64
            value = float(t)
            type_suffix = "f64"
        return Const(value, ShapeT(Base(type_suffix)))

    # Integer literal: 42, 42u8, 0xFF, 0b1010
    from auric.lexer import INT_LIT
    if INT_LIT.match(t):
        from auric.ast import Const, ShapeT, Base
        # Check for type suffix
        type_suffix = "i64"  # default
        value_str = t
        for suffix in ["u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64"]:
            if t.endswith(suffix):
                type_suffix = suffix
                value_str = t[:-len(suffix)]
                break

        # Parse the value with appropriate base
        if value_str.startswith("0x") or value_str.startswith("0X"):
            value = int(value_str, 16)
        elif value_str.startswith("0o") or value_str.startswith("0O"):
            value = int(value_str, 8)
        elif value_str.startswith("0b") or value_str.startswith("0B"):
            value = int(value_str, 2)
        else:
            value = int(value_str)

        return Const(value, ShapeT(Base(type_suffix)))

    # Boolean literals: @true, @false
    if t == "@true":
        from auric.ast import Const, ShapeT, Base
        return Const(True, ShapeT(Base("bool")))
    if t == "@false":
        from auric.ast import Const, ShapeT, Base
        return Const(False, ShapeT(Base("bool")))

    # Builtin identifiers: @zero, @succ, @Print, etc.
    if t.startswith("@"):
        return Var(t)
    if VAR_ID.match(t):
        return Var(t)
    if TYPE_ID.match(t):
        return Var(t)
    raise SyntaxError(
        f"invalid term identifier '{t}': must be snake_case (e.g., 'my_var'), CamelCase type (e.g., 'Nat'), or builtin (@zero)"
    )


def _load_module(module_path: str) -> tuple[Dict[str, Type], Dict[str, Exp]]:
    """Load a module from the standard library or filesystem.

    Module paths like 'std/nat' are converted to 'std/nat.au' files.
    """
    from pathlib import Path

    au_file = module_path + ".au" if not module_path.endswith(".au") else module_path
    std_path = Path(__file__).parent.parent.parent / au_file
    if std_path.exists():
        src = std_path.read_text()
        return parse(src)
    raise SyntaxError(f"Module not found: {module_path}")


def parse(src: str) -> tuple[Dict[str, Type], Dict[str, Exp]]:
    """Parse Auric source code into signatures and definitions.

    Returns: (type_signatures, expressions)

    Supported forms:
    - const name : Type = expr
    - const name = (params: Type, ...) -> Type { body }
    - type Name(params) = { constructors }
    """
    sigs: Dict[str, Type] = {}
    defs: Dict[str, Exp] = {}

    lines = src.strip("\n").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and comments
        if not line or line.startswith("//"):
            i += 1
            continue

        # Import statements:
        # - import module: *              (import all)
        # - import module: name1, name2   (selective import)
        # - import module                 (import all, legacy syntax)
        if line.startswith("import "):
            import_stmt = line[7:].strip()  # Remove "import "

            # Check if selective import (contains ':')
            if ":" in import_stmt:
                # Selective import: module: name1, name2
                module_path, import_list = import_stmt.split(":", 1)
                module_path = module_path.strip()
                import_list = import_list.strip()

                # Load the module
                imported_sigs, imported_defs = _load_module(module_path)

                # Check for wildcard
                if import_list == "*":
                    # Import everything
                    sigs.update(imported_sigs)
                    defs.update(imported_defs)
                else:
                    # Import only specified names
                    names = [name.strip() for name in import_list.split(",")]
                    for name in names:
                        if name in imported_sigs:
                            sigs[name] = imported_sigs[name]
                        if name in imported_defs:
                            defs[name] = imported_defs[name]
            else:
                # Legacy import: import module (imports all)
                module_path = import_stmt
                imported_sigs, imported_defs = _load_module(module_path)
                sigs.update(imported_sigs)
                defs.update(imported_defs)

            i += 1
            continue

        # Type definitions: type Name(params) = { ... }
        if line.startswith("type "):
            # For now, skip type definitions (they don't produce defs/sigs)
            i += 1
            continue

        # Macro definitions: macro name = (params) => body
        if line.startswith("macro "):
            from auric.ast import MacroDef

            line = line[6:]  # strip "macro "

            # Extract name
            eq_pos = line.index("=")
            name = line[:eq_pos].strip()
            rest = line[eq_pos + 1:].strip()

            # rest should be: (params) => { body }
            if not rest.startswith("("):
                raise SyntaxError(f"Macro definition requires (params) => body: {line}")

            # Find parameter list
            paren_depth = 0
            paren_end = 0
            for j, ch in enumerate(rest):
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        paren_end = j
                        break

            param_str = rest[1:paren_end]  # Inside parens
            params = [p.strip() for p in param_str.split(",") if p.strip()]

            # Find =>
            after_params = rest[paren_end + 1:].strip()
            if not after_params.startswith("=>"):
                raise SyntaxError(f"Macro requires => after parameters: {line}")

            body_start = rest.index("=>") + 2
            body_str = rest[body_start:].strip()

            # Collect multi-line body if needed
            body_lines = [body_str]
            i += 1
            brace_depth = body_str.count("{") - body_str.count("}")

            while i < len(lines) and brace_depth > 0:
                line_content = lines[i]
                body_lines.append(line_content.lstrip())
                brace_depth += line_content.count("{") - line_content.count("}")
                i += 1

            full_body = "\n".join(body_lines)
            body_expr = parse_expr(full_body)

            defs[name] = MacroDef(name, params, body_expr)
            continue

        # Constant/function definitions: const name ...
        if line.startswith("const "):
            line = line[6:]  # strip "const "

            # Check for := or = for binding
            has_inferred = ":=" in line
            has_explicit = "=" in line

            if not (has_inferred or has_explicit):
                raise SyntaxError(f"const requires ':=' or '=': {line}")

            # Handle := (inferred type declaration)
            if has_inferred:
                eq_pos = line.index(":=")
                name = line[:eq_pos].strip()
                rest = line[eq_pos + 2:].strip()
            else:
                # Handle : Type = (explicit type declaration) or just = (value binding)
                eq_pos = line.index("=")
                name = line[:eq_pos].strip()
                rest = line[eq_pos + 1:].strip()

            # Check if this is a function with params: (...)  => ...
            # New syntax: const name: Type -> Type = (params) => { body }
            if rest.startswith("(") and "=>" in rest:
                # Function definition: const name: ParamTypes -> RetType = (params) => { body }
                # The type signature should be in the name part (before =)

                # Parse the type signature from name (if it has : in it)
                if " : " in name or ": " in name:
                    # Split name and type
                    colon_idx = name.index(":")
                    func_name = name[:colon_idx].strip()
                    type_str = name[colon_idx + 1:].strip()
                    fn_type = parse_type(type_str)
                    sigs[func_name] = fn_type
                    name = func_name

                    # Extract parameter and return types from the function type
                    param_types_list = []
                    current_type = fn_type
                    while isinstance(current_type, (Arrow, Forall)):
                        if isinstance(current_type, Arrow):
                            param_types_list.append(current_type.param)
                            current_type = current_type.ret
                        elif isinstance(current_type, Forall):
                            param_types_list.append(None)  # Type parameter
                            current_type = current_type.body
                else:
                    raise SyntaxError(f"Function definition requires type signature: {line}")

                # Find closing paren for parameters
                paren_depth = 0
                paren_end = 0
                for j, ch in enumerate(rest):
                    if ch == "(":
                        paren_depth += 1
                    elif ch == ")":
                        paren_depth -= 1
                        if paren_depth == 0:
                            paren_end = j
                            break

                if paren_depth != 0:
                    raise SyntaxError(f"Unmatched parentheses in function definition: {line}")

                params_str = rest[1:paren_end]
                after_params = rest[paren_end + 1:].strip()

                if not after_params.startswith("=>"):
                    raise SyntaxError(f"Expected '=>' after params: {line}")

                after_arrow = after_params[2:].strip()

                # Body must start with {
                if not after_arrow.startswith("{"):
                    raise SyntaxError(f"Function body must be in braces {{ }}: {line}")

                body_str = after_arrow.strip()

                # Collect multiline body
                rhs_lines = [body_str]
                i += 1
                brace_depth = body_str.count("{") - body_str.count("}")
                while i < len(lines) and brace_depth > 0:
                    next_line = lines[i]
                    rhs_lines.append(next_line)
                    brace_depth += next_line.count("{") - next_line.count("}")
                    i += 1

                full_body = "\n".join(rhs_lines)

                # Parse parameters from params_str
                # Just get the parameter names (types are already in the type signature)
                param_names = []
                if params_str.strip():
                    # Split parameters by comma, but respect bracket nesting
                    param_parts = []
                    current_part = []
                    bracket_depth = 0
                    paren_depth = 0
                    for ch in params_str:
                        if ch == ',' and bracket_depth == 0 and paren_depth == 0:
                            param_parts.append(''.join(current_part))
                            current_part = []
                        else:
                            if ch == '[':
                                bracket_depth += 1
                            elif ch == ']':
                                bracket_depth -= 1
                            elif ch == '(':
                                paren_depth += 1
                            elif ch == ')':
                                paren_depth -= 1
                            current_part.append(ch)
                    if current_part:
                        param_parts.append(''.join(current_part))

                    for param_part in param_parts:
                        param_part = param_part.strip()
                        # Parameter can be just a name, or name: Type
                        if ":" in param_part:
                            p_name = param_part.split(":", 1)[0].strip()
                        else:
                            p_name = param_part
                        param_names.append(p_name)

                # Parse body - keep braces so block detection works
                full_body = full_body.strip()

                # Parse body as expression (keep braces for block detection)
                body = parse_expr(full_body)

                # Determine which parameters are type parameters vs term parameters
                # by looking at the function type
                param_is_type = []
                current_type = fn_type
                while isinstance(current_type, (Arrow, Forall)):
                    if isinstance(current_type, Forall):
                        param_is_type.append(True)
                        current_type = current_type.body
                    elif isinstance(current_type, Arrow):
                        param_is_type.append(False)
                        current_type = current_type.ret
                    else:
                        break

                # Fix scrutinee in pattern matching blocks
                # If the body contains a Case with _scrutinee, replace it with the first term parameter
                if param_names:
                    # Find the first term parameter (not a type parameter)
                    for idx in range(len(param_names)):
                        if idx < len(param_is_type) and not param_is_type[idx]:
                            body = _fix_scrutinee(body, "_scrutinee", param_names[idx])
                            break

                # Wrap body in lambdas/type abstractions
                # Collect consecutive term parameters for multi-arg Lam
                # Process in reverse to maintain correct nesting
                idx = len(param_names) - 1
                while idx >= 0:
                    if idx < len(param_is_type) and param_is_type[idx]:
                        # Type parameter - wrap with TyAbs
                        body = TyAbs(param_names[idx], body)
                        idx -= 1
                    else:
                        # Term parameter - collect all consecutive term params
                        term_params = []
                        while idx >= 0 and (idx >= len(param_is_type) or not param_is_type[idx]):
                            term_params.insert(0, param_names[idx])
                            idx -= 1
                        # Create single multi-arg Lam
                        if term_params:
                            body = Lam(term_params, body)

                defs[name] = body
            else:
                # Simple constant: const name : Type = expr  OR const name = expr
                if " : " in line[:eq_pos]:
                    # Has explicit type
                    name_part, type_part = line[:eq_pos].split(" : ", 1)
                    name = name_part.strip()
                    ty_src = type_part.strip()
                    sigs[name] = parse_type(ty_src)

                # Collect RHS value
                rhs_lines = [rest]
                i += 1

                # Track brace depth to collect multi-line expressions
                brace_depth = rest.count("{") - rest.count("}")
                while i < len(lines):
                    line_content = lines[i]
                    # Stop if we hit an empty line and braces are balanced
                    if not line_content.strip() and brace_depth == 0:
                        break
                    # Stop if line doesn't start with whitespace and braces are balanced
                    if line_content and line_content[0] not in " \t" and brace_depth == 0:
                        break

                    rhs_lines.append(line_content.lstrip())
                    brace_depth += line_content.count("{") - line_content.count("}")
                    i += 1

                    # Stop once braces are balanced
                    if brace_depth == 0:
                        break

                body_src = "\n".join(rhs_lines)
                defs[name] = parse_expr(body_src)
            continue

        raise SyntaxError(f"unrecognised top-level line: {line}")

    return sigs, defs
