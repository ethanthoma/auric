"""Pattern matching for macro expansion.

Patterns can contain:
- Literal tokens that must match exactly
- $var - captures a single identifier
- $expr - captures an expression (sequence of tokens)
- $block - captures a {...} group
- ..$expr - spread operator prefix
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from auric.token_tree import TokenTree, TTToken, TTGroup, TTSequence


@dataclass
class PatternVar:
    """A pattern variable like $var, $expr, $block"""
    name: str  # The variable name (without $)
    kind: str  # 'var', 'expr', 'block'

    def __repr__(self):
        return f"${self.name}"


@dataclass
class PatternSpread:
    """A spread pattern like ..$expr"""
    name: str  # The variable name (without $ and ..)

    def __repr__(self):
        return f"..${self.name}"


@dataclass
class PatternRepeat:
    """A repetition pattern like $x*, $x+, $x?

    Attributes:
        name: Variable name (without $ and quantifier)
        kind: 'var', 'expr', 'block' - what kind of element to match
        quantifier: '*' (zero or more), '+' (one or more), '?' (zero or one)
        separator: Optional separator token between repetitions (e.g., ',')
    """
    name: str
    kind: str
    quantifier: str  # '*', '+', '?'
    separator: Optional[str] = None

    def __repr__(self):
        sep = f" sep={self.separator}" if self.separator else ""
        return f"${self.name}{self.quantifier}{sep}"


# Pattern elements
PatternElement = TokenTree | PatternVar | PatternSpread | PatternRepeat


def parse_pattern(tt: TokenTree) -> List[PatternElement]:
    """Parse a token tree into a pattern with capture variables.

    Example:
        for $var = ..$expr $block

    Becomes:
        [TTToken('for'), PatternVar('var', 'var'), TTToken('='),
         PatternSpread('expr'), PatternVar('block', 'block')]
    """
    if isinstance(tt, TTToken):
        # Check if this is a pattern variable
        if tt.value.startswith('$'):
            # Determine kind from name or context
            var_name = tt.value[1:]  # Remove $
            # Simple heuristic: $block for blocks, others are $var or $expr
            kind = 'block' if var_name == 'block' else 'var'
            return [PatternVar(var_name, kind)]
        elif tt.value.startswith('..'):
            # Spread operator
            if len(tt.value) > 2 and tt.value[2:].startswith('$'):
                var_name = tt.value[3:]  # Remove ..$
                return [PatternSpread(var_name)]
            else:
                # Not a spread pattern, just literal ..
                return [tt]
        else:
            return [tt]

    elif isinstance(tt, TTGroup):
        # Group remains as-is in pattern (for matching $block)
        return [tt]

    elif isinstance(tt, TTSequence):
        # Flatten sequence into list of pattern elements
        # Handle two-token pattern variables: $ followed by identifier
        result = []
        i = 0
        while i < len(tt.items):
            item = tt.items[i]

            # Check for $ followed by identifier (pattern variable)
            # Optionally followed by *, +, or ? (repetition quantifier)
            if (isinstance(item, TTToken) and item.value == '$' and
                i + 1 < len(tt.items)):
                next_item = tt.items[i + 1]
                if isinstance(next_item, TTToken):
                    var_name = next_item.value
                    kind = 'block' if var_name == 'block' else 'var'

                    # Check for quantifier after the variable name
                    if (i + 2 < len(tt.items) and
                        isinstance(tt.items[i + 2], TTToken) and
                        tt.items[i + 2].value in ('*', '+', '?')):
                        quantifier = tt.items[i + 2].value
                        result.append(PatternRepeat(var_name, kind, quantifier))
                        i += 3  # Skip $, name, and quantifier
                    else:
                        # Regular pattern variable without quantifier
                        result.append(PatternVar(var_name, kind))
                        i += 2  # Skip $ and name
                    continue

            # Check for .. followed by $ and identifier (spread pattern)
            if (isinstance(item, TTToken) and item.value == '..' and
                i + 2 < len(tt.items)):
                next_item = tt.items[i + 1]
                next_next = tt.items[i + 2]
                if (isinstance(next_item, TTToken) and next_item.value == '$' and
                    isinstance(next_next, TTToken)):
                    # This is a spread pattern
                    result.append(PatternSpread(next_next.value))
                    i += 3  # Skip all three tokens
                    continue

            # Regular item
            result.extend(parse_pattern(item))
            i += 1

        return result

    else:
        return [tt]


def match_pattern(pattern: List[PatternElement],
                  tt: TokenTree) -> Optional[Dict[str, TokenTree]]:
    """Try to match a pattern against a token tree.

    Args:
        pattern: List of pattern elements (from parse_pattern)
        tt: Token tree to match against

    Returns:
        Dict mapping variable names to captured token trees, or None if no match
    """
    # Convert token tree to flat list for matching
    if isinstance(tt, TTSequence):
        tokens = tt.items
    else:
        tokens = [tt]

    captures: Dict[str, TokenTree] = {}
    token_idx = 0
    pattern_idx = 0

    while pattern_idx < len(pattern) and token_idx < len(tokens):
        pat_elem = pattern[pattern_idx]

        if isinstance(pat_elem, TTToken):
            # Literal token - must match exactly
            tok = tokens[token_idx]
            if isinstance(tok, TTToken) and tok.value == pat_elem.value:
                token_idx += 1
                pattern_idx += 1
            else:
                return None  # No match

        elif isinstance(pat_elem, PatternVar):
            # Capture a single token/group
            if pat_elem.kind == 'block':
                # Must be a {...} group
                tok = tokens[token_idx]
                if isinstance(tok, TTGroup) and tok.delim == '{':
                    captures[pat_elem.name] = tok
                    token_idx += 1
                    pattern_idx += 1
                else:
                    return None  # No match
            else:
                # Capture identifier or expression
                # For now, just capture one token
                # TODO: Better expr matching
                captures[pat_elem.name] = tokens[token_idx]
                token_idx += 1
                pattern_idx += 1

        elif isinstance(pat_elem, PatternSpread):
            # Spread pattern - first match literal '..' then capture remaining tokens
            # First, match the literal '..' token
            tok = tokens[token_idx]
            if not (isinstance(tok, TTToken) and tok.value == '..'):
                return None
            token_idx += 1  # Consume the '..'

            pattern_idx += 1

            if pattern_idx >= len(pattern):
                # No more pattern elements - capture rest
                captures[pat_elem.name] = TTSequence(tokens[token_idx:])
                token_idx = len(tokens)
            else:
                # Find where the next pattern element matches
                next_pat = pattern[pattern_idx]
                # Simple approach: capture tokens until we see the next literal
                if isinstance(next_pat, TTToken):
                    # Capture until we see this literal token
                    captured = []
                    while token_idx < len(tokens):
                        tok = tokens[token_idx]
                        if isinstance(tok, TTToken) and tok.value == next_pat.value:
                            break
                        captured.append(tok)
                        token_idx += 1
                    captures[pat_elem.name] = TTSequence(captured)
                elif isinstance(next_pat, PatternVar) and next_pat.kind == 'block':
                    # Capture until we see a {...} group
                    captured = []
                    while token_idx < len(tokens):
                        tok = tokens[token_idx]
                        if isinstance(tok, TTGroup) and tok.delim == '{':
                            break
                        captured.append(tok)
                        token_idx += 1
                    captures[pat_elem.name] = TTSequence(captured)
                else:
                    # More complex - for now, just capture one token
                    captures[pat_elem.name] = tokens[token_idx]
                    token_idx += 1

        elif isinstance(pat_elem, PatternRepeat):
            # Repetition pattern - match 0 or more, 1 or more, or 0-1
            pattern_idx += 1  # Move to next pattern element first
            matched_items = []

            # Determine what comes next to know when to stop
            next_pat = pattern[pattern_idx] if pattern_idx < len(pattern) else None

            # Keep matching while we can
            while token_idx < len(tokens):
                # Check if we've hit the next pattern element
                if next_pat:
                    # Try to match the next pattern
                    if isinstance(next_pat, TTToken):
                        tok = tokens[token_idx]
                        if isinstance(tok, TTToken) and tok.value == next_pat.value:
                            # Next pattern matches, stop repeating
                            break
                    elif isinstance(next_pat, PatternVar) and next_pat.kind == 'block':
                        tok = tokens[token_idx]
                        if isinstance(tok, TTGroup) and tok.delim == '{':
                            # Next pattern (block) matches, stop repeating
                            break

                # Try to match one item
                tok = tokens[token_idx]
                if pat_elem.kind == 'block':
                    # Match blocks
                    if isinstance(tok, TTGroup) and tok.delim == '{':
                        matched_items.append(tok)
                        token_idx += 1
                    else:
                        break  # Can't match more
                else:
                    # Match regular tokens
                    if isinstance(tok, TTToken):
                        matched_items.append(tok)
                        token_idx += 1
                    else:
                        break  # Can't match more

                # For '?' quantifier, stop after one match
                if pat_elem.quantifier == '?' and len(matched_items) >= 1:
                    break

            # Check quantifier constraints
            if pat_elem.quantifier == '+' and len(matched_items) < 1:
                return None  # Need at least one match
            elif pat_elem.quantifier == '?' and len(matched_items) > 1:
                return None  # Can have at most one match

            # Store captures as a sequence
            if len(matched_items) == 0:
                captures[pat_elem.name] = TTSequence([])
            elif len(matched_items) == 1:
                captures[pat_elem.name] = matched_items[0]
            else:
                captures[pat_elem.name] = TTSequence(matched_items)

        else:
            # Other token tree types
            if token_idx < len(tokens) and tokens[token_idx] == pat_elem:
                token_idx += 1
                pattern_idx += 1
            else:
                return None

    # Check if we consumed all tokens and pattern
    if pattern_idx == len(pattern) and token_idx == len(tokens):
        return captures
    else:
        return None  # Didn't match completely


def substitute_captures(template: List[PatternElement],
                        captures: Dict[str, TokenTree]) -> TokenTree:
    """Substitute captured variables into an expansion template.

    Args:
        template: Pattern elements (parsed from expansion side)
        captures: Variable bindings from pattern matching

    Returns:
        Token tree with variables substituted
    """
    result = []

    for elem in template:
        if isinstance(elem, PatternVar):
            # Substitute captured variable
            if elem.name in captures:
                captured = captures[elem.name]
                # If this is a block variable, unwrap the group contents
                if elem.kind == 'block' and isinstance(captured, TTGroup):
                    # Substitute the contents of the block, not the block itself
                    if isinstance(captured.contents, TTSequence):
                        result.extend(captured.contents.items)
                    else:
                        result.append(captured.contents)
                elif isinstance(captured, TTSequence):
                    result.extend(captured.items)
                else:
                    result.append(captured)
            else:
                raise ValueError(f"Unbound pattern variable: ${elem.name}")

        elif isinstance(elem, PatternSpread):
            # Substitute spread variable
            if elem.name in captures:
                captured = captures[elem.name]
                if isinstance(captured, TTSequence):
                    result.extend(captured.items)
                else:
                    result.append(captured)
            else:
                raise ValueError(f"Unbound pattern variable: ..${elem.name}")

        elif isinstance(elem, PatternRepeat):
            # Substitute repetition variable - expand each item
            if elem.name in captures:
                captured = captures[elem.name]
                if isinstance(captured, TTSequence):
                    # Multiple items - expand each one
                    for item in captured.items:
                        result.append(item)
                elif captured:  # Single item or empty
                    result.append(captured)
                # If empty sequence, add nothing
            else:
                # For repetition patterns, it's okay to be unbound (means zero matches)
                # Only error if it's a '+' quantifier
                if elem.quantifier == '+':
                    raise ValueError(f"Unbound repetition pattern: ${elem.name}+ requires at least one match")

        elif isinstance(elem, TTGroup):
            # Recursively substitute inside groups
            # First parse the group's contents as a pattern
            group_pattern = parse_pattern(elem.contents)
            # Then substitute captures
            substituted_contents = substitute_captures(group_pattern, captures)
            # Create new group with substituted contents
            result.append(TTGroup(elem.delim, substituted_contents))

        else:
            # Regular token tree element (TTToken, etc.)
            result.append(elem)

    return TTSequence(result)
