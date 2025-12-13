package totality

import (
	"fmt"
	"maps"

	"github.com/ethanthoma/auric/internal/syntax"
)

type CallGraph struct {
	edges map[string][]string
}

func NewCallGraph() *CallGraph {
	return &CallGraph{edges: make(map[string][]string)}
}

func (g *CallGraph) AddEdge(from, to string) {
	g.edges[from] = append(g.edges[from], to)
}

func (g *CallGraph) HasCycle() (bool, []string) {
	visited := make(map[string]bool)
	recStack := make(map[string]bool)
	var path []string

	var dfs func(string) bool
	dfs = func(node string) bool {
		visited[node] = true
		recStack[node] = true
		path = append(path, node)

		for _, neighbor := range g.edges[node] {
			if !visited[neighbor] {
				if dfs(neighbor) {
					return true
				}
			} else if recStack[neighbor] {
				cycleStart := -1
				for i, n := range path {
					if n == neighbor {
						cycleStart = i
						break
					}
				}
				if cycleStart >= 0 {
					return true
				}
			}
		}

		recStack[node] = false
		path = path[:len(path)-1]
		return false
	}

	for node := range g.edges {
		if !visited[node] {
			if dfs(node) {
				return true, path
			}
		}
	}

	return false, nil
}

type Analyzer struct {
	graph          *CallGraph
	currentFn      string
	bindings       map[string]bool
	structuralVars map[string]bool
}

func NewAnalyzer() *Analyzer {
	return &Analyzer{
		graph:          NewCallGraph(),
		bindings:       make(map[string]bool),
		structuralVars: make(map[string]bool),
	}
}

func (a *Analyzer) AnalyzeExpr(expr syntax.Expr) error {
	switch e := expr.(type) {
	case syntax.Lit, syntax.Var:
		return nil

	case syntax.Let:
		a.bindings[e.Name] = true
		oldFn := a.currentFn
		a.currentFn = e.Name

		if err := a.AnalyzeExpr(e.Value); err != nil {
			return err
		}

		a.currentFn = oldFn

		if e.Body != nil {
			return a.AnalyzeExpr(e.Body)
		}
		return nil

	case syntax.Record:
		for _, stmt := range e.Stmts {
			switch s := stmt.(type) {
			case syntax.LetBinding:
				if err := a.AnalyzeExpr(s.Value); err != nil {
					return err
				}
			case syntax.FieldDef:
				if err := a.AnalyzeExpr(s.Value); err != nil {
					return err
				}
			}
		}
		return nil

	case syntax.FieldAccess:
		return a.AnalyzeExpr(e.Record)

	case syntax.BinOp:
		if err := a.AnalyzeExpr(e.Left); err != nil {
			return err
		}
		return a.AnalyzeExpr(e.Right)

	case syntax.Into:
		for _, param := range e.Params {
			if param.Value != nil {
				if err := a.AnalyzeExpr(param.Value); err != nil {
					return err
				}
			}
		}
		return a.AnalyzeExpr(e.Body)

	case syntax.App:
		if err := a.AnalyzeExpr(e.Fn); err != nil {
			return err
		}

		if v, ok := e.Fn.(syntax.Var); ok {
			if a.bindings[v.Name] && a.currentFn != "" {
				isStructural := false
				for _, arg := range e.Args {
					if argVar, ok := arg.(syntax.Var); ok {
						if a.structuralVars[argVar.Name] {
							isStructural = true
							break
						}
					}
				}

				if !isStructural {
					a.graph.AddEdge(a.currentFn, v.Name)
				}
			}
		}

		for _, arg := range e.Args {
			if err := a.AnalyzeExpr(arg); err != nil {
				return err
			}
		}
		return nil

	case syntax.VariantConstruct:
		for _, field := range e.Fields {
			if err := a.AnalyzeExpr(field.Value); err != nil {
				return err
			}
		}
		return nil

	case syntax.Match:
		if err := a.AnalyzeExpr(e.Scrutinee); err != nil {
			return err
		}

		for _, c := range e.Cases {
			oldStructuralVars := make(map[string]bool)
			maps.Copy(oldStructuralVars, a.structuralVars)

			if pattern, ok := c.Pattern.(syntax.PatternVariant); ok {
				for _, field := range pattern.Fields {
					a.structuralVars[field] = true
				}
			}

			if err := a.AnalyzeExpr(c.Body); err != nil {
				return err
			}

			a.structuralVars = oldStructuralVars
		}
		return nil

	case syntax.ArrayLit:
		for _, elem := range e.Elements {
			if err := a.AnalyzeExpr(elem); err != nil {
				return err
			}
		}
		return nil

	case syntax.Index:
		if err := a.AnalyzeExpr(e.Array); err != nil {
			return err
		}
		return a.AnalyzeExpr(e.Index)

	case syntax.Slice:
		if err := a.AnalyzeExpr(e.Array); err != nil {
			return err
		}
		if e.Start != nil {
			if err := a.AnalyzeExpr(e.Start); err != nil {
				return err
			}
		}
		if e.End != nil {
			return a.AnalyzeExpr(e.End)
		}
		return nil

	default:
		return nil
	}
}

func Check(program syntax.Program) error {
	analyzer := NewAnalyzer()
	if err := analyzer.AnalyzeExpr(program.Expr); err != nil {
		return err
	}

	hasCycle, path := analyzer.graph.HasCycle()
	if hasCycle {
		return fmt.Errorf("recursive function detected (not allowed yet): %v", path)
	}

	return nil
}
