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
	LPAREN
	RPAREN
	DOT
	EQUAL
	SEMI
	COMMA
	COLON
	LET
	PLUS
	MINUS
	STAR
	SLASH
	ARROW
)

type Token struct {
	Type  TokenType
	Value string
}

type Lexer struct {
	Input string
	Pos   int
}

func New(input string) *Lexer {
	return &Lexer{Input: input}
}

func (l *Lexer) Next() Token {
	l.skipWhitespace()

	if l.Pos >= len(l.Input) {
		return Token{Type: EOF}
	}

	ch := l.Input[l.Pos]

	switch ch {
	case '{':
		l.Pos++
		return Token{Type: LBRACE, Value: "{"}
	case '}':
		l.Pos++
		return Token{Type: RBRACE, Value: "}"}
	case '(':
		l.Pos++
		return Token{Type: LPAREN, Value: "("}
	case ')':
		l.Pos++
		return Token{Type: RPAREN, Value: ")"}
	case '.':
		l.Pos++
		return Token{Type: DOT, Value: "."}
	case '=':
		l.Pos++
		return Token{Type: EQUAL, Value: "="}
	case ';':
		l.Pos++
		return Token{Type: SEMI, Value: ";"}
	case ',':
		l.Pos++
		return Token{Type: COMMA, Value: ","}
	case ':':
		l.Pos++
		return Token{Type: COLON, Value: ":"}
	case '+':
		l.Pos++
		return Token{Type: PLUS, Value: "+"}
	case '*':
		l.Pos++
		return Token{Type: STAR, Value: "*"}
	case '/':
		l.Pos++
		return Token{Type: SLASH, Value: "/"}
	case '-':
		if l.Pos+1 < len(l.Input) && l.Input[l.Pos+1] == '>' {
			l.Pos += 2
			return Token{Type: ARROW, Value: "->"}
		}
		l.Pos++
		return Token{Type: MINUS, Value: "-"}
	}

	if unicode.IsDigit(rune(ch)) {
		return l.readNumber()
	}

	if unicode.IsLetter(rune(ch)) || ch == '_' {
		return l.readIdent()
	}

	l.Pos++
	return Token{Type: EOF}
}

func (l *Lexer) skipWhitespace() {
	for l.Pos < len(l.Input) && unicode.IsSpace(rune(l.Input[l.Pos])) {
		l.Pos++
	}
}

func (l *Lexer) readNumber() Token {
	start := l.Pos
	for l.Pos < len(l.Input) && unicode.IsDigit(rune(l.Input[l.Pos])) {
		l.Pos++
	}
	return Token{Type: NUMBER, Value: l.Input[start:l.Pos]}
}

func (l *Lexer) readIdent() Token {
	start := l.Pos
	for l.Pos < len(l.Input) && (unicode.IsLetter(rune(l.Input[l.Pos])) || unicode.IsDigit(rune(l.Input[l.Pos])) || l.Input[l.Pos] == '_') {
		l.Pos++
	}
	value := l.Input[start:l.Pos]

	if value == "let" {
		return Token{Type: LET, Value: value}
	}

	return Token{Type: IDENT, Value: value}
}
