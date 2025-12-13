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

type TSum struct {
	Name     string
	Variants map[string]TRecord
}

type TSized struct {
	Base Type
	Size int
}

type TSlice struct {
	Base Type
}

func (TInt) typ()    {}
func (TRecord) typ() {}
func (TFunc) typ()   {}
func (TSum) typ()    {}
func (TSized) typ()  {}
func (TSlice) typ()  {}

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

func (t TSum) String() string {
	return t.Name
}

func (t TSized) String() string {
	return fmt.Sprintf("%s[%d]", t.Base.String(), t.Size)
}

func (t TSlice) String() string {
	return fmt.Sprintf("%s[]", t.Base.String())
}

type Checker struct {
	ctx         map[string]Type
	typeDefs    map[string]TSum
	typeAliases map[string]Type
}

func New(defs []syntax.TypeDef) *Checker {
	c := &Checker{
		ctx:         make(map[string]Type),
		typeDefs:    make(map[string]TSum),
		typeAliases: make(map[string]Type),
	}

	for _, def := range defs {
		if def.Alias != nil {
			ty, _ := c.elaborateTypeWithDefs(def.Alias)
			c.typeAliases[def.Name] = ty
		} else {
			variants := make(map[string]TRecord)
			for _, variant := range def.Variants {
				fields := make(map[string]Type)
				for _, field := range variant.Fields {
					ty, _ := c.elaborateTypeWithDefs(field.Type)
					fields[field.Name] = ty
				}
				variants[variant.Name] = TRecord{Fields: fields}
			}
			c.typeDefs[def.Name] = TSum{Name: def.Name, Variants: variants}
		}
	}

	return c
}

