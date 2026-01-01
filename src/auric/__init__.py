from auric.evaluator import Env, evaluate, type_of
from auric.parser import parse
from auric.macros import register_macro, register_type_macro, expand_type_macros

# Alias for backward compatibility with old code
elaborate = parse

__all__ = [
    "Env",
    "elaborate",
    "evaluate",
    "type_of",
    "parse",
    "register_macro",
    "register_type_macro",
    "expand_type_macros",
]
