"""Token tree macro expansion - unified macro system.

Macros are defined with pattern matching syntax:

    macro for => {
        for $var = ..$expr $block -> for_impl($expr, ($var) => $block);
    }

Macros operate on token trees before parsing, allowing them to define
custom syntax.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from auric.token_tree import TokenTree, TTToken, TTGroup, TTSequence, group_tokens, ungroup_tokens
from auric.macro_patterns import parse_pattern, match_pattern, substitute_captures, PatternElement


@dataclass
class MacroRule:
    """A single pattern -> expansion rule in a macro definition."""
    pattern: List[PatternElement]
    expansion: List[PatternElement]

    def try_expand(self, tt: TokenTree) -> Optional[TokenTree]:
        """Try to expand this rule against a token tree.

        Returns:
            Expanded token tree if pattern matches, None otherwise
        """
        captures = match_pattern(self.pattern, tt)
        if captures is not None:
            return substitute_captures(self.expansion, captures)
        return None


@dataclass
class TTMacro:
    """A token tree macro with multiple pattern-matching rules."""
    name: str
    rules: List[MacroRule]

    def try_expand(self, tt: TokenTree) -> Optional[TokenTree]:
        """Try to expand this macro against a token tree.

        Tries each rule in order until one matches.
        """
        for rule in self.rules:
            result = rule.try_expand(tt)
            if result is not None:
                return result
        return None


def parse_macro_definition(tt: TokenTree) -> TTMacro:
    """Parse a macro definition from a token tree.

    Expected format:
        macro name => {
            pattern1 -> expansion1;
            pattern2 -> expansion2;
        }
    """
    if not isinstance(tt, TTSequence) or len(tt.items) < 4:
        raise SyntaxError("Invalid macro definition")

    items = tt.items

    # Check for 'macro' keyword
    if not (isinstance(items[0], TTToken) and items[0].value == "macro"):
        raise SyntaxError("Macro definition must start with 'macro'")

    # Get macro name
    if not isinstance(items[1], TTToken):
        raise SyntaxError("Expected macro name")
    name = items[1].value

    # Check for '=>'
    if not (isinstance(items[2], TTToken) and items[2].value == "=>"):
        raise SyntaxError("Expected '=>' after macro name")

    # Get macro body (should be a {...} group)
    if not isinstance(items[3], TTGroup) or items[3].delim != '{':
        raise SyntaxError("Expected {...} for macro body")

    body = items[3].contents

    # Parse rules from body
    rules = parse_macro_rules(body)

    return TTMacro(name, rules)


def parse_macro_rules(body: TokenTree) -> List[MacroRule]:
    """Parse macro rules from the body of a macro definition.

    Rules are separated by ';' and have the form:
        pattern -> expansion
    """
    if not isinstance(body, TTSequence):
        body = TTSequence([body])

    rules = []
    current_pattern = []
    current_expansion = []
    in_expansion = False

    for item in body.items:
        if isinstance(item, TTToken):
            if item.value == "->":
                # Switch to expansion mode
                in_expansion = True
            elif item.value == ";":
                # End of rule
                if current_pattern and current_expansion:
                    pattern = parse_pattern(TTSequence(current_pattern))
                    expansion = parse_pattern(TTSequence(current_expansion))
                    rules.append(MacroRule(pattern, expansion))
                current_pattern = []
                current_expansion = []
                in_expansion = False
            else:
                # Add to current pattern or expansion
                if in_expansion:
                    current_expansion.append(item)
                else:
                    current_pattern.append(item)
        else:
            # Groups and other elements
            if in_expansion:
                current_expansion.append(item)
            else:
                current_pattern.append(item)

    # Handle last rule if no trailing semicolon
    if current_pattern and current_expansion:
        pattern = parse_pattern(TTSequence(current_pattern))
        expansion = parse_pattern(TTSequence(current_expansion))
        rules.append(MacroRule(pattern, expansion))

    return rules


def collect_tt_macros(tt: TokenTree) -> Tuple[Dict[str, TTMacro], List[TokenTree]]:
    """Collect macro definitions from a token tree.

    Args:
        tt: Token tree representing top-level definitions

    Returns:
        (macros dict, non-macro definitions)
    """
    macros = {}
    other_defs = []

    if isinstance(tt, TTSequence):
        i = 0
        while i < len(tt.items):
            item = tt.items[i]

            # Check for macro definition pattern: macro name => { ... }
            if (isinstance(item, TTToken) and item.value == "macro" and
                i + 3 < len(tt.items)):
                # Check if next tokens match: name => { ... }
                name_tok = tt.items[i + 1]
                arrow_tok = tt.items[i + 2]
                body_tok = tt.items[i + 3]

                if (isinstance(name_tok, TTToken) and
                    isinstance(arrow_tok, TTToken) and arrow_tok.value == "=>" and
                    isinstance(body_tok, TTGroup) and body_tok.delim == "{"):
                    # This is a macro definition
                    try:
                        # Create a TTSequence for parse_macro_definition
                        macro_tt = TTSequence([item, name_tok, arrow_tok, body_tok])
                        macro = parse_macro_definition(macro_tt)
                        macros[macro.name] = macro
                        i += 4  # Skip the macro definition
                        continue
                    except SyntaxError as e:
                        print(f"Warning: Failed to parse macro: {e}")

            # Not a macro definition - add to other_defs
            other_defs.append(item)
            i += 1
    else:
        other_defs.append(tt)

    return macros, other_defs


def expand_tt_macros(tt: TokenTree, macros: Dict[str, TTMacro], depth: int = 0) -> TokenTree:
    """Recursively expand macros in a token tree.

    Args:
        tt: Token tree to expand
        macros: Dictionary of macro definitions
        depth: Recursion depth (for preventing infinite loops)

    Returns:
        Expanded token tree
    """
    if depth > 100:
        raise RecursionError("Macro expansion depth exceeded")

    if isinstance(tt, TTToken):
        return tt

    elif isinstance(tt, TTGroup):
        # Expand contents of group
        expanded_contents = expand_tt_macros(tt.contents, macros, depth)
        return TTGroup(tt.delim, expanded_contents)

    elif isinstance(tt, TTSequence):
        # Try to match entire sequence against macro patterns
        for macro in macros.values():
            result = macro.try_expand(tt)
            if result is not None:
                # Expansion succeeded - recursively expand result
                return expand_tt_macros(result, macros, depth + 1)

        # No macro matched entire sequence - try to find macro invocations within it
        expanded_items = []
        i = 0
        while i < len(tt.items):
            # Try to match a macro starting at position i
            matched = False
            for macro in macros.values():
                # Try to match against a subsequence starting at i
                for end in range(i + 1, len(tt.items) + 1):
                    subseq = TTSequence(tt.items[i:end])
                    result = macro.try_expand(subseq)
                    if result is not None:
                        # Found a match! Expand it and add to result
                        expanded = expand_tt_macros(result, macros, depth + 1)
                        if isinstance(expanded, TTSequence):
                            expanded_items.extend(expanded.items)
                        else:
                            expanded_items.append(expanded)
                        i = end  # Skip past the matched tokens
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                # No macro matched - expand this item and move on
                expanded = expand_tt_macros(tt.items[i], macros, depth)
                expanded_items.append(expanded)
                i += 1

        return TTSequence(expanded_items)

    else:
        return tt
