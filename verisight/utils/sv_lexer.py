"""
Lightweight SystemVerilog lexer/tokenizer for VeriSight.

Provides basic tokenization of SystemVerilog source files for use
by the RTL and UVM parsers. This is NOT a full compiler — it handles
the subset needed for structural extraction: keywords, identifiers,
operators, string literals, comments, and preprocessor directives.
"""

import re
from typing import List, Tuple, Optional
from enum import Enum, auto
from dataclasses import dataclass


class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    OPERATOR = auto()
    PUNCTUATION = auto()
    COMMENT = auto()
    PREPROCESSOR = auto()
    WHITESPACE = auto()
    NEWLINE = auto()
    EOF = auto()


# SystemVerilog keywords relevant to structural extraction
SV_KEYWORDS = {
    # Module & hierarchy
    "module", "endmodule", "interface", "endinterface", "package", "endpackage",
    "program", "endprogram", "class", "endclass", "function", "endfunction",
    "task", "endtask", "generate", "endgenerate",
    # Ports & types
    "input", "output", "inout", "ref",
    "wire", "reg", "logic", "integer", "real", "time", "bit", "byte",
    "shortint", "int", "longint", "string",
    "signed", "unsigned",
    # Parameters
    "parameter", "localparam", "typedef", "enum", "struct", "union",
    # Always blocks
    "always", "always_comb", "always_ff", "always_latch",
    "initial", "assign", "deassign",
    # Control flow
    "if", "else", "case", "casex", "casez", "default", "endcase",
    "for", "foreach", "while", "do", "repeat", "forever",
    "begin", "end", "fork", "join", "join_any", "join_none",
    # Sensitivity
    "posedge", "negedge", "edge",
    # Assertions
    "assert", "assume", "cover", "restrict", "property", "endproperty",
    "sequence", "endsequence",
    # UVM-relevant
    "virtual", "extends", "implements", "import", "export",
    "static", "automatic", "const", "rand", "randc",
    "constraint", "with", "inside",
    "new", "null", "this", "super",
    # Miscellaneous
    "return", "void", "chandle", "event",
    "disable", "wait", "triggered",
    "clocking", "endclocking", "modport",
}


@dataclass
class Token:
    """A single token from SystemVerilog source."""
    type: TokenType
    value: str
    line: int
    column: int


# Regex patterns for tokenization (order matters — first match wins)
TOKEN_PATTERNS = [
    # Block comments
    (TokenType.COMMENT, r"/\*[\s\S]*?\*/"),
    # Line comments
    (TokenType.COMMENT, r"//[^\n]*"),
    # Preprocessor directives
    (TokenType.PREPROCESSOR, r"`[a-zA-Z_]\w*"),
    # String literals
    (TokenType.STRING, r'"(?:[^"\\]|\\.)*"'),
    # Numbers (hex, binary, decimal with width)
    (TokenType.NUMBER, r"\d+'[bBhHoOdD][0-9a-fA-F_xXzZ]+"),
    (TokenType.NUMBER, r"\d+\.\d+"),
    (TokenType.NUMBER, r"\d+"),
    # Identifiers (checked against keywords later)
    (TokenType.IDENTIFIER, r"[a-zA-Z_$][a-zA-Z0-9_$]*"),
    # Operators (multi-char first)
    (TokenType.OPERATOR, r"[<>=!]=|<<|>>|&&|\|\||[+\-*/%&|^~<>=!?:]"),
    # Punctuation
    (TokenType.PUNCTUATION, r"[{}()\[\];,\.#@]"),
    # Newlines
    (TokenType.NEWLINE, r"\n"),
    # Whitespace
    (TokenType.WHITESPACE, r"[ \t\r]+"),
]

# Compile the master regex
_MASTER_PATTERN = "|".join(
    f"(?P<g{i}>{pattern})" for i, (_, pattern) in enumerate(TOKEN_PATTERNS)
)
_MASTER_REGEX = re.compile(_MASTER_PATTERN)


def tokenize(source: str) -> List[Token]:
    """
    Tokenize SystemVerilog source code.

    Args:
        source: Source code string.

    Returns:
        List of Token objects (comments and whitespace excluded).
    """
    tokens = []
    line = 1
    col = 1

    for match in _MASTER_REGEX.finditer(source):
        value = match.group()
        # Determine which group matched
        token_type = TokenType.IDENTIFIER  # default
        for i, (tt, _) in enumerate(TOKEN_PATTERNS):
            if match.group(f"g{i}") is not None:
                token_type = tt
                break

        # Check if identifier is a keyword
        if token_type == TokenType.IDENTIFIER and value in SV_KEYWORDS:
            token_type = TokenType.KEYWORD

        # Track line/column
        token_line = line
        token_col = col
        newlines = value.count("\n")
        if newlines:
            line += newlines
            col = len(value.rsplit("\n", 1)[-1]) + 1
        else:
            col += len(value)

        # Skip whitespace and newlines, keep everything else
        if token_type not in (TokenType.WHITESPACE, TokenType.NEWLINE):
            tokens.append(Token(
                type=token_type,
                value=value,
                line=token_line,
                column=token_col,
            ))

    return tokens


def strip_comments(source: str) -> str:
    """
    Remove all comments from SystemVerilog source.

    Args:
        source: Source code string.

    Returns:
        Source with comments replaced by whitespace.
    """
    # Remove block comments
    result = re.sub(r"/\*[\s\S]*?\*/", lambda m: " " * len(m.group()), source)
    # Remove line comments
    result = re.sub(r"//[^\n]*", "", result)
    return result


def extract_between(
    tokens: List[Token],
    start_keyword: str,
    end_keyword: str,
    start_index: int = 0,
) -> Tuple[List[Token], int]:
    """
    Extract tokens between matching start/end keywords (e.g., module/endmodule).

    Args:
        tokens: Token list.
        start_keyword: Opening keyword (e.g., 'module').
        end_keyword: Closing keyword (e.g., 'endmodule').
        start_index: Index to start searching from.

    Returns:
        Tuple of (extracted tokens, index after end keyword).
    """
    depth = 0
    result = []
    i = start_index

    while i < len(tokens):
        tok = tokens[i]
        if tok.type == TokenType.KEYWORD and tok.value == start_keyword:
            depth += 1
        elif tok.type == TokenType.KEYWORD and tok.value == end_keyword:
            depth -= 1
            if depth == 0:
                return result, i + 1
        if depth > 0:
            result.append(tok)
        i += 1

    return result, i


def find_token(
    tokens: List[Token],
    value: str,
    start: int = 0,
    token_type: Optional[TokenType] = None,
) -> int:
    """
    Find the index of a token with the given value.

    Args:
        tokens: Token list.
        value: Token value to find.
        start: Start index for search.
        token_type: Optional type constraint.

    Returns:
        Index of found token, or -1 if not found.
    """
    for i in range(start, len(tokens)):
        if tokens[i].value == value:
            if token_type is None or tokens[i].type == token_type:
                return i
    return -1
