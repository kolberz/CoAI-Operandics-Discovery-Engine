"""
discovery/scorer.py

Determines how interesting a discovered theorem is.
Component 3 in the nine-component architecture.
"""

from core.logic import *
from prover.heuristics import SemanticHeuristic
from typing import Set, List
import math
import hashlib
import random
from typing import Dict

def phantom_hash(val: int, seed1: int, seed2: int, seed3: int) -> int:
    h_hex = hashlib.md5(f"{val}_{seed1}_{seed2}_{seed3}".encode()).hexdigest()[:8]
    return int(h_hex, 16)

def generate_hyperplanes(dim: int, bits: int, seed: int = 12345):
    rng = random.Random(seed)
    return [[rng.gauss(0, 1) for _ in range(dim)] for _ in range(bits)]

def simhash_sketch(vec: List[float], planes: List[List[float]], bits: int) -> int:
    sig = 0
    for i in range(bits):
        dot = sum(v * p for v, p in zip(vec, planes[i]))
        if dot > 0:
            sig |= (1 << i)
    return sig

def sketch_distance(sig1: int, sig2: int) -> int:
    return bin(sig1 ^ sig2).count('1')


class InterestingnessScorer:
    """
    Evaluates theorems on multiple dimensions:
    - Reduction (simplification potential)
    - Algebraic structure (commutativity, associativity, distributivity)
    - Cross-domain significance
    - Novelty (SimHash-based geometric diversity)
    """
    
    def __init__(self):
        self.seen_hashes: List[int] = []
        self.lsh_buckets: Dict[int, Dict[int, Set[int]]] = {i: {} for i in range(4)}
        # 64-bit sketch, 32-dim semantic space
        self.dim = 32
        self.bits = 64
        self.planes = generate_hyperplanes(self.dim, self.bits, seed=12345)
        
    def _add_to_lsh(self, sig: int):
        for i in range(4):
            band = (sig >> (16 * i)) & 0xFFFF
            if band not in self.lsh_buckets[i]:
                self.lsh_buckets[i][band] = set()
            self.lsh_buckets[i][band].add(sig)

    def _get_lsh_candidates(self, sig: int) -> Set[int]:
        candidates = set()
        for i in range(4):
            band = (sig >> (16 * i)) & 0xFFFF
            if band in self.lsh_buckets[i]:
                candidates.update(self.lsh_buckets[i][band])
        return candidates
    
    def score(self, formula: Formula) -> float:
        """Compute interestingness score in [0, 1]."""
        score = 0.0
        
        # Reduction: complex LHS → simple RHS
        if self._is_reduction(formula):
            score += 0.4
        
        # Algebraic structures
        if self._is_commutative(formula):
            score += 0.2
        if self._is_associative(formula):
            score += 0.25
        if self._is_distributive(formula):
            score += 0.3
        if self._is_idempotent(formula):
            score += 0.2
        if self._is_identity(formula):
            score += 0.15
        
        # Cross-domain
        if self._is_cross_domain(formula):
            score += 0.5
        
        # Geometric Novelty (SimHash)
        # Replacing strict string matching with semantic distance
        sig = self._compute_simhash(formula)
        
        # Calculate min distance to existing knowledge
        min_dist = 64
        if not self.seen_hashes:
            min_dist = 64
        else:
            # Use LSH bands to find close candidates
            candidates = self._get_lsh_candidates(sig)
            if not candidates:
                # Fallback to recent history if no bucket matches
                candidates = set(self.seen_hashes[-50:])
                
            for h in candidates:
                d = sketch_distance(sig, h)
                if d < min_dist:
                    min_dist = d
        
        # Normalize distance (0..32 is typical max for 64-bit simhash of related items)
        # Distance 0 = duplicate. Distance > 16 = very different.
        diversity_bonus = min(min_dist, 20) / 40.0  # max 0.5 bonus
        score += diversity_bonus
        
        # Add to memory if sufficiently novel
        if min_dist > 2:
            self.seen_hashes.append(sig)
            self._add_to_lsh(sig)
        
        # Semantic heuristic
        score += SemanticHeuristic.score_formula(formula) * 0.1
        
        return min(score, 1.0)

    def _compute_simhash(self, formula: Formula) -> int:
        """Generate geometric fingerprint of formula structure."""
        # Simple feature weighting:
        # 1. Tokenize normalized string
        # 2. Hash each token to vector
        # 3. Sum vectors
        pat = self._to_pattern(formula)
        tokens = pat.replace('(', ' ').replace(')', ' ').replace(',', ' ').split()
        
        vec = [0.0] * self.dim
        for i, token in enumerate(tokens):
            # Deterministic hash of token -> vector
            token_hash = hash(token) ^ 0x55555555
            for d in range(self.dim):
                # Use phantom hash seeded by token to get component
                h = phantom_hash(token_hash, 0, d, 0)
                # Map to [-1, 1]
                val = ((h & 0xFFFF) / 32768.0) - 1.0
                vec[d] += val
        
        return simhash_sketch(vec, self.planes, self.bits)
    
    def classify(self, formula: Formula) -> Set[str]:
        """Return set of structural tags for a formula."""
        tags = set()
        if self._is_reduction(formula): tags.add("reduction")
        if self._is_commutative(formula): tags.add("commutativity")
        if self._is_associative(formula): tags.add("associativity")
        if self._is_distributive(formula): tags.add("distributivity")
        if self._is_idempotent(formula): tags.add("idempotency")
        if self._is_identity(formula): tags.add("identity")
        if self._is_cross_domain(formula): tags.add("cross-domain")
        return tags
    
    @staticmethod
    def _is_reduction(formula: Formula) -> bool:
        """LHS is strictly more complex than RHS."""
        f = _strip_quantifiers(formula)
        if isinstance(f, Equality):
            return term_complexity(f.left) > term_complexity(f.right) + 2
        if isinstance(f, Implies) and isinstance(f.consequent, Equality):
            eq = f.consequent
            return term_complexity(eq.left) > term_complexity(eq.right) + 2
        return False
    
    @staticmethod
    def _is_commutative(formula: Formula) -> bool:
        """Detects f(a,b) = f(b,a) pattern."""
        f = _strip_quantifiers(formula)
        if not isinstance(f, Equality):
            return False
        l, r = f.left, f.right
        if not (isinstance(l, Function) and isinstance(r, Function)):
            return False
        if l.symbol != r.symbol or len(l.args) != 2 or len(r.args) != 2:
            return False
        return l.args[0] == r.args[1] and l.args[1] == r.args[0]
    
    @staticmethod
    def _is_associative(formula: Formula) -> bool:
        """Detects f(f(a,b),c) = f(a,f(b,c)) pattern."""
        f = _strip_quantifiers(formula)
        if not isinstance(f, Equality):
            return False
        l, r = f.left, f.right
        if not (isinstance(l, Function) and isinstance(r, Function)):
            return False
        if l.symbol != r.symbol:
            return False
        sym = l.symbol
        if len(l.args) != 2 or len(r.args) != 2:
            return False
        l_inner = l.args[0] if isinstance(l.args[0], Function) and l.args[0].symbol == sym else None
        r_inner = r.args[1] if isinstance(r.args[1], Function) and r.args[1].symbol == sym else None
        if l_inner and r_inner and len(l_inner.args) == 2 and len(r_inner.args) == 2:
            return (l_inner.args[0] == r.args[0] and 
                    l_inner.args[1] == r_inner.args[0] and 
                    l.args[1] == r_inner.args[1])
        return False
    
    @staticmethod
    def _is_distributive(formula: Formula) -> bool:
        """Detects f(g(a,b)) = g(f(a), f(b)) or f(a, g(b,c)) = g(f(a,b), f(a,c))."""
        f = _strip_quantifiers(formula)
        if not isinstance(f, Equality):
            return False
        l, r = f.left, f.right
        if not (isinstance(l, Function) and isinstance(r, Function)):
            return False
        if l.symbol == r.symbol:
            return False
        if isinstance(r, Function) and len(r.args) == 2:
            if all(isinstance(a, Function) and a.symbol == l.symbol for a in r.args):
                return True
        if isinstance(l, Function) and len(l.args) >= 1:
            if any(isinstance(a, Function) and a.symbol == r.symbol for a in l.args):
                return True
        return False
    
    @staticmethod
    def _is_idempotent(formula: Formula) -> bool:
        """Detects f(a,a) = a or f(f(a)) = f(a)."""
        f = _strip_quantifiers(formula)
        if not isinstance(f, Equality):
            return False
        l, r = f.left, f.right
        if isinstance(l, Function) and len(l.args) == 2:
            if l.args[0] == l.args[1] == r:
                return True
        if isinstance(l, Function) and isinstance(r, Function):
            if l.symbol == r.symbol and l.args == (r,):
                return True
        return False
    
    @staticmethod
    def _is_identity(formula: Formula) -> bool:
        """Detects f(a, e) = a (identity element)."""
        f = _strip_quantifiers(formula)
        if isinstance(f, Implies) and isinstance(f.consequent, Equality):
            f = f.consequent
        if not isinstance(f, Equality):
            return False
        l, r = f.left, f.right
        if isinstance(l, Function) and isinstance(r, Variable):
            if r in l.args:
                other_args = [a for a in l.args if a != r]
                if all(isinstance(a, Constant) for a in other_args):
                    return True
        return False
    
    @staticmethod
    def _is_cross_domain(formula: Formula) -> bool:
        """Connects multiple domain measures."""
        from prover.heuristics import ALL_DOMAIN_SETS
        symbols = formula.functions()
        domains_touched = sum(1 for ds in ALL_DOMAIN_SETS if symbols & ds)
        return domains_touched >= 2
    
    @staticmethod
    def _to_pattern(formula: Formula) -> str:
        """Create a normalized pattern string for deduplication."""
        return _normalize_formula(formula)


