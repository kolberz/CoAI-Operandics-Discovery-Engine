import os

file_path = "c:\\Users\\admin\\OneDrive\\Desktop\\CoAI Operandics Discovery Engine\\main.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace imports
content = content.replace("from prover.general_atp import GeneralProver", "from prover.general_atp import GeneralATP\nfrom discovery.engine import KnowledgeBase")

# In run_basic_proof_test
old_test1 = """    prover = GeneralProver()
    
    m1 = Variable("M1", MODULE)
    m2 = Variable("M2", MODULE)
    
    def Seq(a, b): return Function("Seq", (a, b), MODULE)
    def Risk(m): return Function("Risk", (m,), REAL)
    def plus(a, b): return Function("plus", (a, b), REAL)
    
    ID_M = Constant("ID_M", MODULE)
    R_ZERO = Constant("R_ZERO", REAL)
    
    # Add axioms
    prover.add_axiom(Forall(m1, Equality(Seq(m1, ID_M), m1)))
    prover.add_axiom(Forall(m1, Forall(m2,
        Equality(Risk(Seq(m1, m2)), plus(Risk(m1), Risk(m2)))
    )))
    prover.add_axiom(Equality(Risk(ID_M), R_ZERO))
    prover.add_axiom(Forall(m1, Equality(plus(m1, R_ZERO), m1)))
    
    # Test 1: Risk(Seq(M1, ID_M)) = Risk(M1)
    test_var = Variable("X", MODULE)
    goal = Equality(Risk(Seq(test_var, ID_M)), Risk(test_var))
    
    print(f"\\n  Test 1: {goal}")
    result = prover.prove(goal, max_steps=500)"""

new_test1 = """    prover = GeneralATP()
    kb = KnowledgeBase()
    
    m1 = Variable("M1", MODULE)
    m2 = Variable("M2", MODULE)
    
    def Seq(a, b): return Function("Seq", (a, b), MODULE)
    def Risk(m): return Function("Risk", (m,), REAL)
    def plus(a, b): return Function("plus", (a, b), REAL)
    
    ID_M = Constant("ID_M", MODULE)
    R_ZERO = Constant("R_ZERO", REAL)
    
    # Add axioms
    kb.axioms.append(Forall(m1, Equality(Seq(m1, ID_M), m1)))
    kb.axioms.append(Forall(m1, Forall(m2,
        Equality(Risk(Seq(m1, m2)), plus(Risk(m1), Risk(m2)))
    )))
    kb.axioms.append(Equality(Risk(ID_M), R_ZERO))
    kb.axioms.append(Forall(m1, Equality(plus(m1, R_ZERO), m1)))
    
    # Test 1: Risk(Seq(M1, ID_M)) = Risk(M1)
    test_var = Variable("X", MODULE)
    goal = Equality(Risk(Seq(test_var, ID_M)), Risk(test_var))
    
    print(f"\\n  Test 1: {goal}")
    result = prover.prove(goal, kb)"""

content = content.replace(old_test1, new_test1)

# Fix Test 2
content = content.replace("result2 = prover.prove(goal2, max_steps=300, timeout_seconds=5.0)", "result2 = prover.prove(goal2, kb)")


# In run_targeted_proofs
old_target = """    explorer = CoAIOperandicsExplorer()
    
    prover = GeneralProver()
    for axiom in explorer.axioms:
        prover.add_axiom(axiom)"""

new_target = """    explorer = CoAIOperandicsExplorer()
    
    prover = GeneralATP()
    kb = KnowledgeBase(axioms=explorer.axioms)"""

content = content.replace(old_target, new_target)


# Fix the loop running over targets
old_loop = """        result = prover.prove(target, max_steps=1800, timeout_seconds=15.0)"""
new_loop = """        result = prover.prove(target, kb)"""

content = content.replace(old_loop, new_loop)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated main.py")
