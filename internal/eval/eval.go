package eval

import (
	"fmt"
	"maps"
	"strings"

	"github.com/ethanthoma/auric/internal/syntax"
)

type Value interface {
	value()
	String() string
}

type VInt struct {
	Val int
}

type VRecord struct {
	Fields map[string]Value
}

func (VInt) value()    {}
func (VRecord) value() {}

func (v VInt) String() string {
	return fmt.Sprintf("%d", v.Val)
}

func (v VRecord) String() string {
	var parts []string
	for k, val := range v.Fields {
		parts = append(parts, fmt.Sprintf("%s = %s", k, val.String()))
	}
	return "{" + strings.Join(parts, ", ") + "}"
}

func Eval(expr syntax.Expr, env map[string]Value) (Value, error) {
	switch e := expr.(type) {
	case syntax.Lit:
		return VInt{Val: e.Value}, nil

	case syntax.Var:
		val, ok := env[e.Name]
		if !ok {
			return nil, fmt.Errorf("undefined variable: %s", e.Name)
		}
		return val, nil

	case syntax.Let:
		val, err := Eval(e.Value, env)
		if err != nil {
			return nil, err
		}

		newEnv := make(map[string]Value)
		maps.Copy(newEnv, env)
		newEnv[e.Name] = val

		if e.Body != nil {
			return Eval(e.Body, newEnv)
		}

		return val, nil

	case syntax.Record:
		localEnv := make(map[string]Value)
		maps.Copy(localEnv, env)

		fields := make(map[string]Value)
		for _, stmt := range e.Stmts {
			switch s := stmt.(type) {
			case syntax.LetBinding:
				val, err := Eval(s.Value, localEnv)
				if err != nil {
					return nil, err
				}
				localEnv[s.Name] = val

			case syntax.FieldDef:
				val, err := Eval(s.Value, localEnv)
				if err != nil {
					return nil, err
				}
				fields[s.Name] = val
			}
		}
		return VRecord{Fields: fields}, nil

	case syntax.FieldAccess:
		recVal, err := Eval(e.Record, env)
		if err != nil {
			return nil, err
		}
		rv, ok := recVal.(VRecord)
		if !ok {
			return nil, fmt.Errorf("not a record value")
		}
		fieldVal, ok := rv.Fields[e.Field]
		if !ok {
			return nil, fmt.Errorf("field %s not found", e.Field)
		}
		return fieldVal, nil

	case syntax.BinOp:
		leftVal, err := Eval(e.Left, env)
		if err != nil {
			return nil, err
		}
		rightVal, err := Eval(e.Right, env)
		if err != nil {
			return nil, err
		}

		lv, ok := leftVal.(VInt)
		if !ok {
			return nil, fmt.Errorf("left operand must be Int")
		}
		rv, ok := rightVal.(VInt)
		if !ok {
			return nil, fmt.Errorf("right operand must be Int")
		}

		var result int
		switch e.Op {
		case "+":
			result = lv.Val + rv.Val
		case "-":
			result = lv.Val - rv.Val
		case "*":
			result = lv.Val * rv.Val
		case "/":
			if rv.Val == 0 {
				return nil, fmt.Errorf("division by zero")
			}
			result = lv.Val / rv.Val
		default:
			return nil, fmt.Errorf("unknown operator: %s", e.Op)
		}

		return VInt{Val: result}, nil

	default:
		return nil, fmt.Errorf("unknown expression type")
	}
}
