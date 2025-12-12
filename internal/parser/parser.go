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
	return p.parseInto()
}

func (p *Parser) parseInto() syntax.Expr {
	if p.tok.Type == lexer.LPAREN {
		start := p.pos()
		params, returnType := p.parseParamList()

		if p.tok.Type == lexer.ARROW {
			p.next()
			body := p.parseInto()
			return syntax.Into{Params: params, ReturnType: returnType, Body: body}
		}

		p.reset(start)
	}

	return p.parseBinOp(0)
}

func (p *Parser) pos() int {
	return p.lex.Pos
}

func (p *Parser) reset(pos int) {
	p.lex.Pos = pos
	p.next()
}

func (p *Parser) parseParamList() ([]syntax.Param, syntax.TypeExpr) {
	p.next()

	var params []syntax.Param
	for p.tok.Type != lexer.RPAREN {
		if p.tok.Type != lexer.IDENT {
			panic(fmt.Sprintf("expected parameter name, got %v", p.tok))
		}
		name := p.tok.Value
		p.next()

		var ty syntax.TypeExpr
		if p.tok.Type == lexer.COLON {
			p.next()
			ty = p.parseTypeExpr()
		}

		var value syntax.Expr
		if p.tok.Type == lexer.EQUAL {
			p.next()
			value = p.parseBinOp(0)
		}

		params = append(params, syntax.Param{Name: name, Type: ty, Value: value})

		if p.tok.Type == lexer.COMMA {
			p.next()
		}
	}

	p.next()

	var returnType syntax.TypeExpr
	if p.tok.Type == lexer.COLON {
		p.next()
		returnType = p.parseTypeExpr()
	}

	return params, returnType
}

func (p *Parser) parseTypeExpr() syntax.TypeExpr {
	if p.tok.Type == lexer.IDENT {
		name := p.tok.Value
		p.next()
		switch name {
		case "Int":
			return syntax.TyInt{}
		default:
			panic(fmt.Sprintf("unknown type: %s", name))
		}
	}

	if p.tok.Type == lexer.LBRACE {
		p.next()
		var fields []syntax.TyField
		for p.tok.Type != lexer.RBRACE {
			if p.tok.Type != lexer.IDENT {
				panic(fmt.Sprintf("expected field name in type, got %v", p.tok))
			}
			fieldName := p.tok.Value
			p.next()

			if p.tok.Type != lexer.COLON {
				panic(fmt.Sprintf("expected : in type field, got %v", p.tok))
			}
			p.next()

			fieldType := p.parseTypeExpr()
			fields = append(fields, syntax.TyField{Name: fieldName, Type: fieldType})

			if p.tok.Type == lexer.SEMI {
				p.next()
			}
		}
		p.next()
		return syntax.TyRecord{Fields: fields}
	}

	panic(fmt.Sprintf("expected type expression, got %v", p.tok))
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

	for {
		switch p.tok.Type {
		case lexer.DOT:
			p.next()
			if p.tok.Type != lexer.IDENT {
				panic(fmt.Sprintf("expected field name after ., got %v", p.tok))
			}
			field := p.tok.Value
			p.next()
			expr = syntax.FieldAccess{Record: expr, Field: field}

		case lexer.LPAREN:
			args := p.parseArgList()
			expr = syntax.App{Fn: expr, Args: args}

		default:
			return expr
		}
	}
}

func (p *Parser) parseArgList() []syntax.Expr {
	p.next()

	var args []syntax.Expr
	for p.tok.Type != lexer.RPAREN {
		arg := p.parseInto()
		args = append(args, arg)

		if p.tok.Type == lexer.COMMA {
			p.next()
		}
	}

	p.next()
	return args
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
