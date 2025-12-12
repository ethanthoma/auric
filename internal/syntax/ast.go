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

type Into struct {
	Params     []Param
	ReturnType TypeExpr
	Body       Expr
}

type Param struct {
	Name  string
	Type  TypeExpr
	Value Expr
}

type App struct {
	Fn   Expr
	Args []Expr
}

type TypeExpr interface {
	typeExpr()
}

type TyInt struct{}

type TyRecord struct {
	Fields []TyField
}

type TyField struct {
	Name string
	Type TypeExpr
}

type TyFunc struct {
	Params []TypeExpr
	Result TypeExpr
}

func (TyInt) typeExpr()    {}
func (TyRecord) typeExpr() {}
func (TyFunc) typeExpr()   {}

func (Lit) expr()         {}
func (Var) expr()         {}
func (Let) expr()         {}
func (Record) expr()      {}
func (FieldAccess) expr() {}
func (BinOp) expr()       {}
func (Into) expr()        {}
func (App) expr()         {}
