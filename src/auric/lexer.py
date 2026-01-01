"""Lexer/Tokenizer for Auric source code."""

import re
from typing import List

# Token patterns
# Types: I_Am_A_Type - each word starts with uppercase, separated by underscores
TYPE_ID = re.compile(r"[A-Z][a-z0-9]*(?:_[A-Z][a-z0-9]*)*\Z")
# Values: i_am_a_value - all lowercase with underscores
VAR_ID = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")

# Number patterns with type suffixes
INT_LIT = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|\d+)(?:u8|u16|u32|u64|i8|i16|i32|i64)?\Z")
FLOAT_LIT = re.compile(r"-?\d+\.\d+(?:[eE][+-]?\d+)?(?:f32|f64)?\Z")

# Symbol pattern - add := and => and ..
_sym = r"[∪∩\\(){}]|:=|=>|->|\.\.|:|=|\[|\]|Λ|\.|,|∀|;"
_tok = re.compile(
    rf"""\s*(
    @[_A-Za-z][_0-9A-Za-z]* |  # Builtin identifiers (@ prefix)
    {_sym} |
    '(?:[^'\\]|\\.)'   |  # Character literals
    -?\d+\.\d+(?:[eE][+-]?\d+)?(?:f32|f64)?  |  # Float literals with suffix
    -?(?:0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|\d+)(?:u8|u16|u32|u64|i8|i16|i32|i64)?  |  # Int literals with suffix
    [_A-Za-z][_0-9A-Za-z]* |  # Regular identifiers
    \n | .
)""",
    re.VERBOSE,
)


def lex(src: str) -> List[str]:
    """Tokenize Auric source code into a list of tokens."""
    return [m.group(1) for m in _tok.finditer(src) if m.group(1).strip() != ""]


class Buf:
    """Token buffer for parsing."""

    def __init__(self, ts: List[str]):
        self.ts = ts
        self.i = 0

    def peek(self):
        """Look at next token without consuming it."""
        return self.ts[self.i] if self.i < len(self.ts) else None

    def pop(self):
        """Consume and return next token."""
        if self.i >= len(self.ts):
            raise SyntaxError("unexpected <eof>")
        t = self.ts[self.i]
        self.i += 1
        return t