func (c *Checker) elaborateTypeWithDefs(te syntax.TypeExpr) (Type, error) {
	switch t := te.(type) {
	case syntax.TyInt:
		return TInt{}, nil
	case syntax.TyRecord:
		fields := make(map[string]Type)
		for _, f := range t.Fields {
			ty, err := c.elaborateTypeWithDefs(f.Type)
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
		result, err := c.elaborateTypeWithDefs(t.Result)
		if err != nil {
			return nil, err
		}
		return TFunc{Params: params, Result: result}, nil
	case syntax.TySum:
		if aliasTy, ok := c.typeAliases[t.Name]; ok {
			return aliasTy, nil
		}
		if sumTy, ok := c.typeDefs[t.Name]; ok {
			return sumTy, nil
		}
		return TSum{Name: t.Name}, nil
	case syntax.TySized:
		base, err := c.elaborateTypeWithDefs(t.Base)
		if err != nil {
			return nil, err
		}
		switch size := t.Size.(type) {
		case syntax.SizeFixed:
			return TSized{Base: base, Size: size.Size}, nil
		case syntax.SizeSlice:
			return TSlice{Base: base}, nil
		default:
			return nil, fmt.Errorf("unknown size expression: %T", t.Size)
		}
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
		if into, ok := e.Value.(syntax.Into); ok && into.ReturnType != nil {
			var exposedParams []string
			for _, param := range into.Params {
				if param.Value == nil && param.Type != nil {
					exposedParams = append(exposedParams, param.Name)
				}
			}

			if len(exposedParams) > 0 {
				returnTy, err := c.elaborateTypeWithDefs(into.ReturnType)
				if err != nil {
					return nil, err
				}
				funcTy := TFunc{Params: exposedParams, Result: returnTy}
				c.ctx[e.Name] = funcTy
			}
		}

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
				localChecker := &Checker{ctx: localEnv, typeDefs: c.typeDefs, typeAliases: c.typeAliases}
				ty, err := localChecker.Infer(s.Value)
				if err != nil {
					return nil, err
				}
				localEnv[s.Name] = ty

			case syntax.FieldDef:
				localChecker := &Checker{ctx: localEnv, typeDefs: c.typeDefs, typeAliases: c.typeAliases}
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
				ty, err := c.elaborateTypeWithDefs(param.Type)
				if err != nil {
					return nil, err
				}
				localEnv[param.Name] = ty
				exposedParams = append(exposedParams, param.Name)
			} else {
				localChecker := &Checker{ctx: localEnv, typeDefs: c.typeDefs, typeAliases: c.typeAliases}
				ty, err := localChecker.Infer(param.Value)
				if err != nil {
					return nil, err
				}
				if param.Type != nil {
					annotatedTy, err := c.elaborateTypeWithDefs(param.Type)
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

		bodyChecker := &Checker{ctx: localEnv, typeDefs: c.typeDefs, typeAliases: c.typeAliases}
		resultTy, err := bodyChecker.Infer(e.Body)
		if err != nil {
			return nil, err
		}

		if e.ReturnType != nil {
			annotatedReturnTy, err := c.elaborateTypeWithDefs(e.ReturnType)
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

	case syntax.VariantConstruct:
		variantFound := false
		var variantType TRecord
		var sumType TSum

		for _, sumTy := range c.typeDefs {
			if variantRec, ok := sumTy.Variants[e.Variant]; ok {
				variantFound = true
				variantType = variantRec
				sumType = sumTy
				break
			}
		}

		if !variantFound {
			return nil, fmt.Errorf("unknown variant: %s", e.Variant)
		}

		providedFields := make(map[string]Type)
		for _, field := range e.Fields {
			ty, err := c.Infer(field.Value)
			if err != nil {
				return nil, err
			}
			providedFields[field.Name] = ty
		}

		if len(providedFields) != len(variantType.Fields) {
			return nil, fmt.Errorf("variant %s expects %d fields, got %d", e.Variant, len(variantType.Fields), len(providedFields))
		}

		for fieldName, expectedTy := range variantType.Fields {
			providedTy, ok := providedFields[fieldName]
			if !ok {
				return nil, fmt.Errorf("missing field %s in variant %s", fieldName, e.Variant)
			}
			if !typeEqual(expectedTy, providedTy) {
				return nil, fmt.Errorf("field %s has type %v, expected %v", fieldName, providedTy, expectedTy)
			}
		}

		return sumType, nil

	case syntax.Match:
		scrutineeTy, err := c.Infer(e.Scrutinee)
		if err != nil {
			return nil, err
		}

		sumTy, ok := scrutineeTy.(TSum)
		if !ok {
			return nil, fmt.Errorf("match requires sum type, got %v", scrutineeTy)
		}

		if err := c.checkExhaustiveness(sumTy, e.Cases); err != nil {
			return nil, err
		}

		if len(e.Cases) == 0 {
			return nil, fmt.Errorf("match must have at least one case")
		}

		var resultTy Type
		for i, matchCase := range e.Cases {
			localEnv := make(map[string]Type)
			maps.Copy(localEnv, c.ctx)

			if err := c.bindPattern(sumTy, matchCase.Pattern, localEnv); err != nil {
				return nil, err
			}

			caseChecker := &Checker{ctx: localEnv, typeDefs: c.typeDefs, typeAliases: c.typeAliases}
			caseTy, err := caseChecker.Infer(matchCase.Body)
			if err != nil {
				return nil, err
			}

			if i == 0 {
				resultTy = caseTy
			} else {
				if !typeEqual(resultTy, caseTy) {
					return nil, fmt.Errorf("match cases must have same type: got %v and %v", resultTy, caseTy)
				}
			}
		}

		return resultTy, nil

	case syntax.ArrayLit:
		if len(e.Elements) == 0 {
			return nil, fmt.Errorf("cannot infer type of empty array literal")
		}

		firstTy, err := c.Infer(e.Elements[0])
		if err != nil {
			return nil, err
		}

		for i, elem := range e.Elements[1:] {
			elemTy, err := c.Infer(elem)
			if err != nil {
				return nil, err
			}
			if !typeEqual(firstTy, elemTy) {
				return nil, fmt.Errorf("array element %d has type %v, expected %v", i+1, elemTy, firstTy)
			}
		}

		return TSized{Base: firstTy, Size: len(e.Elements)}, nil

	case syntax.Index:
		arrayTy, err := c.Infer(e.Array)
		if err != nil {
			return nil, err
		}

		indexTy, err := c.Infer(e.Index)
		if err != nil {
			return nil, err
		}

		if _, ok := indexTy.(TInt); !ok {
			return nil, fmt.Errorf("array index must be Int, got %v", indexTy)
		}

		switch at := arrayTy.(type) {
		case TSized:
			return at.Base, nil
		case TSlice:
			return at.Base, nil
		default:
			return nil, fmt.Errorf("cannot index non-array type %v", arrayTy)
		}

	case syntax.Slice:
		arrayTy, err := c.Infer(e.Array)
		if err != nil {
			return nil, err
		}

		if e.Start != nil {
			startTy, err := c.Infer(e.Start)
			if err != nil {
				return nil, err
			}
			if _, ok := startTy.(TInt); !ok {
				return nil, fmt.Errorf("slice start must be Int, got %v", startTy)
			}
		}

		if e.End != nil {
			endTy, err := c.Infer(e.End)
			if err != nil {
				return nil, err
			}
			if _, ok := endTy.(TInt); !ok {
				return nil, fmt.Errorf("slice end must be Int, got %v", endTy)
			}
		}

		switch at := arrayTy.(type) {
		case TSized:
			return TSlice{Base: at.Base}, nil
		case TSlice:
			return at, nil
		default:
			return nil, fmt.Errorf("cannot slice non-array type %v", arrayTy)
		}

	default:
		return nil, fmt.Errorf("unknown expression type")
	}
}

func (c *Checker) bindPattern(sumTy TSum, pattern syntax.Pattern, env map[string]Type) error {
	switch p := pattern.(type) {
	case syntax.PatternVariant:
		variantRec, ok := sumTy.Variants[p.Variant]
		if !ok {
			return fmt.Errorf("unknown variant %s for type %s", p.Variant, sumTy.Name)
		}

		if len(p.Fields) != len(variantRec.Fields) {
			return fmt.Errorf("variant %s expects %d fields, pattern has %d", p.Variant, len(variantRec.Fields), len(p.Fields))
		}

		i := 0
		for _, fieldTy := range variantRec.Fields {
			if i < len(p.Fields) {
				env[p.Fields[i]] = fieldTy
				i++
			}
		}

		return nil

	case syntax.PatternWildcard:
		return nil

	default:
		return fmt.Errorf("unknown pattern type")
	}
}

func (c *Checker) checkExhaustiveness(sumTy TSum, cases []syntax.MatchCase) error {
	coveredVariants := make(map[string]bool)

	for _, matchCase := range cases {
		switch p := matchCase.Pattern.(type) {
		case syntax.PatternVariant:
			coveredVariants[p.Variant] = true
		case syntax.PatternWildcard:
			for variant := range sumTy.Variants {
				coveredVariants[variant] = true
			}
		}
	}

	for variant := range sumTy.Variants {
		if !coveredVariants[variant] {
			return fmt.Errorf("non-exhaustive match: missing case for variant %s", variant)
		}
	}

	return nil
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
	case TSum:
		bt, ok := b.(TSum)
		if !ok {
			return false
		}
		return at.Name == bt.Name
	case TSized:
		bt, ok := b.(TSized)
		if !ok {
			return false
		}
		return at.Size == bt.Size && typeEqual(at.Base, bt.Base)
	case TSlice:
		bt, ok := b.(TSlice)
		if !ok {
			return false
		}
		return typeEqual(at.Base, bt.Base)
	default:
		return false
	}
}
