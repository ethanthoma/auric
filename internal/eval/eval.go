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

type VClosure struct {
	Params []syntax.Param
	Body   syntax.Expr
	Env    map[string]Value
}

func (VInt) value()     {}
func (VRecord) value()  {}
func (VClosure) value() {}

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

func (v VClosure) String() string {
	var params []string
	for _, p := range v.Params {
		if p.Value == nil {
			if p.Type != nil {
				params = append(params, fmt.Sprintf("%s", p.Name))
			} else {
				params = append(params, p.Name)
			}
		}
	}
	if len(params) == 0 {
		return "<function>"
	}
	return fmt.Sprintf("<function(%s)>", strings.Join(params, ", "))
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

	case syntax.Into:
		closureEnv := make(map[string]Value)
		maps.Copy(closureEnv, env)
		return VClosure{Params: e.Params, Body: e.Body, Env: closureEnv}, nil

	case syntax.App:
		fnVal, err := Eval(e.Fn, env)
		if err != nil {
			return nil, err
		}

		closure, ok := fnVal.(VClosure)
		if !ok {
			return nil, fmt.Errorf("not a function: %v", fnVal)
		}

		argVals := make([]Value, len(e.Args))
		for i, arg := range e.Args {
			val, err := Eval(arg, env)
			if err != nil {
				return nil, err
			}
			argVals[i] = val
		}

		callEnv := make(map[string]Value)
		maps.Copy(callEnv, closure.Env)

		argIdx := 0
		for _, param := range closure.Params {
			if param.Value == nil {
				if argIdx >= len(argVals) {
					return nil, fmt.Errorf("not enough arguments")
				}
				callEnv[param.Name] = argVals[argIdx]
				argIdx++
			} else {
				val, err := Eval(param.Value, callEnv)
				if err != nil {
					return nil, err
				}
				callEnv[param.Name] = val
			}
		}

		return Eval(closure.Body, callEnv)

	default:
		return nil, fmt.Errorf("unknown expression type")
	}
}
