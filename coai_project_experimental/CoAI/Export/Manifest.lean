import CoAI.CertifiedStack
import CoAI.NormalizedAttention

set_option pp.universes false
set_option pp.all false
set_option pp.explicit false

def printBegin (s : String) : IO Unit := IO.println s!"BEGIN {s}"
def printEnd   (s : String) : IO Unit := IO.println s!"END {s}"

-- Add exactly the Lean theorems you want to cite as justification for engine rewrite rules.

#eval printBegin "StochasticAttention.attnKernel_factorize"
#check StochasticAttention.attnKernel_factorize
#print axioms StochasticAttention.attnKernel_factorize
#eval printEnd "StochasticAttention.attnKernel_factorize"

#eval printBegin "Matrix.mul_assoc"
#check Matrix.mul_assoc
#print axioms Matrix.mul_assoc
#eval printEnd "Matrix.mul_assoc"

#eval printBegin "Matrix.transpose_transpose"
#check Matrix.transpose_transpose
#print axioms Matrix.transpose_transpose
#eval printEnd "Matrix.transpose_transpose"

#eval printBegin "Matrix.transpose_mul"
#check Matrix.transpose_mul
#print axioms Matrix.transpose_mul
#eval printEnd "Matrix.transpose_mul"

#eval printBegin "Matrix.one_mul"
#check Matrix.one_mul
#print axioms Matrix.one_mul
#eval printEnd "Matrix.one_mul"

#eval printBegin "Matrix.mul_one"
#check Matrix.mul_one
#print axioms Matrix.mul_one
#eval printEnd "Matrix.mul_one"

#eval printBegin "Matrix.transpose_one"
#check Matrix.transpose_one
#print axioms Matrix.transpose_one
#eval printEnd "Matrix.transpose_one"
