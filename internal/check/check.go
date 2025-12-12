package check

import (
	"fmt"
	"maps"
	"strings"

	"github.com/ethanthoma/auric/internal/syntax"
)

type Type interface {
	typ()
	String() string
}

type TInt struct{}

type TRecord struct {
	Fields map[string]Type
}

type TFunc struct {
	Params []string
	Result Type
}

func (TInt) typ()    {}
func (TRecord) typ() {}
func (TFunc) typ()   {}

func (t TInt) String() string {
	return "Int"
}

func (t TRecord) String() string {
	var parts []string
	for k, ty := range t.Fields {
		parts = append(parts, fmt.Sprintf("%s: %s", k, ty.String()))
	}
	return "{" + strings.Join(parts, ", ") + "}"
}

func (t TFunc) String() string {
	if len(t.Params) == 0 {
		return fmt.Sprintf("() -> %s", t.Result.String())
	}
	return fmt.Sprintf("(%s) -> %s", strings.Join(t.Params, ", "), t.Result.String())
}

type Checker struct {
	ctx map[string]Type
}

func New() *Checker {
	return &Checker{ctx: make(map[string]Type)}
}

func elaborateType(te syntax.TypeExpr) (Type, error) {
	switch t := te.(type) {
	case syntax.TyInt:
		return TInt{}, nil
	case syntax.TyRecord:
		fields := make(map[string]Type)
		for _, f := range t.Fields {
			ty, err := elaborateType(f.Type)
			if err != nil {
				return nil, err
			}
			fields[f.Name] = ty
		}
		return TRecord{Fields: fields}, nil
	case syntax.TyFunc:
		params := make([]string, len(t.Params))
		for i := range t.Params {
			params[i] = fmt.Sprintf("param%d", i)
		}
		result, err := elaborateType(t.Result)
		if err != nil {
			return nil, err
		}
		return TFunc{Params: params, Result: result}, nil
	case nil:
		return nil, nil
	default:
		return nil, fmt.Errorf("unknown type expression: %T", te)
	}
}

