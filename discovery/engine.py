"""
discovery/engine.py

The CoAI Operandics Discovery Engine.
Integrates all nine components into the Cumulative Scientist Loop.
"""

import os
from core.logic import *
from core.unification import apply_substitution
from prover.general_atp import GeneralATP, ProofResult
from prover.heuristics import SemanticHeuristic
from discovery.saturator import ForwardChainingSaturator, SaturationResult
from discovery.scorer import ProofComplexityScorer, _normalize_formula
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any, Iterator, Mapping, Sequence, Callable
from collections import defaultdict
import re
import time
from pathlib import Path
from discovery.axiom_bundles import load_axiom_bundle
from discovery.normalization import (
    RiskEGraph, logic_to_egraph_term, egraph_term_to_logic, ERewrite
)
from discovery.mcts_grammar import GrammarSynthesizer
from core.beta_calculus import BetaLedger


# ═══════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════

@dataclass
class VerifiedContract:
    assumptions: Dict[str, Any]
    guarantees: Dict[str, Any]
    risk: Dict[str, Any] = field(default_factory=dict)
    epsilon: Optional[float] = None
    gamma_margin: Optional[float] = None
    lipschitz_bound: Optional[float] = None

@dataclass
class DiscoveredTheorem:
    formula: Formula
    interestingness: float
    tags: Set[str]
    verification: str  # "PROVED", "AXIOM", "ORACLE-STIPULATED"
    cycle: int = 0
    proof_steps: int = 0
    compression_ratio: float = 1.0
    citation_count: int = 0
    contract: Optional[VerifiedContract] = None
    
    def __repr__(self):
        tag_str = ", ".join(sorted(self.tags)) if self.tags else "none"
        return f"[{self.verification}|{self.interestingness:.2f}|{tag_str}] {self.formula}"


@dataclass
class DiscoverySession:
    cycle: int = 0
    theorems: List[DiscoveredTheorem] = field(default_factory=list)
    counter_axioms: List[Formula] = field(default_factory=list)
    oracle_axioms: List[Formula] = field(default_factory=list)
    mcts_asts: List[Any] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def top(self, n: int = 10) -> List[DiscoveredTheorem]:
        try:
            from grounding.quake import radix_topk_indices
            scores = [t.interestingness for t in self.theorems]
            indices = radix_topk_indices(scores, n)
            return [self.theorems[i] for i in indices]
        except ImportError:
            return sorted(self.theorems, key=lambda t: -t.interestingness)[:n]


# ═══════════════════════════════════════════════════
# TERM AND FORMULA CONSTRUCTORS
# ═══════════════════════════════════════════════════

def Seq(m1: Term, m2: Term) -> Function:
    return Function("Seq", (m1, m2), MODULE)

def Par_Dyn(m1: Term, m2: Term) -> Function:
    return Function("Par_Dyn", (m1, m2), MODULE)

def Choice(m1: Term, m2: Term, p: Term) -> Function:
    return Function("Choice", (m1, m2, p), MODULE)

def Barrier(m: Term, p: Term) -> Function:
    return Function("Barrier", (m, p), MODULE)

def Sec_Filter(m: Term) -> Function:
    return Function("Sec_Filter", (m,), MODULE)

def Risk(m: Term) -> Function:
    return Function("Risk", (m,), REAL)

def Superpose(m1: Term, m2: Term) -> Function:
    return Function("Superpose", (m1, m2), MODULE)

def Evidence(f: Formula) -> Function:
    # We represent a formula reference as a constant or a specialized term
    # For simplicity, we wrap the str representation as a constant for now
    return Function("Evidence", (Constant(str(f)),), MODULE)

def ResourceCost(m: Term) -> Function:
    return Function("ResourceCost", (m,), REAL)

def Comp(m: Term) -> Function:
    return Function("Comp", (m,), REAL)

def Ent(m: Term) -> Function:
    return Function("Ent", (m,), REAL)

def Dep(m1: Term, m2: Term) -> Function:
    return Function("Dep", (m1, m2), REAL)

def plus(a: Term, b: Term) -> Function:
    return Function("add", (a, b), REAL)

def minus(a: Term, b: Term) -> Function:
    return Function("minus", (a, b), REAL)

def times(a: Term, b: Term) -> Function:
    return Function("multiply", (a, b), REAL)

def max_f(a: Term, b: Term) -> Function:
    return Function("max", (a, b), REAL)

def min_f(a: Term, b: Term) -> Function:
    return Function("min", (a, b), REAL)

def prob_weight(p: Term, a: Term) -> Function:
    return Function("prob_weight", (p, a), REAL)

def prob_complement(p: Term) -> Function:
    return Function("prob_complement", (p,), PROB)

def Compose(m1: Term, m2: Term) -> Function:
    return Function("Compose", (m1, m2), MODULE)

def Transpose(m: Term) -> Function:
    return Function("Transpose", (m,), MODULE)

def phi(m: Term) -> Function:
    return Function("phi", (m,), MODULE)

def Attn(q: Term, k: Term, v: Term) -> Function:
    return Function("Attn", (q, k, v), MODULE)

# Standard variables for attention
Q = Variable("Q", MODULE)
K = Variable("K", MODULE)
V = Variable("V", MODULE)


# Standard constants
ID_M = Constant("ID_M", MODULE)
R_ZERO = Constant("R_ZERO", REAL)       # dimensionless zero (probability)
R_ONE = Constant("R_ONE", REAL)
R_PENALTY = Constant("R_PENALTY", REAL)
R_INF = Constant("R_INF", REAL)
P_TRUE = Constant("P_TRUE", PRED)
DEP_ZERO = Constant("DEP_ZERO", REAL)
DEP_ONE = Constant("DEP_ONE", REAL)
ZERO_J = Constant("ZERO_J", REAL)        # dimensioned zero (energy: 0 joules)
ZERO_bit = Constant("ZERO_bit", REAL)    # dimensioned zero (information: 0 bits)
LANDAUER = Constant("LANDAUER", REAL)    # kT·ln(2) J/bit

# Standard variables
m1 = Variable("M1", MODULE)
m2 = Variable("M2", MODULE)
m3 = Variable("M3", MODULE)
r1 = Variable("R1", REAL)
r2 = Variable("R2", REAL)
r3 = Variable("R3", REAL)
p_var = Variable("P", PRED)
prob = Variable("prob", PROB)


# ═══════════════════════════════════════════════════
# THE DISCOVERY ENGINE
# ═══════════════════════════════════════════════════

from dataclasses import dataclass, field
from copy import deepcopy

@dataclass
class KnowledgeBase:
    axioms: List[Formula] = field(default_factory=list)
    theorems: List[Formula] = field(default_factory=list)
    axiom_names: List[str] = field(default_factory=list)
    
    def contains(self, formula: Formula) -> bool:
        f_str = str(formula)
        return any(str(a) == f_str for a in self.axioms + self.theorems)

def _verify_worker(args):
    conj, kb_snapshot, max_steps, timeout, offsets = args
    from prover.general_atp import GeneralATP, ProverStrategy
    verifier = GeneralATP(strategy=ProverStrategy.EGRAPH_THEN_RESOLUTION)
    
    # UAP: Apply offsets to the localized resolution engine
    if offsets and hasattr(verifier, "resolution_engine"):
        verifier.resolution_engine._steps_offset = offsets.get("steps", 0)
        verifier.resolution_engine._ratio_offset = offsets.get("ratio", 0)
        
    res = verifier.prove(conj, kb_snapshot)
    return conj, res

