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

type VVariant struct {
	Variant string
	Fields  map[string]Value
}

type VArray struct {
	Elements []Value
}

func (VInt) value()     {}
func (VRecord) value()  {}
func (VClosure) value() {}
func (VVariant) value() {}
func (VArray) value()   {}

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

func (v VVariant) String() string {
	if len(v.Fields) == 0 {
		return v.Variant
	}
	var parts []string
	for k, val := range v.Fields {
		parts = append(parts, fmt.Sprintf("%s = %s", k, val.String()))
	}
	return fmt.Sprintf("%s{%s}", v.Variant, strings.Join(parts, ", "))
}

func (v VArray) String() string {
	var parts []string
	for _, val := range v.Elements {
		parts = append(parts, val.String())
	}
	return "[" + strings.Join(parts, ", ") + "]"
}

func Eval(program syntax.Program, env map[string]Value) (Value, error) {
	return evalExpr(program.Expr, env)
}

func evalExpr(expr syntax.Expr, env map[string]Value) (Value, error) {
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
		var val Value
		var err error

		if into, ok := e.Value.(syntax.Into); ok {
			closureEnv := make(map[string]Value)
			maps.Copy(closureEnv, env)

			closure := VClosure{Params: into.Params, Body: into.Body, Env: closureEnv}
			closureEnv[e.Name] = closure

			val = closure
		} else {
			val, err = evalExpr(e.Value, env)
			if err != nil {
				return nil, err
			}
		}

		newEnv := make(map[string]Value)
		maps.Copy(newEnv, env)
		newEnv[e.Name] = val

		if e.Body != nil {
			return evalExpr(e.Body, newEnv)
		}

		return val, nil

	case syntax.Record:
		localEnv := make(map[string]Value)
		maps.Copy(localEnv, env)

		fields := make(map[string]Value)
		for _, stmt := range e.Stmts {
			switch s := stmt.(type) {
			case syntax.LetBinding:
				val, err := evalExpr(s.Value, localEnv)
				if err != nil {
					return nil, err
				}
				localEnv[s.Name] = val

			case syntax.FieldDef:
				val, err := evalExpr(s.Value, localEnv)
				if err != nil {
					return nil, err
				}
				fields[s.Name] = val
			}
		}
		return VRecord{Fields: fields}, nil

	case syntax.FieldAccess:
		recVal, err := evalExpr(e.Record, env)
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
		leftVal, err := evalExpr(e.Left, env)
		if err != nil {
			return nil, err
		}
		rightVal, err := evalExpr(e.Right, env)
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
		fnVal, err := evalExpr(e.Fn, env)
		if err != nil {
			return nil, err
		}

		closure, ok := fnVal.(VClosure)
		if !ok {
			return nil, fmt.Errorf("not a function: %v", fnVal)
		}

		argVals := make([]Value, len(e.Args))
		for i, arg := range e.Args {
			val, err := evalExpr(arg, env)
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
				val, err := evalExpr(param.Value, callEnv)
				if err != nil {
					return nil, err
				}
				callEnv[param.Name] = val
			}
		}

		return evalExpr(closure.Body, callEnv)

	case syntax.VariantConstruct:
		fields := make(map[string]Value)
		for _, field := range e.Fields {
			val, err := evalExpr(field.Value, env)
			if err != nil {
				return nil, err
			}
			fields[field.Name] = val
		}
		return VVariant{Variant: e.Variant, Fields: fields}, nil

	case syntax.Match:
		scrutineeVal, err := evalExpr(e.Scrutinee, env)
		if err != nil {
			return nil, err
		}

		variant, ok := scrutineeVal.(VVariant)
		if !ok {
			return nil, fmt.Errorf("match scrutinee must be a variant, got %v", scrutineeVal)
		}

		for _, matchCase := range e.Cases {
			matched, caseEnv := matchPattern(variant, matchCase.Pattern, env)
			if matched {
				return evalExpr(matchCase.Body, caseEnv)
			}
		}

		return nil, fmt.Errorf("no match case handled variant %s", variant.Variant)

	case syntax.ArrayLit:
		elements := make([]Value, len(e.Elements))
		for i, elem := range e.Elements {
			val, err := evalExpr(elem, env)
			if err != nil {
				return nil, err
			}
			elements[i] = val
		}
		return VArray{Elements: elements}, nil

	case syntax.Index:
		arrayVal, err := evalExpr(e.Array, env)
		if err != nil {
			return nil, err
		}

		indexVal, err := evalExpr(e.Index, env)
		if err != nil {
			return nil, err
		}

		array, ok := arrayVal.(VArray)
		if !ok {
			return nil, fmt.Errorf("cannot index non-array value")
		}

		idx, ok := indexVal.(VInt)
		if !ok {
			return nil, fmt.Errorf("array index must be Int")
		}

		actualIdx := idx.Val
		if actualIdx < 0 {
			actualIdx = len(array.Elements) + actualIdx
		}

		if actualIdx < 0 || actualIdx >= len(array.Elements) {
			return nil, fmt.Errorf("array index out of bounds: %d", idx.Val)
		}

		return array.Elements[actualIdx], nil

	case syntax.Slice:
		arrayVal, err := evalExpr(e.Array, env)
		if err != nil {
			return nil, err
		}

		array, ok := arrayVal.(VArray)
		if !ok {
			return nil, fmt.Errorf("cannot slice non-array value")
		}

		start := 0
		if e.Start != nil {
			startVal, err := evalExpr(e.Start, env)
			if err != nil {
				return nil, err
			}
			startInt, ok := startVal.(VInt)
			if !ok {
				return nil, fmt.Errorf("slice start must be Int")
			}
			start = startInt.Val
			if start < 0 {
				start = len(array.Elements) + start
			}
		}

		end := len(array.Elements)
		if e.End != nil {
			endVal, err := evalExpr(e.End, env)
			if err != nil {
				return nil, err
			}
			endInt, ok := endVal.(VInt)
			if !ok {
				return nil, fmt.Errorf("slice end must be Int")
			}
			end = endInt.Val
			if end < 0 {
				end = len(array.Elements) + end
			}
		}

		if start < 0 || start > len(array.Elements) {
			return nil, fmt.Errorf("slice start out of bounds: %d", start)
		}
		if end < 0 || end > len(array.Elements) {
			return nil, fmt.Errorf("slice end out of bounds: %d", end)
		}
		if end < start {
			return nil, fmt.Errorf("slice end %d is before start %d", end, start)
		}

		elements := make([]Value, end-start)
		copy(elements, array.Elements[start:end])
		return VArray{Elements: elements}, nil

	default:
		return nil, fmt.Errorf("unknown expression type")
	}
}

func matchPattern(variant VVariant, pattern syntax.Pattern, env map[string]Value) (bool, map[string]Value) {
	switch p := pattern.(type) {
	case syntax.PatternVariant:
		if variant.Variant != p.Variant {
			return false, nil
		}

		caseEnv := make(map[string]Value)
		maps.Copy(caseEnv, env)

		i := 0
		for _, fieldVal := range variant.Fields {
			if i < len(p.Fields) {
				caseEnv[p.Fields[i]] = fieldVal
				i++
			}
		}

		return true, caseEnv

	case syntax.PatternWildcard:
		return true, env

	default:
		return false, nil
	}
}
