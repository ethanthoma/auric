import sys
from pathlib import Path

from auric.evaluator import Env, evaluate, type_of
from auric.tt_parser import parse_with_tt_macros as parse


def run_file(file_path: str):
    """Run an Auric source file."""
    path = Path(file_path)

    if not path.exists():
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)

    if not path.suffix == ".au":
        print(f"Warning: File extension is '{path.suffix}', expected '.au'")

    print(f"Running {path.name}...")
    print("=" * 60)

    # Read source
    source = path.read_text()

    try:
        # Parse
        sigs, defs = parse(source)
        print(f"✓ Parsed {len(defs)} definitions")

        # Separate and expand user-defined macros
        from auric.macro_expander import collect_macros, expand_macros as expand_user_macros, expand_expr as expand_user_macro_expr
        from auric.ast import Record as RecordAST

        macros, regular_defs = collect_macros(defs)

        if macros:
            print(f"✓ Found {len(macros)} user-defined macros")

            # Multi-pass expansion with const propagation for user-defined macros
            # First pass: expand without const values
            expanded_defs = expand_user_macros(regular_defs, macros)

            # Build const_defs from Record literals
            const_defs = {name: val for name, val in expanded_defs.items() if isinstance(val, RecordAST)}

            # Second pass: expand with const propagation (inline Records)
            if const_defs:
                expanded_defs = {
                    name: expand_user_macro_expr(expr, macros, const_defs)
                    for name, expr in expanded_defs.items()
                }

            print(f"✓ Expanded user-defined macros")
        else:
            expanded_defs = regular_defs

        # Expand expression-level macros (old system)
        from auric.macros import expand_macros as expand_expr_macros
        from auric.ast import Record as RecordAST
        from auric.staging import evaluate_consts_at_comptime

        # First pass: expand without const propagation
        first_pass = {name: expand_expr_macros(expr) for name, expr in expanded_defs.items()}

        # Automatic staging: normalize const values at compile-time
        normalized = evaluate_consts_at_comptime(first_pass)

        # Build const_defs for inlining (only Records for compile-time unrolling)
        # Now includes both original Records and normalized Records from staging
        const_defs = {name: val for name, val in normalized.items() if isinstance(val, RecordAST)}

        # Second pass: expand with const propagation (for loops unroll here)
        # Use normalized definitions so Records are already inlined
        final_defs = {name: expand_expr_macros(expr, const_defs) for name, expr in normalized.items()}
        print(f"✓ Expanded expression macros")

        # Final staging pass: normalize any new expressions from second expansion
        final_defs = evaluate_consts_at_comptime(final_defs)

        # Type check
        env: Env = {}
        types = {}
        for name, expr in final_defs.items():
            if name in sigs:
                types[name] = sigs[name]
        print(f"✓ Type checked successfully")

        for name, ty in types.items():
            print(f"  {name} : {ty}")

        # Evaluate
        print("\n" + "=" * 60)
        print("Evaluation:")
        print("=" * 60)

        values = evaluate(final_defs, env)

        for name, value in values.items():
            print(f"{name} = {value}")

        print("\n" + "=" * 60)
        print("✓ Completed successfully")

    except SyntaxError as e:
        print(f"\n✗ Syntax Error: {e}")
        sys.exit(1)
    except TypeError as e:
        print(f"\n✗ Type Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def repl():
    """Start an interactive REPL."""
    print("Auric REPL (Ctrl+D or 'exit' to quit)")
    print("=" * 60)

    env: Env = {}

    while True:
        try:
            line = input("auric> ")
            if line.strip() in ("exit", "quit"):
                break
            if not line.strip():
                continue

            # Try to parse and evaluate
            from auric.macros import expand_macros

            sigs, defs = parse(line)
            expanded_defs = {name: expand_macros(expr) for name, expr in defs.items()}
            types = type_of(line, env)  # Also expands internally
            values = evaluate(expanded_defs, env)

            # Update environment
            env.update(values)

            # Show results
            for name, value in values.items():
                ty = types.get(name, "?")
                print(f"{name} : {ty} = {value}")

        except EOFError:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\nUse Ctrl+D or 'exit' to quit")
            continue
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point for Auric CLI."""
    if len(sys.argv) > 1:
        # Run file mode
        file_path = sys.argv[1]
        run_file(file_path)
    else:
        # REPL mode
        repl()


if __name__ == "__main__":
    main()
