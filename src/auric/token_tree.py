"""Token Tree representation for macro expansion.

Token trees are a grouped representation of tokens that sits between
tokenization and parsing. Macros operate on token trees, allowing them
to define custom syntax.

Token Tree Types:
- TTToken: A single token
- TTGroup: Grouped tokens like {...}, (...), etc.
- TTSequence: A sequence of token trees
"""

from dataclasses import dataclass
from typing import List, Union


@dataclass
class TTToken:
    """A single token."""
    value: str

    def __repr__(self):
        return f"TTToken({self.value!r})"


@dataclass
class TTGroup:
    """A group of tokens delimited by braces, parens, etc.

    Delimiters:
    - '{' ... '}' - braces
    - '(' ... ')' - parens
    - Other delimiters as needed
    """
    delim: str  # Opening delimiter: '{', '(', etc.
    contents: 'TokenTree'

    def __repr__(self):
        close = {'(': ')', '{': '}', '[': ']'}.get(self.delim, self.delim)
        return f"{self.delim}{self.contents}{close}"


@dataclass
class TTSequence:
    """A sequence of token trees."""
    items: List['TokenTree']

    def __repr__(self):
        return ' '.join(str(item) for item in self.items)


# Token tree can be any of these types
TokenTree = Union[TTToken, TTGroup, TTSequence]


def group_tokens(tokens: List[str]) -> TokenTree:
    """Convert a flat list of tokens into a token tree.

    Groups tokens by matching delimiters:
    - {...} into TTGroup('{', ...)
    - (...) into TTGroup('(', ...)

    Args:
        tokens: Flat list of tokens from lexer

    Returns:
        A TokenTree representing the grouped structure
    """
    def parse_sequence(ts: List[str], i: int) -> tuple[TTSequence, int]:
        """Parse a sequence of token trees until end or closing delimiter."""
        items = []
        while i < len(ts):
            tok = ts[i]

            # Check for closing delimiters
            if tok in (')', '}', ']'):
                break

            # Opening delimiters - start a group
            if tok in ('(', '{', '['):
                group, i = parse_group(ts, i)
                items.append(group)
            else:
                # Regular token
                items.append(TTToken(tok))
                i += 1

        return TTSequence(items), i

    def parse_group(ts: List[str], i: int) -> tuple[TTGroup, int]:
        """Parse a grouped token tree."""
        delim = ts[i]
        i += 1  # skip opening delimiter

        # Parse contents until closing delimiter
        contents, i = parse_sequence(ts, i)

        # Expect closing delimiter
        if i >= len(ts):
            raise SyntaxError(f"Unclosed '{delim}'")

        close = ts[i]
        expected_close = {'(': ')', '{': '}', '[': ']'}[delim]
        if close != expected_close:
            raise SyntaxError(f"Expected '{expected_close}', got '{close}'")

        i += 1  # skip closing delimiter
        return TTGroup(delim, contents), i

    result, _ = parse_sequence(tokens, 0)
    return result


def ungroup_tokens(tt: TokenTree) -> List[str]:
    """Convert a token tree back into a flat list of tokens.

    Used after macro expansion to get tokens for final parsing.
    """
    if isinstance(tt, TTToken):
        return [tt.value]
    elif isinstance(tt, TTGroup):
        close = {'(': ')', '{': '}', '[': ']'}[tt.delim]
        return [tt.delim] + ungroup_tokens(tt.contents) + [close]
    elif isinstance(tt, TTSequence):
        result = []
        for item in tt.items:
            result.extend(ungroup_tokens(item))
        return result
    else:
        raise TypeError(f"Unknown token tree type: {type(tt)}")