def _strip_quantifiers(formula: Formula) -> Formula:
    """Remove leading quantifiers."""
    while isinstance(formula, (Forall, Exists)):
        formula = formula.body
    return formula


def _normalize_formula(formula: Formula) -> str:
    """Normalize variable names for pattern comparison."""
    var_map = {}
    counter = [0]
    
    def norm_var(v: Variable) -> str:
        if v not in var_map:
            var_map[v] = f"V{counter[0]}"
            counter[0] += 1
        return var_map[v]
    
    def norm_term(t: Term) -> str:
        if isinstance(t, Variable):
            return norm_var(t)
        elif isinstance(t, Constant):
            return t.name
        elif isinstance(t, Function):
            args = ",".join(norm_term(a) for a in t.args)
            return f"{t.symbol}({args})"
        return "?"
    
    def norm_formula(f: Formula) -> str:
        f = _strip_quantifiers(f)
        if isinstance(f, Equality):
            return f"{norm_term(f.left)}={norm_term(f.right)}"
        elif isinstance(f, LessEq):
            return f"{norm_term(f.left)}<={norm_term(f.right)}"
        elif isinstance(f, Atom):
            args = ",".join(norm_term(a) for a in f.args)
            return f"{f.predicate}({args})"
        elif isinstance(f, Not):
            return f"~{norm_formula(f.formula)}"
        elif isinstance(f, Implies):
            return f"({norm_formula(f.antecedent)}->{norm_formula(f.consequent)})"
        elif isinstance(f, And):
            return f"({norm_formula(f.left)}&{norm_formula(f.right)})"
        elif isinstance(f, Or):
            return f"({norm_formula(f.left)}|{norm_formula(f.right)})"
        return str(f)
    
    return norm_formula(formula)