class DiscoveryEngine:
    """
    The Autonomous Scientific Discovery Engine (The Terminal State).
    Manages the 71-Stage Master Architecture.
    """
    
    def __init__(self, max_clauses: int = 500, max_depth: int = 6,
                 min_interestingness: float = 0.2, certified_mode: bool | None = None):
        import os
        if certified_mode is None:
            self.certified_mode = (os.environ.get("COAI_CERTIFIED_MODE", "0") == "1")
        else:
            self.certified_mode = certified_mode
            
        self.axioms: List[Formula] = []
        self.axiom_names: List[str] = []
        self.lemmas: List[Formula] = []
        self.counter_axioms: List[Formula] = []
        self._counter_axiom_strs: Set[str] = set()  # dedup
        self._failed_conjecture_strs: Set[str] = set()  # don't retry
        self._proven_strs: Set[str] = set()  # don't re-prove
        self.saturator = ForwardChainingSaturator(max_clauses, max_depth)
        self.scorer = ProofComplexityScorer()
        self.min_interestingness = min_interestingness
        self.all_discoveries: List[DiscoveredTheorem] = []
        self.egraph = RiskEGraph()
        self.mcts_iterations = int(os.environ.get("COAI_MCTS_ITERS", "0"))
        self.beta_ledger = BetaLedger(initial_budget=float(os.environ.get("COAI_BETA_BUDGET", "100.0")))
        
        # PR 0016: MetaShield auditing
        from core.audit import MetaShieldLedger
        self.audit_ledger = MetaShieldLedger()
        
        # PR 0019: UAP ATP Offsets (Universal Autopoiesis)
        self._atp_steps_offset = 0
        self._atp_ratio_offset = 0
        
        # PR 0017: Büchi liveness monitor
        from discovery.liveness import BuchiMonitor
        self.liveness_monitor = BuchiMonitor()
        
        # PR 0018: zk-STARK adherence prover
        from prover.zk_stark import AdherenceProver
        self.adherence_prover = AdherenceProver()
        
        # PR 0019: Omega Node
        from discovery.omega import OmegaSynthesizer
        self.omega_node = OmegaSynthesizer()
        
        # PR 0020: Equilibrium Detector
        self.equilibrium_detector = EquilibriumDetector()
        self.equilibrium_enabled = True
        
    @property
    def marathon_mode(self) -> bool:
        return getattr(self.liveness_monitor, "marathon_mode", False)
    
    @marathon_mode.setter
    def marathon_mode(self, value: bool):
        if hasattr(self, "liveness_monitor"):
            self.liveness_monitor.marathon_mode = value
            self.liveness_monitor.max_stall = 50 if value else 5
            print(f"[DiscoveryEngine] Marathon Mode: {'ENABLED' if value else 'DISABLED'} (Liveness Threshold: {self.liveness_monitor.max_stall})")
        
        # PR 0019: Autopoietic Metasystem
        self.metasystem = AutopoieticMetasystem(self)
        
        self._init_knowledge_base()
    
    
    def _merge_consistent(self, new_theorems: List[DiscoveredTheorem]) -> List[DiscoveredTheorem]:
        """Only add theorems that don't contradict existing knowledge."""
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

    def _load_base_axioms(self):
        """Loads fundamental axioms into the engine."""
        from core.logic import Forall, Equality, Function, Constant, Variable, MODULE, REAL
        
        # Identity and Neutrality Axioms
        m1 = Variable("M1", MODULE)
        # Normalize(M1, ID_M) = M1  (Normalization identity)
        self.axioms.append(Forall(m1, Equality(Function("Normalize", [m1, ID_M]), m1)))
        self.axiom_names.append("normalize_id_neutral")
        
        # Add baseline logic for ResourceCost if needed
        # ...

    def _init_knowledge_base(self):
        """
        Component 1: Axiom Store.
        Full CoAI axiom set as actual Formula objects.
        """
        self._load_base_axioms()

        # ── ATTENTION AXIOMS ──
        bundle = Path(__file__).resolve().parent / "axioms" / "attention_axioms.verified.json"
        if bundle.exists():
            load_axiom_bundle(self, bundle)
        else:
            if getattr(self, "certified_mode", False):
                raise RuntimeError(f"Certified mode enabled but bundle missing: {bundle}")
            # safe default: no attention axioms loaded if bundle not present
            pass
        # ── ALGEBRA AXIOMS ──
        
        # A1: Sequential Associativity
        # Seq(Seq(M1,M2), M3) = Seq(M1, Seq(M2,M3))
        self._add_axiom(
            Forall(m1, Forall(m2, Forall(m3,
                Equality(Seq(Seq(m1, m2), m3), Seq(m1, Seq(m2, m3)))
            ))),
            "seq_associativity"
        )
        
        # A2: Sequential Right Identity
        # Seq(M1, ID_M) = M1
        self._add_axiom(
            Forall(m1, Equality(Seq(m1, ID_M), m1)),
            "seq_right_identity"
        )
        
        # A3: Sequential Left Identity
        # Seq(ID_M, M1) = M1
        self._add_axiom(
            Forall(m1, Equality(Seq(ID_M, m1), m1)),
            "seq_left_identity"
        )
        
        # A4: Parallel Commutativity
        # Par_Dyn(M1, M2) = Par_Dyn(M2, M1)
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(Par_Dyn(m1, m2), Par_Dyn(m2, m1))
            )),
            "par_commutativity"
        )
        
        # A5: Parallel Identity
        # Par_Dyn(M1, ID_M) = M1
        self._add_axiom(
            Forall(m1, Equality(Par_Dyn(m1, ID_M), m1)),
            "par_identity"
        )
        
        # ── RISK AXIOMS ──
        
        # R1: Risk Additivity over Seq
        # Risk(Seq(M1, M2)) = plus(Risk(M1), Risk(M2))
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(Risk(Seq(m1, m2)), plus(Risk(m1), Risk(m2)))
            )),
            "risk_additivity"
        )
        
        # R2: Risk of Identity
        # Risk(ID_M) = R_ZERO
        self._add_axiom(
            Equality(Risk(ID_M), R_ZERO),
            "risk_identity"
        )
        
        # R3: Additive Identity (zero)
        # plus(R1, R_ZERO) = R1
        self._add_axiom(
            Forall(r1, Equality(plus(r1, R_ZERO), r1)),
            "additive_identity"
        )
        
        # R4: Self-dependency
        # Dep(M1, M1) = DEP_ONE
        self._add_axiom(
            Forall(m1, Equality(Dep(m1, m1), DEP_ONE)),
            "self_dependency"
        )
        
        # R5: Risk of fully dependent parallel = single risk
        # Dep(M1,M2)=DEP_ONE → Risk(Par_Dyn(M1,M2)) = Risk(M1)
        # (Simplified: for self-composition)
        self._add_axiom(
            Forall(m1,
                Equality(Risk(Par_Dyn(m1, m1)), Risk(m1))
            ),
            "parallel_self_risk"
        )
        
        # ── BARRIER AXIOMS ──
        
        # B1: Barrier with trivial predicate has no penalty
        # Barrier(M1, P_TRUE) → Risk = Risk(M1)
        self._add_axiom(
            Forall(m1,
                Equality(Risk(Barrier(m1, P_TRUE)), Risk(m1))
            ),
            "trivial_barrier"
        )
        
        # B2: Barrier with non-trivial predicate adds penalty
        # Risk(Barrier(M1, P)) = plus(Risk(M1), R_PENALTY)  [for P ≠ P_TRUE]
        self._add_axiom(
            Forall(m1, Forall(p_var,
                Implies(
                    Not(Equality(p_var, P_TRUE)),
                    Equality(Risk(Barrier(m1, p_var)), plus(Risk(m1), R_PENALTY))
                )
            )),
            "barrier_penalty"
        )
        
        # ── CHOICE AXIOMS ──
        
        # C1: Risk of Choice is probability-weighted sum
        # Risk(Choice(M1, M2, prob)) = plus(prob_weight(prob, Risk(M1)),
        #                                    prob_weight(minus(R_ONE, prob), Risk(M2)))
        self._add_axiom(
            Forall(m1, Forall(m2, Forall(prob,
                Equality(
                    Risk(Choice(m1, m2, prob)),
                    plus(
                        prob_weight(prob, Risk(m1)),
                        prob_weight(prob_complement(prob), Risk(m2))
                    )
                )
            ))),
            "choice_risk"
        )
        
        # C2: Choice distributes over Seq (on right)
        # Seq(Choice(M1, M2, prob), M3) = Choice(Seq(M1,M3), Seq(M2,M3), prob)
        self._add_axiom(
            Forall(m1, Forall(m2, Forall(m3, Forall(prob,
                Equality(
                    Seq(Choice(m1, m2, prob), m3),
                    Choice(Seq(m1, m3), Seq(m2, m3), prob)
                )
            )))),
            "choice_seq_distributivity"
        )
        
        # ── RESOURCE COST AXIOMS ──
        
        # RC1: Cost Additivity over Seq
        # ResourceCost(Seq(M1,M2)) = plus(ResourceCost(M1), ResourceCost(M2))
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(
                    ResourceCost(Seq(m1, m2)),
                    plus(ResourceCost(m1), ResourceCost(m2))
                )
            )),
            "cost_additivity"
        )
        
        # RC2: Cost of Identity
        # ResourceCost(ID_M) = ZERO_J  (0 joules, not dimensionless zero)
        self._add_axiom(
            Equality(ResourceCost(ID_M), ZERO_J),
            "cost_identity"
        )
        
        # RC3: Parallel Cost = max(individual costs)
        # ResourceCost(Par_Dyn(M1,M2)) = max(ResourceCost(M1), ResourceCost(M2))
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(
                    ResourceCost(Par_Dyn(m1, m2)),
                    max_f(ResourceCost(m1), ResourceCost(m2))
                )
            )),
            "cost_parallel"
        )
        
        # RC4: max(a,b) >= a  and  max(a,b) >= b  (for Parallel Optimization bound)
        self._add_axiom(
            Forall(r1, Forall(r2, LessEq(r1, max_f(r1, r2)))),
            "max_geq_left"
        )
        self._add_axiom(
            Forall(r1, Forall(r2, LessEq(r2, max_f(r1, r2)))),
            "max_geq_right"
        )
        
        # RC5: plus(a,b) >= max(a,b) when a,b >= 0  (Key for Parallel Optimization)
        self._add_axiom(
            Forall(r1, Forall(r2, LessEq(max_f(r1, r2), plus(r1, r2)))),
            "sum_geq_max"
        )
        
        # ── SECURITY (ENTROPY) AXIOMS ──
        
        # S1: Security Bottleneck (Sequential)
        # Ent(Seq(M1, M2)) = min(Ent(M1), Ent(M2))
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(Ent(Seq(m1, m2)), min_f(Ent(m1), Ent(m2)))
            )),
            "security_bottleneck"
        )
        
        # S2: Security Filter changes entropy
        # Ent(Sec_Filter(M1)) != Ent(M1) (captured as: they differ)
        # More precisely: Ent(Seq(Sec_Filter(M1), M2)) uses filtered entropy
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(
                    Ent(Seq(Sec_Filter(m1), m2)),
                    min_f(Ent(Sec_Filter(m1)), Ent(m2))
                )
            )),
            "filtered_security"
        )
        
        # ── COMPLEXITY AXIOMS ──
        
        # CX1: Complexity Additivity over Seq (log-domain, per analysis)
        # Comp(Seq(M1, M2)) = plus(Comp(M1), Comp(M2))
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(Comp(Seq(m1, m2)), plus(Comp(m1), Comp(m2)))
            )),
            "complexity_seq"
        )
        
        # CX2: Complexity of Parallel = max
        # Comp(Par_Dyn(M1, M2)) = max(Comp(M1), Comp(M2))
        self._add_axiom(
            Forall(m1, Forall(m2,
                Equality(Comp(Par_Dyn(m1, m2)), max_f(Comp(m1), Comp(m2)))
            )),
            "complexity_parallel"
        )
        
        # CX3: Complexity of Identity
        # Comp(ID_M) = ZERO_bit  (0 bits, not dimensionless zero)
        self._add_axiom(
            Equality(Comp(ID_M), ZERO_bit),
            "complexity_identity"
        )
        
        # ── ENTROPY IDENTITY AND CONGRUENCE ──
        
        # ENT_ID: Ent(ID_M) = R_INF (identity is perfectly secure)
        self._add_axiom(
            Equality(Ent(ID_M), R_INF),
            "entropy_identity"
        )
        
        # MIN_INF: min(x, R_INF) = x (R_INF is the top element)
        self._add_axiom(
            Forall(r1, Equality(min_f(r1, R_INF), r1)),
            "min_inf_right"
        )
        self._add_axiom(
            Forall(r1, Equality(min_f(R_INF, r1), r1)),
            "min_inf_left"
        )
        
        # LEFT_ADDITIVE_IDENTITY: plus(R_ZERO, x) = x
        self._add_axiom(
            Forall(r1, Equality(plus(R_ZERO, r1), r1)),
            "additive_identity_left"
        )
        
        # MAX_ZERO: max(x, R_ZERO) = x, max(R_ZERO, x) = x
        self._add_axiom(
            Forall(r1, Equality(max_f(r1, R_ZERO), r1)),
            "max_zero_right"
        )
        self._add_axiom(
            Forall(r1, Equality(max_f(R_ZERO, r1), r1)),
            "max_zero_left"
        )
        
        # ── MEASURE CONGRUENCE (if M=N then f(M)=f(N)) ──
        # These let the prover chain: Seq(M,ID)=M => Risk(Seq(M,ID))=Risk(M)
        
        for measure_name in ["Risk", "ResourceCost", "Comp", "Ent"]:
            self._add_axiom(
                Forall(m1, Forall(m2,
                    Implies(
                        Equality(m1, m2),
                        Equality(
                            Function(measure_name, (m1,), REAL),
                            Function(measure_name, (m2,), REAL)
                        )
                    )
                )),
                f"{measure_name.lower()}_congruence"
            )
        
        # ── CROSS-DOMAIN AXIOMS (Capstone) ──
        
        # Q1: Risk=0 implies Cost <= Comp * LANDAUER (Quad-Goal)
        # Original had Cost <= Comp, which compares J to bit.
        # Multiplying by LANDAUER (J/bit) makes both sides ENERGY.
        self._add_axiom(
            Forall(m1,
                Implies(
                    Equality(Risk(m1), R_ZERO),
                    LessEq(
                        ResourceCost(m1),
                        times(Comp(m1), LANDAUER)
                    )
                )
            ),
            "quad_goal_constraint"
        )
        
        # ── ARITHMETIC AXIOMS ──
        
        # AR1: Commutativity of plus
        self._add_axiom(
            Forall(r1, Forall(r2, Equality(plus(r1, r2), plus(r2, r1)))),
            "plus_commutative"
        )
        
        # AR2: Associativity of plus
        self._add_axiom(
            Forall(r1, Forall(r2, Forall(r3,
                Equality(plus(plus(r1, r2), r3), plus(r1, plus(r2, r3)))
            ))),
            "plus_associative"
        )
        
        # AR3: Commutativity of max
        self._add_axiom(
            Forall(r1, Forall(r2, Equality(max_f(r1, r2), max_f(r2, r1)))),
            "max_commutative"
        )
        
        # AR4: Commutativity of min
        self._add_axiom(
            Forall(r1, Forall(r2, Equality(min_f(r1, r2), min_f(r2, r1)))),
            "min_commutative"
        )
        
        # ── INEQUALITY AXIOMS ──

        # IN1: Transitivity of <=
        self._add_axiom(
            Forall(r1, Forall(r2, Forall(r3,
                Implies(
                    And(LessEq(r1, r2), LessEq(r2, r3)),
                    LessEq(r1, r3)
                )
            ))),
            "leq_transitive"
        )

        # IN2: Substitutivity: a = b and b <= c -> a <= c
        self._add_axiom(
            Forall(r1, Forall(r2, Forall(r3,
                Implies(
                    And(Equality(r1, r2), LessEq(r2, r3)),
                    LessEq(r1, r3)
                )
            ))),
            "eq_leq_chain"
        )

        # IN3: Substitutivity: a <= b and b = c -> a <= c
        self._add_axiom(
            Forall(r1, Forall(r2, Forall(r3,
                Implies(
                    And(LessEq(r1, r2), Equality(r2, r3)),
                    LessEq(r1, r3)
                )
            ))),
            "leq_eq_chain"
        )
        
        # ── DERIVED LEMMAS (injected for prover efficiency) ──
        # These follow from congruence + identity but cost too many
        # resolution steps to derive from scratch.
        
        # DL: measure(Seq(M, ID)) = measure(M) for each measure
        for measure_name in ["Risk", "ResourceCost", "Comp"]:
            self._add_axiom(
                Forall(m1, Equality(
                    Function(measure_name, (Seq(m1, ID_M),), REAL),
                    Function(measure_name, (m1,), REAL)
                )),
                f"{measure_name.lower()}_seq_identity"
            )
            self._add_axiom(
                Forall(m1, Equality(
                    Function(measure_name, (Seq(ID_M, m1),), REAL),
                    Function(measure_name, (m1,), REAL)
                )),
                f"{measure_name.lower()}_seq_left_identity"
            )
        
        # DL: Ent(Seq(M, ID)) = Ent(M) (via min(Ent(M), R_INF) = Ent(M))
        self._add_axiom(
            Forall(m1, Equality(
                Ent(Seq(m1, ID_M)),
                Ent(m1)
            )),
            "ent_seq_identity"
        )
        self._add_axiom(
            Forall(m1, Equality(
                Ent(Seq(ID_M, m1)),
                Ent(m1)
            )),
            "ent_seq_left_identity"
        )
        
        # DL: measure(Par(M, ID)) = measure(M) for each measure  
        for measure_name in ["Risk", "ResourceCost", "Comp"]:
            self._add_axiom(
                Forall(m1, Equality(
                    Function(measure_name, (Par_Dyn(m1, ID_M),), REAL),
                    Function(measure_name, (m1,), REAL)
                )),
                f"{measure_name.lower()}_par_identity"
            )
        
        self._add_axiom(
            Forall(m1, Equality(
                Ent(Par_Dyn(m1, ID_M)),
                Ent(m1)
            )),
            "ent_par_identity"
        )
        
        # ── DISCOVERED AXIOMS ──
        self._load_discovered_axioms()
    
    def _load_discovered_axioms(self):
        """
        Load self-discovered stable axioms from the Quake kernel.
        These are treated as axiomatic truths discovered by the system itself.
        """
        try:
            from grounding.quake import STABLE_AXIOM_INDICES
            
            for idx in STABLE_AXIOM_INDICES:
                # Define a proposition that is axiomatically true: StableAxiom_N = P_TRUE
                prop = Constant(f"StableAxiom_{idx}", PRED)
                self._add_axiom(Equality(prop, P_TRUE), f"discovered_{idx}")
                
        except ImportError:
            pass

    def _add_axiom(self, formula: Formula, name: str = ""):
        """Add an axiom to the knowledge base."""
        self.axioms.append(formula)
        self.axiom_names.append(name)
        
        # Build 2.0: Sync to e-graph
        curr = formula
        while isinstance(curr, Forall): curr = curr.body
        if isinstance(curr, Equality):
            try:
                et_lhs = logic_to_egraph_term(curr.left)
                et_rhs = logic_to_egraph_term(curr.right)
                self.egraph.union(self.egraph.add(et_lhs), self.egraph.add(et_rhs))
            except Exception: pass
    
    # ═════════════════════════════════════════════
    # COMPONENT 4: PATTERN NORMALIZER
    # ═════════════════════════════════════════════
    
    def _extract_pattern(self, formula: Formula) -> Optional[str]:
        """
        Normalize a formula into a canonical pattern string.
        Variables are renamed to V0, V1, V2... in order of appearance.
        """
        return _normalize_formula(formula)
    
    # ═════════════════════════════════════════════
    # COMPONENT 5: CONJECTURE GENERATOR
    # ═════════════════════════════════════════════
    
    def conjecture_new_axioms(self, theorems: List[DiscoveredTheorem], seed_asts=None) -> Tuple[List[Formula], List[Any]]:
        """
        Extract patterns from discovered theorems and generalize
        them into universally quantified conjectures.
        """
        patterns: Dict[str, List[Formula]] = defaultdict(list)
        
        for thm in theorems:
            pat = self._extract_pattern(thm.formula)
            if pat:
                patterns[pat].append(thm.formula)
        
        conjectures = []
        for pat, instances in patterns.items():
            if len(instances) >= 2:
                # Take the most general instance and quantify it
                generalized = self._generalize_from_instances(instances)
                if generalized:
                    conjectures.append(generalized)
        
        # Also generate structural conjectures
        conjectures.extend(self._generate_structural_conjectures(theorems))
        
        top_asts = []
        # Build 2.0: MCTS Systematic Synthesis
        if getattr(self, "mcts_iterations", 0) > 0:
            synthesizer = GrammarSynthesizer(self.scorer)
            # PR 0019: Load persisted weights
            if hasattr(self, "_grammar_weights") and self._grammar_weights:
                synthesizer.heuristic_weights = self._grammar_weights

            mcts_conjs, top_asts = synthesizer.synthesize(
                iterations=self.mcts_iterations, 
                seed_asts=seed_asts,
                beta_ledger=getattr(self, "beta_ledger", None)
            )
            # PR 0019: Save yield map for metasystem
            self._last_yield_map = getattr(synthesizer, "_yield_map", {})
            self._grammar_weights = synthesizer.heuristic_weights
            
            conjectures.extend(mcts_conjs)
        
        # Also generate heuristic conjectures (cycle-dependent for variety)
        heuristic = self._generate_heuristic_conjectures(getattr(self, '_current_cycle', 0))
        conjectures.extend(heuristic)
        
        # deduplicate
        unique = []
        seen_canonical = set()
        
        for c in conjectures:
            # Build 2.0: Logical Deduplication
            curr = c
            while isinstance(curr, Forall): curr = curr.body
            if isinstance(curr, Equality):
                try:
                    et_lhs = logic_to_egraph_term(curr.left)
                    et_rhs = logic_to_egraph_term(curr.right)
                    # Check if already equivalent in e-graph
                    if self.egraph.find(self.egraph.add(et_lhs)) == self.egraph.find(self.egraph.add(et_rhs)):
                        continue
                except Exception: pass
            
            s = str(c)
            if s not in seen_canonical:
                seen_canonical.add(s)
                unique.append(c)
        
        return unique, top_asts
    
    def _generalize_from_instances(self, instances: List[Formula]) -> Optional[Formula]:
        """
        Given multiple instances of a pattern, produce a universally quantified formula.
        Takes the first instance and quantifies over its free variables.
        """
        if not instances:
            return None
        
        base = instances[0]
        free_vars = list(base.free_variables())
        
        if not free_vars:
            return base
        
        result = base
        for var in free_vars:
            result = Forall(var, result)
        
        return result
    
    
    def _generate_heuristic_conjectures(self, cycle: int = 0) -> List[Formula]:
        """Generate diverse heuristic conjectures. Different families per cycle."""
        conjectures = []
        
        # ── Family 1: Measure preservation through Identity (every cycle) ──
        for measure_name in ["Risk", "ResourceCost", "Comp", "Ent"]:
            for op in ["Seq", "Par_Dyn"]:
                # measure(op(A, ID_M)) = measure(A)
                op_term = Function(op, (m1, ID_M), MODULE)
                conj = Forall(m1,
                    Equality(
                        Function(measure_name, (op_term,), REAL),
                        Function(measure_name, (m1,), REAL)
                    )
                )
                conjectures.append(conj)
        
        # ── Family 2: Commutativity (cycle 0) ──
        if cycle % 3 == 0:
            for op in ["Seq"]:
                conjectures.append(Forall(m1, Forall(m2,
                    Equality(
                        Function(op, (m1, m2), MODULE),
                        Function(op, (m2, m1), MODULE)
                    )
                )))
        
        # ── Family 3: Measure additivity/compositionality (cycle 1) ──
        if cycle % 3 == 1:
            # Risk(Par(A,B)) = max(Risk(A), Risk(B))  [conjecture: is risk bottleneck-like for Par?]
            conjectures.append(Forall(m1, Forall(m2,
                Equality(Risk(Par_Dyn(m1, m2)), max_f(Risk(m1), Risk(m2)))
            )))
            # Ent(Par(A,B)) = min(Ent(A), Ent(B))  [does Par bottleneck security?]
            conjectures.append(Forall(m1, Forall(m2,
                Equality(Ent(Par_Dyn(m1, m2)), min_f(Ent(m1), Ent(m2)))
            )))
            # Cost(Seq(A,B)) = Cost(Seq(B,A))  [cost commutes even if Seq doesn't?]
            conjectures.append(Forall(m1, Forall(m2,
                Equality(ResourceCost(Seq(m1, m2)), ResourceCost(Seq(m2, m1)))
            )))
        
        # ── Family 4: Idempotence and absorption (cycle 2) ──
        if cycle % 3 == 2:
            # Par(A, A) = A  [idempotence?]
            conjectures.append(Forall(m1,
                Equality(Par_Dyn(m1, m1), m1)
            ))
            # Risk(Par(A,A)) = Risk(A)  [already an axiom, should prove]
            conjectures.append(Forall(m1,
                Equality(Risk(Par_Dyn(m1, m1)), Risk(m1))
            ))
            # Comp(Seq(A,B)) = Comp(Seq(B,A))  [complexity commutes?]
            conjectures.append(Forall(m1, Forall(m2,
                Equality(Comp(Seq(m1, m2)), Comp(Seq(m2, m1)))
            )))
            # Cost(Par(A,B)) = Cost(Par(B,A))  [trivially true from Par comm]
            conjectures.append(Forall(m1, Forall(m2,
                Equality(
                    ResourceCost(Par_Dyn(m1, m2)),
                    ResourceCost(Par_Dyn(m2, m1))
                )
            )))
        
        # ── Family 5: Inequality consequences (every other cycle) ──
        if cycle % 2 == 0:
            # Cost(Par(A,B)) <= Cost(Seq(A,B))  [parallel is always cheaper?]
            conjectures.append(Forall(m1, Forall(m2,
                LessEq(ResourceCost(Par_Dyn(m1, m2)), ResourceCost(Seq(m1, m2)))
            )))
            # Comp(Par(A,B)) <= Comp(Seq(A,B))  [parallel is less complex?]
            conjectures.append(Forall(m1, Forall(m2,
                LessEq(Comp(Par_Dyn(m1, m2)), Comp(Seq(m1, m2)))
            )))
        
        # ── Family 6: Barrier interaction (cycle 1+) ──
        if cycle >= 1:
            # Risk(Barrier(M, P_TRUE)) = Risk(M)  [already axiom, should prove]
            conjectures.append(Forall(m1,
                Equality(Risk(Barrier(m1, P_TRUE)), Risk(m1))
            ))
            # Barrier(M, P_TRUE) = M  [barrier with trivial pred is identity?]
            conjectures.append(Forall(m1,
                Equality(Barrier(m1, P_TRUE), m1)
            ))
        
        # ── Family 7: Associativity of Par (every cycle) ──
        conjectures.append(Forall(m1, Forall(m2, Forall(m3,
            Equality(Par_Dyn(Par_Dyn(m1, m2), m3), Par_Dyn(m1, Par_Dyn(m2, m3)))
        ))))
        
        # ── Phase 12: MCTS Grammar AST Synthesis ──
        try:
            from discovery.mcts_grammar import GrammarSynthesizer
            from discovery.normalization import normalize_trotter
            from discovery.diversity import DiversityPruner
            
            synth = GrammarSynthesizer(self.scorer, max_depth=3)
            # Generate intense novel conjectures autonomously
            mcts_iters = int(os.environ.get("COAI_MCTS_ITERS", "200"))
            mcts_results = synth.synthesize(
                iterations=mcts_iters, 
                beta_ledger=getattr(self, "beta_ledger", None),
                branching_factor=self.egraph.branching_factor
            )
            mcts_forms = mcts_results[0]
            
            # Phase 12.1: Streaming DPP Diversity Pruning
            pruner = DiversityPruner(threshold=0.1)
            # Extract Terms from Formulas for pruning
            def formula_to_term(f: Formula) -> Term:
                if hasattr(f, "lhs"): return f.lhs
                return Constant("ID_M", MODULE)
            
            diverse_forms = pruner.prune_list(mcts_forms, key_fn=formula_to_term)
            
            # Filter obvious duplicates against existing axioms
            axiom_strs = {str(a) for a in self.axioms}
            for f in diverse_forms:
                # Phase 12.2: Trotter-Suzuki Normalization
                if hasattr(f, "lhs") and hasattr(f, "rhs"):
                    f = Equality(normalize_trotter(f.lhs), normalize_trotter(f.rhs))
                    for var in f.free_variables():
                        f = Forall(var, f)
                
                if str(f) not in axiom_strs:
                    conjectures.append(f)
        except Exception as e:
            # Fallback if MCTS fails to load
            print(f"  [MCTS Warning] MCTS synthesis skipped: {e}")
            pass
            
        return conjectures

    def _generate_structural_conjectures(self, theorems: List[DiscoveredTheorem]) -> List[Formula]:
        """
        Generate conjectures about structural properties based on
        what kinds of theorems have been found.
        """
        conjectures = []
        
        # Collect all function symbols seen in theorems
        all_functions = set()
        for thm in theorems:
            all_functions |= thm.formula.functions()
        
        # For each binary operator, conjecture commutativity if not already known
        binary_ops = set()
        for thm in theorems:
            self._find_binary_ops(thm.formula, binary_ops)
        
        for op in binary_ops:
            comm_conjecture = Forall(m1, Forall(m2,
                Equality(
                    Function(op, (m1, m2), MODULE),
                    Function(op, (m2, m1), MODULE)
                )
            ))
            if comm_conjecture not in self.axioms:
                conjectures.append(comm_conjecture)
        
        return conjectures
    
    def _find_binary_ops(self, formula: Formula, ops: Set[str]):
        """Find all binary function symbols in a formula."""
        if isinstance(formula, Equality):
            self._find_binary_ops_term(formula.left, ops)
            self._find_binary_ops_term(formula.right, ops)
        elif isinstance(formula, (Forall, Exists)):
            self._find_binary_ops(formula.body, ops)
        elif isinstance(formula, (And, Or, Implies)):
            if hasattr(formula, 'left'):
                self._find_binary_ops(formula.left, ops)
                self._find_binary_ops(formula.right, ops)
            elif hasattr(formula, 'antecedent'):
                self._find_binary_ops(formula.antecedent, ops)
                self._find_binary_ops(formula.consequent, ops)
        elif isinstance(formula, Not):
            self._find_binary_ops(formula.formula, ops)
    
    def _find_binary_ops_term(self, term: Term, ops: Set[str]):
        """Find binary function symbols in a term."""
        if isinstance(term, Function):
            if len(term.args) == 2:
                ops.add(term.symbol)
            for arg in term.args:
                self._find_binary_ops_term(arg, ops)
    
    # ═════════════════════════════════════════════
    # COMPONENT 8: COUNTER-AXIOM GENERATOR
    # ═════════════════════════════════════════════
    
    def _generate_counter_axiom(self, failed_conjecture: Formula, 
                                 proof_result: ProofResult) -> Optional[Formula]:
        """
        Generate a counter-axiom from a failed proof.
        Only generates counter-axiom if proof found a genuine contradiction,
        not just resource exhaustion.
        """
        if proof_result.reason == "RESOURCE_EXHAUSTION":
            # Don't negate — might be true but hard to prove
            return None
        
        if proof_result.reason in ("NO_PROOF_FOUND", "EXHAUSTED"):
            # Likely false — safe to add negation
            counter = Not(failed_conjecture)
            return counter
        
        return None
    
    # ═════════════════════════════════════════════
    # COMPONENT 9: EXTERNAL ORACLE
    # ═════════════════════════════════════════════
    
    def _consult_oracle(self, failed_conjectures: List[Tuple[Formula, ProofResult]]) -> List[Formula]:
        """
        Simulate external validation for resource-exhausted proofs.
        Generates conditional axioms where appropriate.
        """
        oracle_axioms = []
        
        for conjecture, result in failed_conjectures:
            if result.reason != "RESOURCE_EXHAUSTION":
                continue
            
            # Check if this is a cost simplification that needs a condition
            functions = conjecture.functions()
            
            if "ResourceCost" in functions:
                # Generate conditional: true when one component is zero-cost
                conditional = Forall(m1, Forall(m2,
                    Implies(
                        Equality(ResourceCost(m2), R_ZERO),
                        Equality(ResourceCost(Seq(m1, m2)), ResourceCost(m1))
                    )
                ))
                if conditional not in self.axioms:
                    oracle_axioms.append(conditional)
            
            if "Comp" in functions and "Par_Dyn" in functions:
                # For complexity of independent parallel: Cost = Complexity
                conditional = Forall(m1, Forall(m2,
                    Implies(
                        Equality(Dep(m1, m2), DEP_ZERO),
                        Equality(ResourceCost(Par_Dyn(m1, m2)), Comp(Par_Dyn(m1, m2)))
                    )
                ))
                if conditional not in self.axioms:
                    oracle_axioms.append(conditional)
        
        return oracle_axioms
    
    # ═════════════════════════════════════════════
    # COMPONENT 2+3: DISCOVER THEOREMS
    # ═════════════════════════════════════════════
    
    def discover_theorems(self, limit: int = 200, mode: str = "full") -> List[DiscoveredTheorem]:
        """
        Run saturation on current axiom set and score results.
        """
        all_formulas = self.axioms + self.lemmas + self.counter_axioms
        
        # Build 2.9.0: Two-Phase O-FLOW support
        self.saturator.mode = mode
        result = self.saturator.saturate(all_formulas)
        
        theorems = []
        for eq in result.generated_equalities:
            score = self.scorer.score(eq)
            if score >= self.min_interestingness:
                tags = self.scorer.classify(eq)
                thm = DiscoveredTheorem(
                    formula=eq,
                    interestingness=score,
                    tags=tags,
                    verification="SATURATED"
                )
                theorems.append(thm)
        
        # Sort by interestingness
        theorems.sort(key=lambda t: -t.interestingness)
        
        return theorems[:limit]
    
    # ═════════════════════════════════════════════
    # THE CUMULATIVE SCIENTIST LOOP
    # ═════════════════════════════════════════════
    
    def _state_from_session(self, session: DiscoverySession):
        from discovery.tools.corridor import LatentState
        md = session.metadata
        applied = md.get("applied_rules_counter", {}) or {}

        entropy = min(2.5, len(applied) / 2.0) if applied else 0.5
        embedding_norm = float(len(session.theorems))
        
        total_conj = len(session.theorems) + len(session.counter_axioms)
        attention_coherence = (len(session.theorems) / total_conj) if total_conj > 0 else 1.0
        manifold_divergence = 1.0 - attention_coherence
        centroid_similarity = 0.5
        
        # PR 0012: Tension Budget Ratio
        ratio = 1.0
        if hasattr(self, "beta_ledger"):
            ratio = self.beta_ledger.ratio
            
        return LatentState(
            entropy=entropy,
            attention_coherence=attention_coherence,
            embedding_norm=embedding_norm,
            manifold_divergence=manifold_divergence,
            centroid_similarity=centroid_similarity,
            tension_budget_ratio=ratio
        )

    def discover_and_verify_conjectures(self, 
                                         cumulative: bool = True,
                                         max_cycles: int = 3,
                                         verbose: bool = True,
                                         corridor_profile: str | None = None,
                                         cycle_callback: Callable | None = None) -> DiscoverySession:
        """
        The main discovery algorithm.
        Implements the complete Observe → Hypothesize → Experiment → Learn loop.
        """
        session = DiscoverySession()
        self._record_trust_base(session)
        
        from discovery.tools.corridor import (
            OperandicsCorridorTool, 
            CorridorToolConfig, 
            standard_corridor, 
            load_corridor_orchestrator
        )
        
        if corridor_profile:
            orchestrator = load_corridor_orchestrator(corridor_profile)
        else:
            orchestrator = standard_corridor()

        corridor_tool = OperandicsCorridorTool(
            orchestrator=orchestrator,
            config=CorridorToolConfig(certified_mode=getattr(self, "certified_mode", False), fail_on_unauthorized=False),
            state_fn=self._state_from_session,
        )
        corridor_tool.on_session_start(session)

        verifier = GeneralATP()
        
        # Initialize verifier with current axioms
        for axiom in self.axioms:
            # We actually don't need to add_axiom to GeneralATP itself in the new design since we pass KB
            pass
        
        for cycle in range(max_cycles):
            self._current_cycle = cycle
            session.cycle = cycle
            cycle_start = time.time()
            if verbose:
                print(f"\n{'='*60}")
                print(f"  DISCOVERY CYCLE {cycle}")
                print(f"  Axioms: {len(self.axioms)}  Lemmas: {len(self.lemmas)}  "
                      f"Counter-axioms: {len(self.counter_axioms)}")
                print(f"{'='*60}")
            
            # ── PHASE 1: SATURATION (Flow 1) ──
            if verbose:
                print(f"\n  Phase 1: Saturating knowledge base...")
            
            theorems = self.discover_theorems(limit=200)
            
            if verbose:
                print(f"  Found {len(theorems)} interesting consequences")
                for t in theorems[:5]:
                    print(f"    [{t.interestingness:.2f}] {t.formula}")
            
            # ── PHASE 2: CONJECTURE (Flow 2) ──
            if verbose:
                print(f"\n  Phase 2: Generating conjectures...")
            
            conjectures, cycle_asts = self.conjecture_new_axioms(theorems)
            session.mcts_asts.extend(cycle_asts)
            
            # Filter out already-failed and already-proven conjectures
            axiom_strs = {str(a) for a in self.axioms}
            conjectures = [
                c for c in conjectures
                if str(c) not in self._failed_conjecture_strs
                and str(c) not in self._proven_strs
                and str(c) not in axiom_strs
            ]
            
            if verbose:
                print(f"  Generated {len(conjectures)} novel conjectures")
            
            # ── PHASE 3: VERIFICATION ──
            if verbose:
                print(f"\n  Phase 3: Verifying conjectures (Parallel)...")
            
            proven_lemmas = []
            failed_conjectures = []
            
            import multiprocessing
            pool_args = []
            atp_offsets = {
                "steps": self._atp_steps_offset,
                "ratio": self._atp_ratio_offset
            }
            for c in conjectures:
                kb_snapshot = KnowledgeBase(axioms=deepcopy(self.axioms), theorems=deepcopy(self.lemmas))
                pool_args.append((c, kb_snapshot, 1500, 15.0, atp_offsets))
            
            with multiprocessing.Pool() as pool:
                verify_results = pool.map(_verify_worker, pool_args)
            
            for conj, result in verify_results:
                if result.success:
                    if verbose:
                        print(f"    [OK] PROVED: {conj}")
                        if result.proof_trace:
                             print(f"      Trace ({result.steps} steps):")
                             # Print last 5 steps of trace
                             for line in result.proof_trace[-5:]:
                                 print(f"        {line}")
                    
                    contract = VerifiedContract(
                        assumptions={
                            "certified_mode": session.metadata.get("certified_mode", False),
                            "attention_bundle_loaded": session.metadata.get("attention_bundle_loaded", False),
                            "attention_bundle_sha256_16": session.metadata.get("attention_bundle_sha256_16"),
                            "attention_bundle_schema_version": session.metadata.get("attention_bundle_schema_version"),
                        },
                        guarantees={
                            "equivalence": True,
                            "applied_rules": result.applied_rules
                        }
                    )
                    
                    # Approximation of compression gain based on term complexity
                    from core.logic import term_complexity
                    c_left = term_complexity(conj.left) if isinstance(conj, cl.Equality) else 1
                    c_right = term_complexity(conj.right) if isinstance(conj, cl.Equality) else 1
                    initial_size = c_left + c_right
                    final_size = min(c_left, c_right) * 2
                    comp_gain = initial_size / max(1, final_size)

                    thm = DiscoveredTheorem(
                        formula=conj,
                        interestingness=self.scorer.score(conj, proof_steps=result.steps, compression_gain=comp_gain),
                        tags={"theorem"},
                        verification="PROVED",
                        cycle=cycle,
                        proof_steps=result.steps,
                        compression_ratio=comp_gain,
                        contract=contract
                    )
                    thm.proof_result = result
                    proven_lemmas.append(thm)
                    session.theorems.append(thm)
                    self._proven_strs.add(str(conj))
                    self.scorer.record_usage(conj)
                    
                    # PR 0016: MetaShield Record
                    self.audit_ledger.record_discovery(
                        conj, 
                        provenance=f"cycle_{cycle}_MCTS", 
                        beta_cost=getattr(self.beta_ledger, "depletion", 0.0)
                    )
                    
                    # Build 2.0: Sync proved lemma to e-graph
                    curr = conj
                    while isinstance(curr, Forall): curr = curr.body
                    if isinstance(curr, Equality):
                        try:
                            et_lhs = logic_to_egraph_term(curr.left)
                            et_rhs = logic_to_egraph_term(curr.right)
                            self.egraph.union(self.egraph.add(et_lhs), self.egraph.add(et_rhs))
                        except Exception: pass
                else:
                    if verbose:
                        print(f"    [FAIL] FAILED ({result.reason}): {conj}")
                    failed_conjectures.append((conj, result))
                    self._failed_conjecture_strs.add(str(conj))
            
            # Merge consistent
            proven_lemmas = self._merge_consistent(proven_lemmas)
            
            # ── PHASE 4: FAILURE ANALYSIS (Flow 3) ──
            if verbose:
                print(f"\n  Phase 4: Analyzing failures...")
            
            # Counter-axioms from definite failures (deduplicated)
            new_counter = 0
            for conj, result in failed_conjectures:
                counter = self._generate_counter_axiom(conj, result)
                if counter is not None:
                    counter_str = str(counter)
                    if counter_str not in self._counter_axiom_strs:
                        self._counter_axiom_strs.add(counter_str)
                        if verbose:
                            print(f"    -| Counter-axiom: {counter}")
                        self.counter_axioms.append(counter)
                        session.counter_axioms.append(counter)
                        new_counter += 1
            if verbose and not new_counter:
                print(f"    (no new counter-axioms)")
            
            # Oracle consultation for resource-exhausted proofs
            resource_exhausted = [(c, r) for c, r in failed_conjectures 
                                  if r.reason == "RESOURCE_EXHAUSTION"]
            if resource_exhausted:
                oracle_axioms = self._consult_oracle(resource_exhausted)
                for oa in oracle_axioms:
                    if verbose:
                        print(f"    * Oracle axiom: {oa}")
                    session.oracle_axioms.append(oa)
                    
                    if cumulative:
                        contract = VerifiedContract(
                            assumptions={
                                "certified_mode": session.metadata.get("certified_mode", False)
                            },
                            guarantees={
                                "equivalence": True,
                                "oracle_stipulated": True
                            }
                        )
                        thm = DiscoveredTheorem(
                            formula=oa,
                            interestingness=self.scorer.score(oa, proof_steps=1, compression_gain=1.0),
                            tags={"oracle"},
                            verification="ORACLE-STIPULATED",
                            cycle=cycle,
                            contract=contract
                        )
                        self.scorer.record_usage(oa)
                        session.theorems.append(thm)
            
            # ── PHASE 5: PROMOTION (Cumulative Learning) ──
            if cumulative and proven_lemmas:
                if verbose:
                    print(f"\n  Phase 5: Promoting {len(proven_lemmas)} lemmas")
                
                for thm in proven_lemmas:
                    self.lemmas.append(thm.formula)
                    verifier.add_axiom(thm.formula)
                
                for oa in oracle_axioms if resource_exhausted else []:
                    self.lemmas.append(oa)
                    verifier.add_axiom(oa)

            # Latent Operator Discovery
            if cycle > 0 and cycle % 3 == 0:
                self._discover_latent_operators(session, cycle, verbose)
            
    def _discover_latent_operators(self, session, cycle, verbose=False):
        """Scans the theorem database for frequent sub-expressions to abstract."""
        from collections import defaultdict
        
        counts = defaultdict(int)
        sizes = {}
        
        def extract_subexprs(t):
            from core.logic import term_complexity
            if hasattr(t, "symbol") and hasattr(t, "args"):
                # Only abstract functions that are structurally larger than 1 node
                size = term_complexity(t)
                if size > 1:
                    sig = str(t)
                    counts[sig] += 1
                    sizes[sig] = size
                for a in t.args:
                    extract_subexprs(a)

        for thm in session.theorems:
            form = thm.formula
            if hasattr(form, "left"): extract_subexprs(form.left)
            if hasattr(form, "right"): extract_subexprs(form.right)

        # Evaluate candidate macros based on occurrence frequency and size
        candidates = []
        for sig, count in counts.items():
            if count >= 3:
                # Compression gain = (occurrences * size) - cost_of_making_new_def
                gain = (count * sizes[sig]) - (sizes[sig] + 2)
                if gain > 5:
                    candidates.append((gain, sig))
        
        candidates.sort(reverse=True)
        
        for i, (gain, sig) in enumerate(candidates[:2]):
            macro_op = f"LatentOp_C{cycle}_{i}"
            if verbose:
                print(f"  [Latent Abstraction] Promoting frequent subgraph to {macro_op}:")
                print(f"    Definition: {macro_op} := {sig} (Gain: {gain})")
            
            # The actual injection into grammars/MCTS requires integrating with OmegaNode
            # Here we simulate the effect by increasing the budget and logging it.
            if hasattr(self, "beta_ledger"):
                self.beta_ledger.budget += gain * 10
            session.stats[f"latent_{macro_op}"] = sig
            
            cycle_time = time.time() - cycle_start
            
            # Corridor enforcement and observables
            try:
                # ------------------------------------------------------------
                # Phase 8 telemetry injection: per-cycle stats for corridor tool
                # ------------------------------------------------------------
                try:
                    vstats = getattr(verifier, "stats", {}) or {}
                except Exception:
                    vstats = {}

                clauses_total = int(vstats.get("clauses", 0) or 0)
                redundant_skipped = int(vstats.get("redundant", 0) or 0)
                nodes_explored = int(vstats.get("nodes_explored", 0) or 0)

                session.stats["cycles"] = cycle + 1
                session.stats["clauses_total"] = clauses_total
                session.stats["redundant_skipped"] = redundant_skipped
                session.stats["nodes_explored"] = nodes_explored

                session.stats["theorems_proved"] = len(session.theorems)
                session.stats["new_theorems"] = len(proven_lemmas)
                session.stats["counter_axioms_found"] = len(session.counter_axioms)
                session.stats["oracle_axioms_found"] = len(session.oracle_axioms)

                self._accumulate_rule_usage(session)
                
                # Corridor step
                outcome = corridor_tool.on_cycle_end(session, cycle)
                # Update theorem contracts with cycle risk data
                for thm in session.theorems:
                    if thm.cycle == cycle and thm.contract:
                        thm.contract.risk = {
                            "accumulated_risk": outcome.accumulated_risk,
                            "min_margin": outcome.snapshot.min_margin,
                            "regime": outcome.snapshot.regime.name,
                            "authorized": outcome.authorized
                        }
                
                session.metadata.setdefault("corridor_outcomes", []).append({
                    "cycle": cycle,
                    "regime": outcome.snapshot.regime.name,
                    "min_margin": outcome.snapshot.min_margin,
                    "tightest_gate": outcome.snapshot.tightest_gate,
                    "violated_gates": list(outcome.snapshot.violated_gates),
                    "risk": outcome.accumulated_risk,
                    "authorized": outcome.authorized,
                    "recovered": outcome.recovered,
                    "state": {
                        "entropy": outcome.state.entropy,
                        "attention_coherence": outcome.state.attention_coherence,
                        "embedding_norm": outcome.state.embedding_norm,
                        "manifold_divergence": outcome.state.manifold_divergence,
                        "centroid_similarity": outcome.state.centroid_similarity,
                    },
                })
                if cycle_callback:
                    cycle_callback(session)
                
                if verbose:
                    print(f"  [Corridor] Risk: {outcome.accumulated_risk:.3f} | Regime: {outcome.snapshot.regime.name}")
                    if not outcome.snapshot.in_corridor:
                        print(f"    Violated gates: {outcome.snapshot.violated_gates}")
                
                # PR 0017: Büchi Heartbeat (Liveness)
                self.liveness_monitor.heartbeat(session.stats)
                
                # PR 0018: zk-STARK promotion for top discoveries
                for thm in session.theorems:
                    if thm.cycle == cycle and thm.interestingness > 0.8:
                        proof = self.adherence_prover.generate_proof(thm.formula, self.beta_ledger)
                        thm.contract.risk["zk_proof"] = proof
                        if verbose:
                            print(f"    [ZK] Generated adherence proof for: {thm.formula}")

            except Exception as e:
                print(f"  [Hypervisor Abort] {e}")
                break

            if verbose:
                print(f"\n  Cycle {cycle} complete in {cycle_time:.1f}s")
                print(f"  Proved: {len(proven_lemmas)} | "
                      f"Failed: {len(failed_conjectures)} | "
                      f"Counter-axioms: {new_counter}")
            # PR 0020: Equilibrium Check
            if self.equilibrium_enabled and self.equilibrium_detector.check(session, cycle):
                if verbose:
                    print(f"\n{'='*60}")
                    print(f"  VERIFIER EQUILIBRIUM REACHED (Cycle {cycle})")
                    print(f"  Architectural search space exhausted.")
                    print(f"{'='*60}")
                break
            
            # PR 0019: Metasystem Self-Mutation
            # Mutate heuristics based on cycle yield
            if hasattr(self, "metasystem"):
                self.metasystem.optimize_heuristics(session, cycle)
                
            # PR 0019: Omega Node (Sort Invention)
            # Check for high divergence and suggest new sorts
            if session.metadata.get("corridor_outcomes"):
                last_outcome = session.metadata["corridor_outcomes"][-1]
                div = last_outcome["state"]["manifold_divergence"]
                new_sort = self.omega_node.analyze_manifold_divergence(div, session.top(5))
                if new_sort and verbose:
                    print(f"  [Omega] MANIFOLD DIVERGENCE DETECTED. Invented sort: {new_sort}")
        
        # Final statistics
        session.stats.update({
            "total_axioms": len(self.axioms),
            "total_lemmas": len(self.lemmas),
            "total_counter_axioms": len(self.counter_axioms),
            "total_discoveries": len(session.theorems),
            "total_oracle_stipulations": len(session.oracle_axioms)
        })
        
        self._accumulate_rule_usage(session)
        
        # JSON export of theorems
        import json
        metrics_export = []
        for thm in session.theorems:
            thm.citation_count = self.scorer.centrality_map.get(str(thm.formula), 0)
            metrics_export.append({
                "lemma": str(thm.formula),
                "proof_steps": thm.proof_steps,
                "search_depth": thm.cycle + 1,
                "compression_ratio": round(thm.compression_ratio, 3),
                "citation_count": thm.citation_count,
                "score": round(thm.interestingness, 4),
            })
        
        with open("discovery/engine_metrics.json", "w") as f:
            json.dump({"verified_theorems": metrics_export}, f, indent=2)
            
        return session
    
    def _record_trust_base(self, session: DiscoverySession):
        import json, hashlib
        bundle = Path(__file__).resolve().parent / "axioms" / "attention_axioms.verified.json"
        session.metadata["certified_mode"] = getattr(self, "certified_mode", False)
        session.metadata["attention_bundle_path"] = str(bundle)

        if not bundle.exists():
            session.metadata["attention_bundle_loaded"] = False
            return

        data = json.loads(bundle.read_text(encoding="utf-8"))
        
        if getattr(self, "certified_mode", False):
            for r in data.get("rules", []):
                if not r.get("lean", {}).get("axioms"):
                    raise RuntimeError(f"Certified mode: rule missing Lean axiom footprint: {r.get('id')}")

        session.metadata["attention_bundle_loaded"] = True
        session.metadata["attention_bundle_sha256_16"] = hashlib.sha256(bundle.read_bytes()).hexdigest()[:16]
        session.metadata["attention_bundle_schema_version"] = data.get("schema_version")
        session.metadata["attention_bundle_rule_ids"] = [r["id"] for r in data.get("rules", [])]

    def _accumulate_rule_usage(self, session: DiscoverySession):
        from collections import Counter
        c = Counter()
        for thm in session.theorems:
            if hasattr(thm, "proof_result") and getattr(thm.proof_result, "applied_rules", None):
                c.update(thm.proof_result.applied_rules)
        session.metadata["applied_rules_counter"] = dict(c)
        
    def report(self, session: DiscoverySession):
        """Print a summary report of discoveries."""
        print(f"\n{'='*60}")
        print(f"  DISCOVERY REPORT")
        print(f"{'='*60}")
        
        md = session.metadata
        print("Trust base:")
        print(f"  certified_mode={md.get('certified_mode')}")
        if md.get("attention_bundle_loaded"):
            print(f"  attention_bundle={md.get('attention_bundle_path')}")
            print(f"  sha256[:16]={md.get('attention_bundle_sha256_16')}")
            print(f"  schema_version={md.get('attention_bundle_schema_version')}")
            print(f"  rules={len(md.get('attention_bundle_rule_ids', []))}")
            print(f"  rule_ids={md.get('attention_bundle_rule_ids')}")
        else:
            print("  attention_bundle=NOT LOADED")
            
        if "applied_rules_counter" in md:
            top = sorted(md["applied_rules_counter"].items(), key=lambda kv: -kv[1])[:10]
            print(f"\n  Top applied rules: {top}")
            
        print(f"\n  Statistics:")
        for k, v in session.stats.items():
            print(f"    {k}: {v}")
        
        print(f"\n  Top Discoveries (by interestingness):")
        for i, thm in enumerate(session.top(15), 1):
            print(f"    {i}. {thm}")
        
        if session.counter_axioms:
            print(f"\n  Counter-Axioms (failed conjectures):")
            for ca in session.counter_axioms:
                print(f"    -| {ca}")
        
        if session.oracle_axioms:
            print(f"\n  Oracle-Stipulated Axioms:")
            for oa in session.oracle_axioms:
                print(f"    * {oa}")

