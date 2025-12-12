package syntax

type Expr interface {
	expr()
}

type Lit struct {
	Value int
}

type Var struct {
	Name string
}

type Let struct {
	Name  string
	Value Expr
	Body  Expr
}

type Record struct {
	Stmts []RecordStmt
}

type RecordStmt interface {
	recordStmt()
}

type LetBinding struct {
	Name  string
	Value Expr
}

type FieldDef struct {
	Name  string
	Value Expr
}

func (LetBinding) recordStmt() {}
func (FieldDef) recordStmt()   {}

type FieldAccess struct {
	Record Expr
	Field  string
}

type BinOp struct {
	Op    string
	Left  Expr
	Right Expr
}

func (Lit) expr()         {}
func (Var) expr()         {}
func (Let) expr()         {}
func (Record) expr()      {}
func (FieldAccess) expr() {}
func (BinOp) expr()       {}
