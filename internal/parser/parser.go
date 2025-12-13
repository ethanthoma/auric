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

func (p *Parser) Parse() syntax.Program {
	return p.parseProgram()
}

func (p *Parser) parseProgram() syntax.Program {
	var typeDefs []syntax.TypeDef

	for p.tok.Type == lexer.TYPE {
		typeDefs = append(typeDefs, p.parseTypeDef())
	}

	expr := p.parseExpr()

	return syntax.Program{TypeDefs: typeDefs, Expr: expr}
}

func (p *Parser) parseTypeDef() syntax.TypeDef {
	p.next()

	if p.tok.Type != lexer.IDENT {
		panic(fmt.Sprintf("expected type name, got %v", p.tok))
	}
	name := p.tok.Value
	p.next()

	if p.tok.Type != lexer.EQUAL {
		panic(fmt.Sprintf("expected = after type name, got %v", p.tok))
	}
	p.next()

	if p.tok.Type != lexer.LBRACE {
		panic(fmt.Sprintf("expected { for type definition, got %v", p.tok))
	}

	start := p.pos()
	p.next()

	if p.tok.Type == lexer.IDENT {
		peekPos := p.pos()
		secondTok := p.lex.Next()
		p.lex.Pos = peekPos

		if secondTok.Type == lexer.COLON {
			p.reset(start)
			tyExpr := p.parseTypeExpr()
			return syntax.TypeDef{Name: name, Alias: tyExpr}
		}
	}

	var variants []syntax.VariantDef
	for p.tok.Type != lexer.RBRACE {
		if p.tok.Type != lexer.IDENT {
			panic(fmt.Sprintf("expected variant name, got %v", p.tok))
		}
		variantName := p.tok.Value
		p.next()

		var fields []syntax.TyField
		if p.tok.Type == lexer.ARROW_LEFT {
			p.next()
			if p.tok.Type != lexer.LBRACE {
				panic(fmt.Sprintf("expected { after <-, got %v", p.tok))
			}
			p.next()

			for p.tok.Type != lexer.RBRACE {
				if p.tok.Type != lexer.IDENT {
					panic(fmt.Sprintf("expected field name, got %v", p.tok))
				}
				fieldName := p.tok.Value
				p.next()

				if p.tok.Type != lexer.COLON {
					panic(fmt.Sprintf("expected : after field name, got %v", p.tok))
				}
				p.next()

				fieldType := p.parseTypeExpr()
				fields = append(fields, syntax.TyField{Name: fieldName, Type: fieldType})

				switch p.tok.Type {
				case lexer.COMMA, lexer.SEMI:
					p.next()
				}
			}
			p.next()
		}

		variants = append(variants, syntax.VariantDef{Name: variantName, Fields: fields})

		if p.tok.Type == lexer.SEMI {
			p.next()
		}
	}
	p.next()

	return syntax.TypeDef{Name: name, Variants: variants}
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

	expr := p.parseBinOp(0)

	if p.tok.Type == lexer.ARROW {
		p.next()
		if p.tok.Type == lexer.MATCH {
			return p.parseMatch(expr)
		}
		panic(fmt.Sprintf("expected match after ->, got %v", p.tok))
	}

	return expr
}

func (p *Parser) parseMatch(scrutinee syntax.Expr) syntax.Expr {
	p.next()

	if p.tok.Type != lexer.LBRACE {
		panic(fmt.Sprintf("expected { after match, got %v", p.tok))
	}
	p.next()

	var cases []syntax.MatchCase
	for p.tok.Type != lexer.RBRACE {
		pattern := p.parsePattern()

		if p.tok.Type != lexer.DOUBLE_ARROW {
			panic(fmt.Sprintf("expected => after pattern, got %v", p.tok))
		}
		p.next()

		body := p.parseExpr()
		cases = append(cases, syntax.MatchCase{Pattern: pattern, Body: body})

		switch p.tok.Type {
		case lexer.COMMA, lexer.SEMI:
			p.next()
		}
	}
	p.next()

	return syntax.Match{Scrutinee: scrutinee, Cases: cases}
}