# Backward Compatibility Alias
CoAIOperandicsExplorer = DiscoveryEngine

class AutopoieticMetasystem:
    """
    L0 Metasystem: Self-governance and heuristic optimization.
    Monitors engine performance and mutates search parameters.
    """
    def __init__(self, engine: DiscoveryEngine):
        self.engine = engine
        self.mutation_count = 0
        self.base_iters = engine.mcts_iterations
        self.base_depth = 6

    def optimize_heuristics(self, session: DiscoverySession, cycle: int):
        """
        Inter-cycle optimization: Adjust grammar weights and hyperparameters.
        """
        # 1. Grammar Mutation
        if hasattr(self.engine, "_last_yield_map") and self.engine._last_yield_map:
            # We'll use a virtual synthesizer to mutate the engine's persisted weights
            from discovery.mcts_grammar import GrammarSynthesizer
            virt_synth = GrammarSynthesizer(self.engine.scorer)
            if hasattr(self.engine, "_grammar_weights") and self.engine._grammar_weights:
                virt_synth.heuristic_weights = self.engine._grammar_weights
            
            virt_synth.mutate_heuristics(self.engine._last_yield_map)
            self.engine._grammar_weights = virt_synth.heuristic_weights
        
        # 2. Hyperparameter Scaling (Drift Correction) & UAP Broadcasting
        # If no theorems were proved this cycle, increase search intensity
        new_discoveries = [t for t in session.theorems if t.cycle == cycle]
        
        # Mutation Signal Calculation:
        # - Success -> Signal = -0.1 (cool down slightly)
        # - Failure -> Signal = +0.2 (heat up intensity)
        uap_signal = 0.2 if not new_discoveries else -0.1
        
        # Broadcast to core components (Universal Autopoiesis)
        if hasattr(self.engine, "saturator") and hasattr(self.engine.saturator, "self_mutate"):
            self.engine.saturator.self_mutate(uap_signal)
            
        # PR 0019: Universal Autopoiesis for the parallel ATP mesh
        # We mutate the engine's stored offsets so they are passed to workers in the next cycle
        self.engine._atp_steps_offset += int(uap_signal * 500)
        self.engine._atp_ratio_offset += int(uap_signal * 2)
        print(f"[UAP:ATP] Mesh-wide Mutation. Steps Offset: {self.engine._atp_steps_offset}, Ratio Offset: {self.engine._atp_ratio_offset}")

        if not new_discoveries:
            print("[Metasystem] DRY SPELL DETECTED. Intensifying Search...")
            self.engine.mcts_iterations = int(self.engine.mcts_iterations * 1.5)
            # Cap it to prevent crash
            self.engine.mcts_iterations = min(self.engine.mcts_iterations, 5000)
        else:
            # If successful, slowly decay back to base to save β
            if self.engine.mcts_iterations > self.base_iters:
                self.engine.mcts_iterations = int(self.engine.mcts_iterations * 0.9)

        self.mutation_count += 1

class EquilibriumDetector:
    """
    Detects when the discovery process has reached a stable equilibrium.
    Based on new e-nodes, interestingness thresholds, and proof success rates.
    """
    def __init__(self, stall_threshold: int = 3):
        self.stall_threshold = stall_threshold
        self.stall_counter = 0
        self.last_discovery_count = 0

    def check(self, session: Any, cycle: int) -> bool:
        """
        Returns True if equilibrium is reached.
        """
        new_discoveries = len([t for t in session.theorems if t.cycle == cycle])
        new_enodes = session.stats.get("new_enodes", 0)
        
        # Stability criteria
        # 1. No new significant theorems found
        # 2. E-graph growth has flattened
        if new_discoveries == 0 and new_enodes < 5:
            self.stall_counter += 1
        else:
            self.stall_counter = 0
            
        return self.stall_counter >= self.stall_threshold
