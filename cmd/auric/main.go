package main

import (
	"fmt"
	"os"

	"github.com/ethanthoma/auric/internal/check"
	"github.com/ethanthoma/auric/internal/eval"
	"github.com/ethanthoma/auric/internal/lexer"
	"github.com/ethanthoma/auric/internal/parser"
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
	expr := parser.Parse()

	checker := check.New()
	ty, err := checker.Infer(expr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "type error: %v\n", err)
		os.Exit(1)
	}

	val, err := eval.Eval(expr, make(map[string]eval.Value))
	if err != nil {
		fmt.Fprintf(os.Stderr, "runtime error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("%s : %s\n", val.String(), ty.String())
}