func (p *Parser) parsePattern() syntax.Pattern {
	if p.tok.Type == lexer.IDENT {
		name := p.tok.Value
		p.next()

		if p.tok.Type == lexer.LBRACE {
			p.next()
			var fields []string
			for p.tok.Type != lexer.RBRACE {
				if p.tok.Type != lexer.IDENT {
					panic(fmt.Sprintf("expected field name in pattern, got %v", p.tok))
				}
				fields = append(fields, p.tok.Value)
				p.next()

				if p.tok.Type == lexer.COMMA {
					p.next()
				}
			}
			p.next()
			return syntax.PatternVariant{Variant: name, Fields: fields}
		}

		return syntax.PatternVariant{Variant: name, Fields: nil}
	}

	panic(fmt.Sprintf("expected pattern, got %v", p.tok))
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
	baseType := p.parseBaseType()

	if p.tok.Type == lexer.LBRACKET {
		p.next()
		if p.tok.Type == lexer.RBRACKET {
			p.next()
			return syntax.TySized{Base: baseType, Size: syntax.SizeSlice{}}
		}

		if p.tok.Type != lexer.NUMBER {
			panic(fmt.Sprintf("expected number or ] in array type, got %v", p.tok))
		}
		size, _ := strconv.Atoi(p.tok.Value)
		p.next()

		if p.tok.Type != lexer.RBRACKET {
			panic(fmt.Sprintf("expected ] after array size, got %v", p.tok))
		}
		p.next()
		return syntax.TySized{Base: baseType, Size: syntax.SizeFixed{Size: size}}
	}

	return baseType
}

func (p *Parser) parseBaseType() syntax.TypeExpr {
	if p.tok.Type == lexer.LPAREN {
		p.next()
		if p.tok.Type == lexer.RPAREN {
			p.next()
			if p.tok.Type == lexer.ARROW {
				p.next()
				resultType := p.parseTypeExpr()
				return syntax.TyFunc{Params: nil, Result: resultType}
			}
			panic(fmt.Sprintf("expected -> after (), got %v", p.tok))
		}
		panic(fmt.Sprintf("thunk types must be () ->, got %v", p.tok))
	}

	if p.tok.Type == lexer.IDENT {
		name := p.tok.Value
		p.next()
		switch name {
		case "Int":
			return syntax.TyInt{}
		default:
			return syntax.TySum{Name: name}
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

			switch p.tok.Type {
			case lexer.COMMA, lexer.SEMI:
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

		case lexer.LBRACKET:
			p.next()
			if p.tok.Type == lexer.DOTDOT {
				p.next()
				end := p.parseBinOp(0)
				if p.tok.Type != lexer.RBRACKET {
					panic(fmt.Sprintf("expected ] after slice end, got %v", p.tok))
				}
				p.next()
				expr = syntax.Slice{Array: expr, Start: nil, End: end}
			} else {
				index := p.parseBinOp(0)
				if p.tok.Type == lexer.DOTDOT {
					p.next()
					if p.tok.Type == lexer.RBRACKET {
						p.next()
						expr = syntax.Slice{Array: expr, Start: index, End: nil}
					} else {
						end := p.parseBinOp(0)
						if p.tok.Type != lexer.RBRACKET {
							panic(fmt.Sprintf("expected ] after slice end, got %v", p.tok))
						}
						p.next()
						expr = syntax.Slice{Array: expr, Start: index, End: end}
					}
				} else {
					if p.tok.Type != lexer.RBRACKET {
						panic(fmt.Sprintf("expected ] after index, got %v", p.tok))
					}
					p.next()
					expr = syntax.Index{Array: expr, Index: index}
				}
			}

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
	if p.tok.Type == lexer.SEMI {
		p.next()
	}
	if p.tok.Type != lexer.EOF && p.tok.Type != lexer.RBRACE {
		body = p.parseExpr()
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
		if p.tok.Type == lexer.LBRACE {
			return p.parseVariantConstruct(name)
		}
		return syntax.Var{Name: name}

	case lexer.LBRACE:
		return p.parseRecord()

	case lexer.LBRACKET:
		return p.parseArrayLit()

	default:
		panic(fmt.Sprintf("unexpected token: %v", p.tok))
	}
}

func (p *Parser) parseArrayLit() syntax.Expr {
	p.next()

	var elements []syntax.Expr
	for p.tok.Type != lexer.RBRACKET {
		elem := p.parseExpr()
		elements = append(elements, elem)

		if p.tok.Type == lexer.COMMA {
			p.next()
		}
	}

	p.next()
	return syntax.ArrayLit{Elements: elements}
}

func (p *Parser) parseVariantConstruct(variant string) syntax.Expr {
	p.next()

	var fields []syntax.FieldDef
	for p.tok.Type != lexer.RBRACE {
		if p.tok.Type != lexer.DOT {
			panic(fmt.Sprintf("expected . for field in variant, got %v", p.tok))
		}
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
		fields = append(fields, syntax.FieldDef{Name: fieldName, Value: fieldValue})

		switch p.tok.Type {
		case lexer.COMMA, lexer.SEMI:
			p.next()
		}
	}
	p.next()

	return syntax.VariantConstruct{Variant: variant, Fields: fields}
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
