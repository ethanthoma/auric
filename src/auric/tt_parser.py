"""Parser integration for token tree macros.

This module provides a wrapper around the existing parser that first
expands token tree macros before parsing.
"""

from typing import Dict
from auric.ast import Type, Exp
from auric.lexer import lex
from auric.token_tree import group_tokens, ungroup_tokens
from auric.tt_macros import collect_tt_macros, expand_tt_macros
from auric.parser import parse as old_parse


def parse_with_tt_macros(src: str) -> tuple[Dict[str, Type], Dict[str, Exp]]:
    """Parse Auric source with token tree macro expansion.

    Pipeline:
    1. Tokenize source
    2. Group tokens into token tree
    3. Collect macro definitions
    4. Expand macros on token trees
    5. Ungroup back to tokens
    6. Convert to source string
    7. Parse with existing parser

    Returns:
        (type_signatures, expressions)
    """
    # Step 1: Tokenize entire source
    tokens = lex(src)

    # Step 2: Group into token tree
    tt = group_tokens(tokens)

    # Step 3: Collect macro definitions
    macros, other_defs = collect_tt_macros(tt)

    if macros:
        print(f"✓ Found {len(macros)} token tree macros")

        # Step 4: Expand macros on remaining definitions
        from auric.token_tree import TTSequence
        expanded_tt = expand_tt_macros(TTSequence(other_defs), macros)

        # Step 5: Ungroup back to tokens
        expanded_tokens = ungroup_tokens(expanded_tt)

        # Step 6: Convert tokens back to source string
        # Join with spaces but handle special cases
        result = []
        for i, tok in enumerate(expanded_tokens):
            if i > 0:
                prev = expanded_tokens[i-1]
                # Add newline before 'const' (start of new definition)
                if tok == 'const' and i > 0:
                    result.append('\n')
                # No space between . and {  (for record syntax .{...})
                # No space between ( and next token
                # No space before ) or }
                elif not (prev == '.' and tok == '{' or
                         prev == '(' or
                         tok in (')', '}', ',', ';') or
                         prev in (',', ';')):
                    result.append(' ')
            result.append(tok)
        expanded_src = ''.join(result)
        print(f"✓ Expanded token tree macros")
    else:
        # No macros - use original source
        expanded_src = src

    # Step 7: Parse with existing parser
    return old_parse(expanded_src)
