package lexer

import (
	"unicode"
)

type TokenType int

const (
	EOF TokenType = iota
	IDENT
	NUMBER
	LBRACE
	RBRACE
	DOT
	EQUAL
	SEMI
	LET
	PLUS
	MINUS
	STAR
	SLASH
)

type Token struct {
	Type  TokenType
	Value string
}

type Lexer struct {
	input string
	pos   int
}

func New(input string) *Lexer {
	return &Lexer{input: input}
}

func (l *Lexer) Next() Token {
	l.skipWhitespace()

	if l.pos >= len(l.input) {
		return Token{Type: EOF}
	}

	ch := l.input[l.pos]

	switch ch {
	case '{':
		l.pos++
		return Token{Type: LBRACE, Value: "{"}
	case '}':
		l.pos++
		return Token{Type: RBRACE, Value: "}"}
	case '.':
		l.pos++
		return Token{Type: DOT, Value: "."}
	case '=':
		l.pos++
		return Token{Type: EQUAL, Value: "="}
	case ';':
		l.pos++
		return Token{Type: SEMI, Value: ";"}
	case '+':
		l.pos++
		return Token{Type: PLUS, Value: "+"}
	case '-':
		l.pos++
		return Token{Type: MINUS, Value: "-"}
	case '*':
		l.pos++
		return Token{Type: STAR, Value: "*"}
	case '/':
		l.pos++
		return Token{Type: SLASH, Value: "/"}
	}

	if unicode.IsDigit(rune(ch)) {
		return l.readNumber()
	}

	if unicode.IsLetter(rune(ch)) || ch == '_' {
		return l.readIdent()
	}

	l.pos++
	return Token{Type: EOF}
}

func (l *Lexer) skipWhitespace() {
	for l.pos < len(l.input) && unicode.IsSpace(rune(l.input[l.pos])) {
		l.pos++
	}
}

func (l *Lexer) readNumber() Token {
	start := l.pos
	for l.pos < len(l.input) && unicode.IsDigit(rune(l.input[l.pos])) {
		l.pos++
	}
	return Token{Type: NUMBER, Value: l.input[start:l.pos]}
}

func (l *Lexer) readIdent() Token {
	start := l.pos
	for l.pos < len(l.input) && (unicode.IsLetter(rune(l.input[l.pos])) || unicode.IsDigit(rune(l.input[l.pos])) || l.input[l.pos] == '_') {
		l.pos++
	}
	value := l.input[start:l.pos]

	if value == "let" {
		return Token{Type: LET, Value: value}
	}

	return Token{Type: IDENT, Value: value}
}
