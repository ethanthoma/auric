package parser

import (
	"fmt"
	"strconv"

	"github.com/ethanthoma/auric/internal/lexer"
	"github.com/ethanthoma/auric/internal/syntax"
)

type Parser struct {
	lex *lexer.Lexer
	tok lexer.Token
}

func New(l *lexer.Lexer) *Parser {
	p := &Parser{lex: l}
	p.next()
	return p
}

func (p *Parser) next() {
	p.tok = p.lex.Next()
}

func (p *Parser) Parse() syntax.Expr {
	return p.parseExpr()
}

func (p *Parser) parseExpr() syntax.Expr {
	if p.tok.Type == lexer.LET {
		return p.parseLet()
	}
	return p.parseBinOp(0)
}

func (p *Parser) parseBinOp(minPrec int) syntax.Expr {
	left := p.parsePostfix()

	for {
		prec := p.precedence()
		if prec == 0 || prec < minPrec {
			break
		}

		op := p.tok.Value
		p.next()

		right := p.parseBinOp(prec + 1)
		left = syntax.BinOp{Op: op, Left: left, Right: right}
	}

	return left
}

func (p *Parser) precedence() int {
	switch p.tok.Type {
	case lexer.PLUS, lexer.MINUS:
		return 1
	case lexer.STAR, lexer.SLASH:
		return 2
	default:
		return 0
	}
}

func (p *Parser) parsePostfix() syntax.Expr {
	expr := p.parsePrimary()

	for p.tok.Type == lexer.DOT {
		p.next()
		if p.tok.Type != lexer.IDENT {
			panic(fmt.Sprintf("expected field name after ., got %v", p.tok))
		}
		field := p.tok.Value
		p.next()
		expr = syntax.FieldAccess{Record: expr, Field: field}
	}

	return expr
}

func (p *Parser) parseLet() syntax.Expr {
	p.next()
	if p.tok.Type != lexer.IDENT {
		panic(fmt.Sprintf("expected identifier, got %v", p.tok))
	}
	name := p.tok.Value
	p.next()

	if p.tok.Type != lexer.EQUAL {
		panic(fmt.Sprintf("expected =, got %v", p.tok))
	}
	p.next()

	value := p.parseExpr()

	var body syntax.Expr
	if p.tok.Type == lexer.SEMI || p.tok.Type == lexer.EOF {
		if p.tok.Type == lexer.SEMI {
			p.next()
		}
		if p.tok.Type != lexer.EOF {
			body = p.parseExpr()
		}
	}

	return syntax.Let{Name: name, Value: value, Body: body}
}

func (p *Parser) parsePrimary() syntax.Expr {
	switch p.tok.Type {
	case lexer.NUMBER:
		val, _ := strconv.Atoi(p.tok.Value)
		p.next()
		return syntax.Lit{Value: val}

	case lexer.IDENT:
		name := p.tok.Value
		p.next()
		return syntax.Var{Name: name}

	case lexer.LBRACE:
		return p.parseRecord()

	default:
		panic(fmt.Sprintf("unexpected token: %v", p.tok))
	}
}

func (p *Parser) parseRecord() syntax.Expr {
	p.next()

	var stmts []syntax.RecordStmt
	for p.tok.Type != lexer.RBRACE {
		switch p.tok.Type {
		case lexer.LET:
			p.next()
			if p.tok.Type != lexer.IDENT {
				panic(fmt.Sprintf("expected identifier after let, got %v", p.tok))
			}
			name := p.tok.Value
			p.next()

			if p.tok.Type != lexer.EQUAL {
				panic(fmt.Sprintf("expected =, got %v", p.tok))
			}
			p.next()

			value := p.parseExpr()
			stmts = append(stmts, syntax.LetBinding{Name: name, Value: value})

		case lexer.DOT:
			p.next()

			if p.tok.Type != lexer.IDENT {
				panic(fmt.Sprintf("expected field name, got %v", p.tok))
			}
			fieldName := p.tok.Value
			p.next()

			if p.tok.Type != lexer.EQUAL {
				panic(fmt.Sprintf("expected =, got %v", p.tok))
			}
			p.next()

			fieldValue := p.parseExpr()
			stmts = append(stmts, syntax.FieldDef{Name: fieldName, Value: fieldValue})

		default:
			panic(fmt.Sprintf("expected let or . inside record, got %v", p.tok))
		}

		if p.tok.Type == lexer.SEMI {
			p.next()
		}
	}

	p.next()
	return syntax.Record{Stmts: stmts}
}