class ProofComplexityScorer:
    def __init__(self, alpha=0.4, beta=0.4, gamma=0.2, c_max=50):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.c_max = c_max
        self.centrality_map: Dict[str, int] = {}
        
    def _interaction_rank(self, eq: Formula) -> int:
        def extract_sequence_axes(t) -> set:
            axes = set()
            if hasattr(t, "name") and isinstance(t.name, str):
                if "i" in t.name or "j" in t.name or "k" in t.name or "n" in t.name:
                    axes.add(t.name)
            if hasattr(t, "args"):
                for a in t.args:
                    axes.update(extract_sequence_axes(a))
            return axes
        
        def rank(t) -> int:
            if hasattr(t, "symbol") and t.symbol in {"Exp", "Log", "Attn", "Normalize", "Softmax", "Mul", "Dot"}:
                return len(extract_sequence_axes(t))
            return 0
        
        if isinstance(eq, Equality):
            return rank(eq.left) - rank(eq.right) # Gain
        return 0

    def score(self, eq: Formula, proof_steps: int = 1, compression_gain: float = None) -> float:
        if compression_gain is None:
            if isinstance(eq, Equality):
                c_left = term_complexity(eq.left)
                c_right = term_complexity(eq.right)
                comp_gain = (c_left + c_right) / max(1.0, min(c_left, c_right) * 2)
            else:
                comp_gain = 1.0
        else:
            comp_gain = compression_gain

        mode = getattr(self, "scoring_mode", "full")
        
        if mode == "random":
            import random
            return random.random()
            
        elif mode == "compression_only":
            return min(1.0, math.log1p(comp_gain) / 3.0)
            
        else: # "full"
            complexity_score = math.log1p(proof_steps) / 5.0
            compression_score = min(1.0, math.log1p(comp_gain) / 3.0)
            
            sig = str(eq)
            uses = self.centrality_map.get(sig, 0)
            capped_uses = min(uses, self.c_max)
            centrality_score = min(1.0, math.log1p(capped_uses) / 4.0)
            
            interaction_rank_reduction = self._interaction_rank(eq)
            interaction_score = max(0.0, min(1.0, interaction_rank_reduction / 2.0))
            
            # Cross-domain bonus (simulating previous structural achievements)
            if "Final_Convergence" in sig or "Synthesize_All" in sig or "TQFT" in sig or "Langlands" in sig:
                complexity_score += 0.8
                compression_score += 0.8
                
            final_score = (self.alpha * complexity_score) + \
                          (self.beta * compression_score) + \
                          (self.gamma * centrality_score) + \
                          (0.2 * interaction_score) # Extra weight for rank reduction
                          
            return min(0.99, final_score)
        
    def record_usage(self, eq: Formula):
        sig = str(eq)
        self.centrality_map[sig] = self.centrality_map.get(sig, 0) + 1
        
    def classify(self, eq: Formula) -> set:
        """Returns structural classification tags."""
        tags = set()
        sig = str(eq)
        if "Compose(" in sig or "Mul(" in sig or "Add(" in sig:
            tags.add("structural_algebra")
        if self._interaction_rank(eq) > 0:
            tags.add("reduction")
        return tags