func (c *Checker) Infer(expr syntax.Expr) (Type, error) {
	switch e := expr.(type) {
	case syntax.Lit:
		return TInt{}, nil

	case syntax.Var:
		ty, ok := c.ctx[e.Name]
		if !ok {
			return nil, fmt.Errorf("undefined variable: %s", e.Name)
		}
		return ty, nil

	case syntax.Let:
		valTy, err := c.Infer(e.Value)
		if err != nil {
			return nil, err
		}

		c.ctx[e.Name] = valTy

		if e.Body != nil {
			return c.Infer(e.Body)
		}

		return valTy, nil

	case syntax.Record:
		localEnv := make(map[string]Type)
		maps.Copy(localEnv, c.ctx)

		fields := make(map[string]Type)
		for _, stmt := range e.Stmts {
			switch s := stmt.(type) {
			case syntax.LetBinding:
				localChecker := &Checker{ctx: localEnv}
				ty, err := localChecker.Infer(s.Value)
				if err != nil {
					return nil, err
				}
				localEnv[s.Name] = ty

			case syntax.FieldDef:
				localChecker := &Checker{ctx: localEnv}
				ty, err := localChecker.Infer(s.Value)
				if err != nil {
					return nil, err
				}
				fields[s.Name] = ty
			}
		}
		return TRecord{Fields: fields}, nil

	case syntax.FieldAccess:
		recTy, err := c.Infer(e.Record)
		if err != nil {
			return nil, err
		}
		rt, ok := recTy.(TRecord)
		if !ok {
			return nil, fmt.Errorf("not a record type")
		}
		fieldTy, ok := rt.Fields[e.Field]
		if !ok {
			return nil, fmt.Errorf("field %s not found", e.Field)
		}
		return fieldTy, nil

	case syntax.BinOp:
		leftTy, err := c.Infer(e.Left)
		if err != nil {
			return nil, err
		}
		rightTy, err := c.Infer(e.Right)
		if err != nil {
			return nil, err
		}

		if _, ok := leftTy.(TInt); !ok {
			return nil, fmt.Errorf("left operand must be Int, got %v", leftTy)
		}
		if _, ok := rightTy.(TInt); !ok {
			return nil, fmt.Errorf("right operand must be Int, got %v", rightTy)
		}

		return TInt{}, nil

	case syntax.Into:
		localEnv := make(map[string]Type)
		maps.Copy(localEnv, c.ctx)

		var exposedParams []string
		for _, param := range e.Params {
			if param.Value == nil {
				if param.Type == nil {
					return nil, fmt.Errorf("parameter %s requires type annotation", param.Name)
				}
				ty, err := elaborateType(param.Type)
				if err != nil {
					return nil, err
				}
				localEnv[param.Name] = ty
				exposedParams = append(exposedParams, param.Name)
			} else {
				localChecker := &Checker{ctx: localEnv}
				ty, err := localChecker.Infer(param.Value)
				if err != nil {
					return nil, err
				}
				if param.Type != nil {
					annotatedTy, err := elaborateType(param.Type)
					if err != nil {
						return nil, err
					}
					if !typeEqual(ty, annotatedTy) {
						return nil, fmt.Errorf("type mismatch for parameter %s: expected %v, got %v", param.Name, annotatedTy, ty)
					}
				}
				localEnv[param.Name] = ty
			}
		}

		bodyChecker := &Checker{ctx: localEnv}
		resultTy, err := bodyChecker.Infer(e.Body)
		if err != nil {
			return nil, err
		}

		if e.ReturnType != nil {
			annotatedReturnTy, err := elaborateType(e.ReturnType)
			if err != nil {
				return nil, err
			}
			if !typeEqual(resultTy, annotatedReturnTy) {
				return nil, fmt.Errorf("return type mismatch: expected %v, got %v", annotatedReturnTy, resultTy)
			}
		}

		return TFunc{Params: exposedParams, Result: resultTy}, nil

	case syntax.App:
		fnTy, err := c.Infer(e.Fn)
		if err != nil {
			return nil, err
		}

		funcTy, ok := fnTy.(TFunc)
		if !ok {
			return nil, fmt.Errorf("not a function type: %v", fnTy)
		}

		if len(e.Args) != len(funcTy.Params) {
			return nil, fmt.Errorf("expected %d arguments, got %d", len(funcTy.Params), len(e.Args))
		}

		argTypes := make([]Type, len(e.Args))
		for i, arg := range e.Args {
			ty, err := c.Infer(arg)
			if err != nil {
				return nil, err
			}
			argTypes[i] = ty
		}

		return funcTy.Result, nil

	default:
		return nil, fmt.Errorf("unknown expression type")
	}
}

func (c *Checker) Check(expr syntax.Expr, ty Type) error {
	inferredTy, err := c.Infer(expr)
	if err != nil {
		return err
	}

	if !typeEqual(inferredTy, ty) {
		return fmt.Errorf("type mismatch: expected %v, got %v", ty, inferredTy)
	}

	return nil
}

func typeEqual(a, b Type) bool {
	switch at := a.(type) {
	case TInt:
		_, ok := b.(TInt)
		return ok
	case TRecord:
		bt, ok := b.(TRecord)
		if !ok {
			return false
		}
		if len(at.Fields) != len(bt.Fields) {
			return false
		}
		for k, v := range at.Fields {
			bv, ok := bt.Fields[k]
			if !ok || !typeEqual(v, bv) {
				return false
			}
		}
		return true
	case TFunc:
		bt, ok := b.(TFunc)
		if !ok {
			return false
		}
		if len(at.Params) != len(bt.Params) {
			return false
		}
		return typeEqual(at.Result, bt.Result)
	default:
		return false
	}
}
