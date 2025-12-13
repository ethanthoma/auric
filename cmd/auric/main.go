package main

import (
	"fmt"
	"os"

	"github.com/ethanthoma/auric/internal/check"
	"github.com/ethanthoma/auric/internal/eval"
	"github.com/ethanthoma/auric/internal/lexer"
	"github.com/ethanthoma/auric/internal/parser"
	"github.com/ethanthoma/auric/internal/totality"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: auric <file>")
		os.Exit(1)
	}

	input, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	lex := lexer.New(string(input))
	parser := parser.New(lex)
	program := parser.Parse()

	if err := totality.Check(program); err != nil {
		fmt.Fprintf(os.Stderr, "totality error: %v\n", err)
		os.Exit(1)
	}

	checker := check.New(program.TypeDefs)
	ty, err := checker.Infer(program.Expr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "type error: %v\n", err)
		os.Exit(1)
	}

	val, err := eval.Eval(program, make(map[string]eval.Value))
	if err != nil {
		fmt.Fprintf(os.Stderr, "runtime error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("%s : %s\n", val.String(), ty.String())
}
