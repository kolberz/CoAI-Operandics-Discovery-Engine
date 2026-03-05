import os
import re

file_path = "c:\\Users\\admin\\OneDrive\\Desktop\\CoAI Operandics Discovery Engine\\discovery\\engine.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add KnowledgeBase and refactor _verify_worker
worker_code = """
from dataclasses import dataclass, field
from copy import deepcopy

@dataclass
class KnowledgeBase:
    axioms: List[Formula] = field(default_factory=list)
    theorems: List[Formula] = field(default_factory=list)
    
    def contains(self, formula: Formula) -> bool:
        f_str = str(formula)
        return any(str(a) == f_str for a in self.axioms + self.theorems)

def _verify_worker(args):
    conj, kb_snapshot, max_steps, timeout = args
    from prover.general_atp import GeneralATP, ProverStrategy
    verifier = GeneralATP(strategy=ProverStrategy.EGRAPH_THEN_RESOLUTION)
    res = verifier.prove(conj, kb_snapshot)
    return conj, res
"""

# Replace existing _verify_worker
old_worker_pattern = r"def _verify_worker\(args\):.*?(?=\nclass CoAIOperandicsExplorer:)"
content = re.sub(old_worker_pattern, worker_code.strip() + "\n", content, flags=re.DOTALL)

# 2. Add _merge_consistent method to CoAIOperandicsExplorer
merge_code = """
    def _merge_consistent(self, new_theorems: List[DiscoveredTheorem]) -> List[DiscoveredTheorem]:
        \"\"\"Only add theorems that don't contradict existing knowledge.\"\"\"
        accepted = []
        kb_set = {str(a) for a in self.axioms + self.lemmas}
        for thm in new_theorems:
            negation = thm.formula.negate()
            if str(negation) not in kb_set:
                accepted.append(thm)
                kb_set.add(str(thm.formula))
            else:
                self.counter_axioms.append(thm.formula)
        return accepted
"""
# Insert after __init__ logic
content = content.replace("def _init_knowledge_base(self):", merge_code + "\n    def _init_knowledge_base(self):")


# 3. Refactor Phase 3 to use the new parallel deepcopy and _merge_consistent
phase3_old = """            import multiprocessing\n            pool_args = [(c, self.axioms, self.lemmas, 1500, 15.0) for c in conjectures]\n            with multiprocessing.Pool() as pool:\n                verify_results = pool.map(_verify_worker, pool_args)"""

phase3_new = """            import multiprocessing
            pool_args = []
            for c in conjectures:
                kb_snapshot = KnowledgeBase(axioms=deepcopy(self.axioms), theorems=deepcopy(self.lemmas))
                pool_args.append((c, kb_snapshot, 1500, 15.0))
            
            with multiprocessing.Pool() as pool:
                verify_results = pool.map(_verify_worker, pool_args)"""

content = content.replace(phase3_old, phase3_new)

# Apply _merge_consistent on the collected proven_lemmas before moving on
phase4_hook = "            # ── PHASE 4: FAILURE ANALYSIS"
phase4_new = """            # Merge consistent
            proven_lemmas = self._merge_consistent(proven_lemmas)
            
            # ── PHASE 4: FAILURE ANALYSIS"""
content = content.replace(phase4_hook, phase4_new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored engine.py successfully.")
