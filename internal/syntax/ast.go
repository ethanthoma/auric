package syntax

type Program struct {
	TypeDefs []TypeDef
	Expr     Expr
}

type TypeDef struct {
	Name     string
	Variants []VariantDef
	Alias    TypeExpr
}

type VariantDef struct {
	Name   string
	Fields []TyField
}

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

type Index struct {
	Array Expr
	Index Expr
}

type Slice struct {
	Array Expr
	Start Expr
	End   Expr
}

type ArrayLit struct {
	Elements []Expr
}

type VariantConstruct struct {
	Variant string
	Fields  []FieldDef
}

type Match struct {
	Scrutinee Expr
	Cases     []MatchCase
}

type MatchCase struct {
	Pattern Pattern
	Body    Expr
}

type Pattern interface {
	pattern()
}

type PatternVariant struct {
	Variant string
	Fields  []string
}

type PatternWildcard struct{}

func (PatternVariant) pattern()  {}
func (PatternWildcard) pattern() {}

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

type TySum struct {
	Name string
}

type TySized struct {
	Base TypeExpr
	Size SizeExpr
}

type SizeExpr interface {
	sizeExpr()
}

type SizeFixed struct {
	Size int
}

type SizeSlice struct{}

func (SizeFixed) sizeExpr() {}
func (SizeSlice) sizeExpr() {}

func (TyInt) typeExpr()    {}
func (TyRecord) typeExpr() {}
func (TyFunc) typeExpr()   {}
func (TySum) typeExpr()    {}
func (TySized) typeExpr()  {}

func (Lit) expr()              {}
func (Var) expr()              {}
func (Let) expr()              {}
func (Record) expr()           {}
func (FieldAccess) expr()      {}
func (BinOp) expr()            {}
func (Into) expr()             {}
func (App) expr()              {}
func (Index) expr()            {}
func (Slice) expr()            {}
func (ArrayLit) expr()         {}
func (VariantConstruct) expr() {}
func (Match) expr()            {}
