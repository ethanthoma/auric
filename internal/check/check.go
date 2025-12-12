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

func (TInt) typ()    {}
func (TRecord) typ() {}

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

type Checker struct {
	ctx map[string]Type
}

func New() *Checker {
	return &Checker{ctx: make(map[string]Type)}
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
	default:
		return false
	}
}
