import os

file_path = "c:\\Users\\admin\\OneDrive\\Desktop\\CoAI Operandics Discovery Engine\\prover\\general_atp.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Enum import
content = content.replace("from typing import List", "from enum import Enum\nfrom typing import List, NamedTuple")

# 2. Remove SubsumptionIndex
subsumption_index_code = """class SubsumptionIndex:
    \"\"\"
    Lightweight length-indexed bucket system for $O(1)$ fast-path subsumption.
    Dramatically accelerates the forward subsumption check in the given-clause loop.
    \"\"\"
    def __init__(self):
        self.by_len = defaultdict(list)
        
    def add(self, clause: Clause):
        self.by_len[len(clause.literals)].append(clause)
        
    def is_subsumed(self, c: Clause) -> bool:
        c_len = len(c.literals)
        # c can only be subsumed by clauses of equal or strictly shorter length
        for l in range(1, c_len + 1):
            for candidate in self.by_len[l]:
                if subsumes(candidate, c):
                    return True
        return False"""
content = content.replace(subsumption_index_code, "")

# 3. Rename GeneralProver to ResolutionEngine
content = content.replace("class GeneralProver:", "class ResolutionEngine:")

# 4. Remove SubsumptionIndex usage in prove()
idx_init = """        # Subsumption Index for O(1) fast-path checks
        sub_index = SubsumptionIndex()
        for c in all_clauses:
            sub_index.add(c)"""
content = content.replace(idx_init, "")

idx_use = """                # Fast forward subsumption using index
                if nc not in processed and not sub_index.is_subsumed(nc):
                    unprocessed.append(nc)
                    sub_index.add(nc)"""
new_use = """                # Fast forward subsumption
                is_subsumed = any(subsumes(p, nc) for p in processed)
                if nc not in processed and not is_subsumed:
                    unprocessed.append(nc)"""
content = content.replace(idx_use, new_use)

# 5. Remove prove_with_normalization from ResolutionEngine
# We'll locate def prove_with_normalization and slice the file there,
# as it's the end portion of the class before diagnose_timeout.
# Wait, let's just use regex or find to cut everything after prove()
import re
match = re.search(r"    def prove_with_normalization\(self, goal: Formula, lemmas: List\[Formula\].*?(?=    def _collect_risk_terms)", content, flags=re.DOTALL)
if match:
    content = content.replace(match.group(0), "")

# 6. Append ProverStrategy, GoalClassification, and GeneralATP
suffix = '''
class ProverStrategy(Enum):
    EGRAPH_ONLY = "egraph"
    RESOLUTION_ONLY = "resolution"
    EGRAPH_THEN_RESOLUTION = "egraph_then_resolution"

class GoalClassification(NamedTuple):
    is_equational: bool
    eq_depth: int
    quant_depth: int

class GeneralATP:
    def __init__(self, strategy: ProverStrategy = ProverStrategy.EGRAPH_THEN_RESOLUTION):
        from discovery.normalization import RiskEGraph
        self.strategy = strategy
        self.egraph = RiskEGraph()
        self.resolution_engine = ResolutionEngine()

    def prove(self, conjecture: Formula, kb) -> ProofResult:
        if self.strategy == ProverStrategy.EGRAPH_THEN_RESOLUTION:
            return self._layered_prove(conjecture, kb)
        elif self.strategy == ProverStrategy.EGRAPH_ONLY:
            return self._egraph_prove(conjecture, kb)
        else:
            return self._resolution_prove(conjecture, kb)

    def _layered_prove(self, conjecture: Formula, kb):
        classification = self._classify_goal(conjecture)

        if classification.is_equational:
            result = self._egraph_prove(conjecture, kb)
            if result.success or result.reason == "EGRAPH_NORMALIZATION":
                return result

        return self._resolution_prove(conjecture, kb)

    def _classify_goal(self, conjecture: Formula) -> GoalClassification:
        # Simple structural analysis
        # Count quantifier depth
        q_depth = 0
        curr = conjecture
        while isinstance(curr, (cl.Forall, cl.Exists)):
            q_depth += 1
            curr = curr.body
            
        is_eq = isinstance(curr, cl.Equality)
        eq_depth = 1 if is_eq else 0
        
        return GoalClassification(
            is_equational=(is_eq and q_depth <= 1),
            eq_depth=eq_depth,
            quant_depth=q_depth
        )

    def _egraph_prove(self, conjecture: Formula, kb) -> ProofResult:
        from discovery.normalization import (
            extract_risk_subterms, logic_to_egraph_term, 
            ERewrite, saturate_with_rewrites
        )
        
        target_goal = conjecture
        while isinstance(target_goal, cl.Forall):
            target_goal = target_goal.body
            
        if not isinstance(target_goal, cl.Equality):
            return ProofResult(success=False, reason="NOT_EQUATIONAL")
            
        def complexity(term):
            if isinstance(term, cl.Variable) or isinstance(term, cl.Constant): return 1
            if isinstance(term, cl.Function):
                return 1 + sum(complexity(a) for a in term.args)
            return 1
            
        rewrites = []
        for item in kb.axioms + kb.theorems:
            curr = item
            while isinstance(curr, cl.Forall):
                curr = curr.body
            if isinstance(curr, cl.Equality):
                l_term, r_term = curr.left, curr.right
                if complexity(l_term) >= complexity(r_term):
                    lhs, rhs = l_term, r_term
                else:
                    lhs, rhs = r_term, l_term
                rewrites.append(ERewrite(
                    lhs=logic_to_egraph_term(lhs),
                    rhs=logic_to_egraph_term(rhs),
                    name=f"rule_{len(rewrites)}"
                ))
                
        # Add risk terms
        all_logic_terms = extract_risk_subterms(conjecture)
        for ax in kb.axioms + kb.theorems:
            all_logic_terms.extend(extract_risk_subterms(ax))
            
        for lt in set(all_logic_terms):
            self.egraph.add(logic_to_egraph_term(lt))
            
        l_id = self.egraph.add(logic_to_egraph_term(target_goal.left))
        r_id = self.egraph.add(logic_to_egraph_term(target_goal.right))
        
        saturate_with_rewrites(self.egraph, rewrites)
        
        if self.egraph.find(l_id) == self.egraph.find(r_id):
            return ProofResult(
                success=True, steps=0,
                proved_formula=conjecture,
                reason="EGRAPH_NORMALIZATION"
            )
            
        return ProofResult(success=False, reason="EGRAPH_FAILED")

    def _resolution_prove(self, conjecture: Formula, kb) -> ProofResult:
        # Load axioms into the resolution engine dynamically
        self.resolution_engine.axioms = []
        self.resolution_engine._axiom_clauses = []
        for ax in kb.axioms + kb.theorems:
            self.resolution_engine.add_axiom(ax)
        return self.resolution_engine.prove(conjecture)
'''
content += suffix

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored general_atp.py successfully.")
