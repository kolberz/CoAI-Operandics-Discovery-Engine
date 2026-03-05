from __future__ import annotations

import sys
import os
import math
import time
import logging
from collections import Counter
from typing import List, Set, Dict, Tuple, Optional, Sequence

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from core.logic import Formula, Forall, Equality, Variable, Constant, Function, MODULE, PRED, REAL
from core.orchestral import (
    LatentState, 
    Orchestrator, 
    standard_corridor, 
    EdgeWalkAndDampenLogger,
    InterestingnessScore,
    StepOutcome
)
from discovery.engine import CoAIOperandicsExplorer, DiscoveredTheorem, DiscoverySession
from prover.general_atp import GeneralATP, ProofResult

from core.telemetry import (
    TraceChannelRegistry, 
    L0MetricAggregator, 
    AnomalyDetectedException,
    InfoTheoryMetrics,
    UncertaintyMetrics,
    ReasoningMetrics,
    TopologyMetrics,
    ContextMetrics,
    GroundingMetrics
)

# Configure diagnostic logging for the governed engine
logging.basicConfig(level=logging.INFO, format="%(message)s")
corridor_logger = logging.getLogger("corridor.telemetry")

class GovernedOperandicsExplorer(CoAIOperandicsExplorer):
    """
    Enhanced Discovery Engine with Orchestral Governance.
    Guides the search for interesting theorems using a latent manifold controller.
    """
    
    def __init__(self, 
                 max_clauses: int = 500, 
                 max_depth: int = 8,
                 min_interestingness: float = 0.1,
                 risk_budget: float = 1.0):
        super().__init__(max_clauses, max_depth, min_interestingness)
        
        # Add higher-level entropy/cost axioms
        self._add_more_axioms()
        self.orch = standard_corridor(
            entropy_floor=0.5,      # Allow some low-entropy starting states
            entropy_ceiling=3.0,    # Cap complexity
            divergence_floor=0.3,   # Ensure some novelty
            risk_budget=risk_budget
        )
        
        # Setup telemetry
        self.telemetry = EdgeWalkAndDampenLogger(log_every_step=True)
        self.orch._telemetry = self.telemetry
        self.orch._dampen_enabled = True
        
        # Build 2.7.0 L0 Governance
        self.bus = TraceChannelRegistry()
        self.governor = L0MetricAggregator(self.bus)
        
    def _add_more_axioms(self):
        """Add complex additivity and identity axioms for higher metrics."""
        from core.logic import MODULE, REAL
        from discovery.engine import Seq, ResourceCost, Ent, Comp, plus, ID_M, ZERO_J, ZERO_bit, R_ZERO, Forall, Equality, Variable
        m1 = Variable("M1", MODULE)
        m2 = Variable("M2", MODULE)
        
        # Resource Cost Additivity
        self._add_axiom(Forall(m1, Forall(m2, Equality(ResourceCost(Seq(m1, m2)), plus(ResourceCost(m1), ResourceCost(m2))))), "res_additivity")
        self._add_axiom(Equality(ResourceCost(ID_M), ZERO_J), "res_id")
        
        # Entropy Additivity
        self._add_axiom(Forall(m1, Forall(m2, Equality(Ent(Seq(m1, m2)), plus(Ent(m1), Ent(m2))))), "ent_additivity")
        self._add_axiom(Equality(Ent(ID_M), ZERO_bit), "ent_id")
        
        # Complexity Additivity
        self._add_axiom(Forall(m1, Forall(m2, Equality(Comp(Seq(m1, m2)), plus(Comp(m1), Comp(m2))))), "comp_additivity")
        self._add_axiom(Equality(Comp(ID_M), R_ZERO), "comp_id")
        
        self._add_cycle_6_axioms()
        
    def _add_cycle_6_axioms(self):
        """Inject connective tissue for compositional discovery."""
        from core.logic import MODULE, PRED
        from discovery.engine import Par_Dyn, Barrier, Risk, Forall, Equality, Variable, Implies
        m1 = Variable("M1", MODULE)
        m2 = Variable("M2", MODULE)
        m3 = Variable("M3", MODULE)
        p = Variable("P", PRED)

        # (C-1) Risk Congruence
        self._add_axiom(Forall(m1, Forall(m2, Forall(m3, 
            Implies(Equality(Risk(m1), Risk(m2)), 
                    Equality(Risk(Par_Dyn(m3, m1)), Risk(Par_Dyn(m3, m2))))
        ))), "risk_cong_par")
        
        self._add_axiom(Forall(m1, Forall(m2, Forall(p, 
            Implies(Equality(Risk(m1), Risk(m2)), 
                    Equality(Risk(Barrier(m1, p)), Risk(Barrier(m2, p))))
        ))), "risk_cong_barrier")

        # (C-2) Associativity
        self._add_axiom(Forall(m1, Forall(m2, Forall(m3, 
            Equality(Par_Dyn(m1, Par_Dyn(m2, m3)), Par_Dyn(Par_Dyn(m1, m2), m3))
        ))), "par_associativity")

        # Inject RISK_ASSOC: ∀A,B,C. Risk(Par_Dyn(A, Par_Dyn(B,C))) = Risk(Par_Dyn(Par_Dyn(A,B), C))
        m1, m2, m3 = Variable("A", MODULE), Variable("B", MODULE), Variable("C", MODULE)
        self.axioms.append(Forall(m1, Forall(m2, Forall(m3,
            Equality(
                Risk(Par_Dyn(m1, Par_Dyn(m2, m3))),
                Risk(Par_Dyn(Par_Dyn(m1, m2), m3))
            )
        ))))
        
        self._add_phase_3_axioms()
        
    def _add_phase_3_axioms(self):
        """Phase 3: Quantum Superposition and Self-Reference axioms."""
        from discovery.engine import Superpose, Evidence, Risk, max_f, ZERO_J
        m1 = Variable("m1", MODULE)
        m2 = Variable("m2", MODULE)
        p = Variable("p", PRED)

        # Q1: Risk Idempotence of Superposition
        self._add_axiom(Forall(m1, Equality(Risk(Superpose(m1, m1)), Risk(m1))), "superpose_idempotence")

        # Q2: Commutativity
        self._add_axiom(Forall(m1, Forall(m2, Equality(Superpose(m1, m2), Superpose(m2, m1)))), "superpose_comm")

        # Q3: Risk of Superposition = max
        self._add_axiom(Forall(m1, Forall(m2, Equality(Risk(Superpose(m1, m2)), max_f(Risk(m1), Risk(m2))))), "risk_superpose")

        # R1: Evidence Transparency (Self-Reference)
        # Risk of Evidence(P) is zero (stipulated for pure evidence)
        self._add_axiom(Forall(p, Equality(Risk(Evidence(p)), Function("R_ZERO", (), REAL))), "evidence_neutral")
        
    def _generate_compositional_conjectures(self) -> List[Formula]:
        """(T8-T11) Recursively nest proven lemmas to probe multi-operator interaction."""
        from core.logic import MODULE
        from discovery.engine import Par_Dyn, Barrier, Risk, Equality, Forall, Variable, P_TRUE, ID_M, Seq, Superpose, Evidence
        conjs = []
        m1 = Variable("M1", MODULE)
        
        # 1. Baseline: High-interest compositions from lemmas
        for lemma in self.lemmas:
            if not isinstance(lemma, Forall): continue
            body = lemma.body
            if not isinstance(body, Equality): continue
            
            # Pattern matching for Risk(Term(M)) = Risk(M)
            if isinstance(body.left, Function) and body.left.symbol == "Risk":
                op_term = body.left.args[0]
                if isinstance(op_term, Function):
                    # Nesting: Op(Op(M))
                    # Ensure we preserve arity for standard operators
                    if op_term.symbol in ("Par_Dyn", "Seq"):
                        # If it was Par_Dyn(M1, ID_M), nest it: Par_Dyn(Par_Dyn(M1, ID_M), ID_M)
                        nested = Function(op_term.symbol, (op_term, ID_M), MODULE)
                        conjs.append(Forall(m1, Equality(Risk(nested), Risk(m1))))
                    elif op_term.symbol == "Barrier":
                        # Barrier(Barrier(M, P), P)
                        nested = Function(op_term.symbol, (op_term, P_TRUE), MODULE)
                        conjs.append(Forall(m1, Equality(Risk(nested), Risk(m1))))
                    elif op_term.symbol == "Sec_Filter":
                        nested = Function(op_term.symbol, (op_term,), MODULE)
                        conjs.append(Forall(m1, Equality(Risk(nested), Risk(m1))))
                        
                    # Parallel Observer: Risk(Par_Dyn(M, Op(M)))
                    p_obs = Par_Dyn(m1, op_term)
                    conjs.append(Forall(m1, Equality(Risk(p_obs), Risk(m1))))

        t11_term = Par_Dyn(m1, Barrier(m1, P_TRUE))
        conjs.append(Forall(m1, Equality(Risk(t11_term), Risk(m1))))
        
        # 4. Phase 3: Superposition stacks
        super_term = Superpose(m1, m1)
        conjs.append(Forall(m1, Equality(Risk(super_term), Risk(m1))))
        
        return conjs

    def detect_universal_schemas(self, verifier: GeneralProver) -> List[Formula]:
        """Scans lemmas for patterns and attempts bounded induction."""
        from discovery.engine import Barrier, Risk, P_TRUE, ID_M
        schemas = []
        # Pattern 1: Risk(Barrier^n(M, True)) = Risk(M)
        # Check if we have instances for n=1, 2
        has_n1 = any("Risk(Barrier(M1, P_TRUE)) = Risk(M1)" in str(l) for l in self.lemmas)
        
        if has_n1:
            print("  [SCHEMA_DETECTION] Potential Barrier schema detected. Running induction...")
            m = Variable("M", MODULE)
            all_proven = True
            for n in range(1, 21):
                term = m
                for _ in range(n):
                    term = Barrier(term, P_TRUE)
                goal = Forall(m, Equality(Risk(term), Risk(m)))
                res = verifier.prove_with_normalization(goal, self.lemmas, max_steps=2000)
                if not res.success:
                    all_proven = False
                    break
            if all_proven:
                # We can't represent ∀n directly in classical FOL easily without induction schema,
                # but we can promote the n=20 instance as a powerful lemma.
                schema_lemma = Forall(m, Equality(Risk(term), Risk(m)))
                print(f"  [⭐ SCHEMA_PROVEN] ∀n ∈ [1, 20]. Risk(Barrier^n(M, P_TRUE)) = Risk(M)")
                schemas.append(schema_lemma)

        return schemas

    def _calculate_shannon_entropy(self, formulas: List[Formula]) -> float:
        """Calculates symbol-distribution entropy in nats."""
        symbols = []
        for f in formulas:
            # Simple recursive symbol collection
            symbols.extend(self._get_formula_symbols(f))
        
        if not symbols:
            return 0.0
            
        counts = Counter(symbols)
        total = sum(counts.values())
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log(p)
        return entropy

    def _get_formula_symbols(self, f: Formula) -> List[str]:
        syms = []
        if isinstance(f, (Function, Constant, Variable)):
            syms.append(getattr(f, 'symbol', str(f)))
        if hasattr(f, 'args'):
            for arg in f.args:
                syms.extend(self._get_formula_symbols(arg))
        if hasattr(f, 'left'):
            syms.extend(self._get_formula_symbols(f.left))
            syms.extend(self._get_formula_symbols(f.right))
        if hasattr(f, 'body'):
            syms.extend(self._get_formula_symbols(f.body))
        return syms

    def _calculate_manifold_divergence(self, conjectures: List[Formula]) -> float:
        """
        Measures how far current conjectures are from the axiom set.
        Uses structural similarity proxy.
        """
        if not conjectures:
            return 0.0
            
        axiom_sym_sets = [set(self._get_formula_symbols(a)) for a in self.axioms]
        divergences = []
        
        for c in conjectures:
            c_syms = set(self._get_formula_symbols(c))
            # Novelty = fraction of symbols not in any single axiom
            # (Simplified distance metric)
            max_overlap = 0.0
            for a_syms in axiom_sym_sets:
                if not a_syms: continue
                overlap = len(c_syms & a_syms) / len(c_syms | a_syms)
                max_overlap = max(max_overlap, overlap)
            divergences.append(1.0 - max_overlap)
            
        return sum(divergences) / len(divergences)

    def governed_discovery_cycle(self, 
                                 max_cycles: int = 10, 
                                 verbose: bool = True) -> DiscoverySession:
        """
        Run the governed discovery loop using the Orchestrator.
        """
        session = DiscoverySession()
        verifier = GeneralATP()
        
        for axiom in self.axioms:
            verifier.add_axiom(axiom)
            
        # Initial state estimation
        current_state = LatentState(
            entropy=self._calculate_shannon_entropy(self.axioms),
            attention_coherence=1.0,
            embedding_norm=float(len(self.axioms)),
            manifold_divergence=0.0,
            centroid_similarity=1.0
        )
        
        print(f"\n[GOVERNANCE] Starting Discovery session with budget {self.orch.risk_budget}")
        print(f"Initial State: {current_state}\n")

        proven_count = 0
        total_conjectures = 0

        for cycle in range(max_cycles):
            self._current_cycle = cycle
            
            # 1. Orchestrator Step
            outcome = self.orch.step(current_state)
            
            if not outcome.authorized:
                print(f"\n[ABORT] Governance Risk Budget Exceeded at Cycle {cycle}.")
                break
                
            if verbose:
                auth_str = "AUTHORIZED" if outcome.authorized else "DENIED"
                print(f"\n--- CYCLE {cycle} [{auth_str}] ---")

            # 1.1 Build 2.7.0 L0 Pre-Thought Check
            try:
                # Mock telemetry publication based on current state
                self.bus.publish("InfoTheory", InfoTheoryMetrics(
                    candidate_entropy=current_state.entropy,
                    kl_divergence_from_prior=0.5,
                    mutual_info_with_context=3.0
                ))
                self.bus.publish("Uncertainty", UncertaintyMetrics(
                    epistemic_uncertainty=0.2,
                    aleatoric_uncertainty=0.1,
                    training_distribution_distance=current_state.manifold_divergence
                ))
                self.bus.publish("Reasoning", ReasoningMetrics(
                    reasoning_chain_depth=int(current_state.embedding_norm),
                    contradiction_detected_count=0,
                    backtracking_frequency=0.1,
                    logical_validity_score=0.95
                ))
                self.bus.publish("Topology", TopologyMetrics(
                    attention_graph_density=0.6,
                    information_flow_bottlenecks=(),
                    attention_hub_count=12
                ))
                self.bus.publish("Context", ContextMetrics(
                    context_coverage_ratio=0.85,
                    retrieval_vs_generation_ratio=0.7,
                    cross_attention_concentration=0.4
                ))
                self.bus.publish("Grounding", GroundingMetrics(
                    grounding_confidence=0.9,
                    ungrounded_statement_ratio=0.05
                ))

                self.governor.analyze_pre_thought_cloud()
                if verbose: print("  [L1:PreGeneration_Grounding_Complete] -> CLEARED FOR DISCOVERY.")
            except AnomalyDetectedException as e:
                print(f"  [ABORT] L0 Governance killed discovery cycle: {e}")
                break

            # 2. Stable Depth Configuration (Search depth locked for consistency)
            self.saturator.max_depth = 8
            self.saturator.max_clauses = 500
            
            # 3. Discovery Heuristics: O-FLOW Two-Phase Saturation
            limit = 100 if outcome.snapshot.min_margin < 0.1 else 50
            
            # Phase 1-T: Topological Scaffolding (no constants/scalars)
            if verbose: print(f"  Phase 1-T: Topological Scaffolding (depth={self.saturator.max_depth})...")
            topo_theorems = self.discover_theorems(limit=limit, mode="topological")
            
            # Phase 1-A: Algebraic Instantiation (filling constants)
            if verbose: print(f"  Phase 1-A: Algebraic Instantiation...")
            # We use Phase 1-T results to seed the KB for Phase 1-A
            # For simplicity, we just run saturation in 'algebraic' mode which now includes more rules
            # and we merge the results.
            algebraic_theorems = self.discover_theorems(limit=limit, mode="algebraic")
            
            theorems = topo_theorems + algebraic_theorems
            if verbose: print(f"    Found {len(theorems)} potential theorems ({len(topo_theorems)} topo, {len(algebraic_theorems)} alg).")
            
            # 4. Hypothesize & Verify
            conjectures, cycle_asts = self.conjecture_new_axioms(theorems, seed_asts=getattr(self, 'incoming_asts', []))
            session.mcts_asts.extend(cycle_asts)
            
            # Also generate structural conjectures
            structural = self._generate_structural_conjectures(theorems)
            conjectures.extend(structural)
            
            # Also generate heuristic conjectures (cycle-dependent for variety)
            heuristic = self._generate_heuristic_conjectures(getattr(self, '_current_cycle', 0))
            conjectures.extend(heuristic)

            # (Cycle-6) Recursive Compositional Synthesis (Dig Deeper)
            compositional = self._generate_compositional_conjectures()
            conjectures.extend(compositional)
            
            # Deduplicate by string representation
            # (This part was missing in the original and is good practice after extending conjectures)
            unique_conjectures = []
            seen_conjecture_strs = set()
            for conj in conjectures:
                conj_str = str(conj)
                if conj_str not in seen_conjecture_strs:
                    unique_conjectures.append(conj)
                    seen_conjecture_strs.add(conj_str)
            conjectures = unique_conjectures
            if verbose: print(f"  Phase 2: Promoted {len(conjectures)} conjectures.")

            proven_in_cycle = []
            max_p_steps = 1000 + (cycle * 50)
            
            if verbose: print(f"  Phase 3: Verifying (max_steps={max_p_steps})...")
            for conj in conjectures[:30]: # Increased cap
                if str(conj) in self._proven_strs: continue
                if str(conj) in self._failed_conjecture_strs: continue
                
                res = verifier.prove(conj, self) # Note: GeneralATP.prove takes (conjecture, kb)
                if res.success:
                    thm = DiscoveredTheorem(conj, self.scorer.score(conj), self.scorer.classify(conj), "PROVED", cycle)
                    thm.proof_steps = res.steps
                    if verbose: 
                        method_str = f" [{res.reason}]" if res.reason != "PROVED" else ""
                        print(f"    [OK] PROVED: {conj}{method_str}")
                    proven_in_cycle.append(thm)
                    self.lemmas.append(conj)
                    verifier.add_axiom(conj)
                    self._proven_strs.add(str(conj))
                    session.theorems.append(thm)
                    
                    # [MANIFESTATION CHECK]
                    # If this theorem involves Evidence, it's a structural manifestation
                    if "Evidence" in str(conj):
                        print(f"    [✨ MANIFESTATION] Self-referential law confirmed: {conj}")
                    
                    # [THEOREM PROMOTION]
                    # Automatically add proven equality results to the prover's E-Graph normalization
                    # This accelerates future proofs in the same session.
                    if isinstance(conj, Equality) or (isinstance(conj, Forall) and isinstance(conj.body, Equality)):
                        verifier._egraph_normalization_enabled = True # Ensure enabled
                else:
                    if verbose:
                        print(f"    [FAIL] {conj} | Stats: {res.diagnostics}")
                    self._failed_conjecture_strs.add(str(conj))

            # 6. Schema Induction Step
            if cycle % 5 == 0:
                schemas = self.detect_universal_schemas(verifier)
                for schema in schemas:
                    if str(schema) not in self._proven_strs:
                        self.lemmas.append(schema)
                        verifier.add_axiom(schema)
                        self._proven_strs.add(str(schema))
                        print(f"    [PROMOTED_SCHEMA] {schema}")

            # 5. Calculate New Latent State
            # ... (Rest of state logic)
            proven_count += len(proven_in_cycle)
            total_conjectures += len(conjectures)
            
            # Update coherence based on actual verification results
            coherence = len(proven_in_cycle) / max(1, len(conjectures))
            
            # Update knowledge base entropy
            kb_formulas = self.axioms + self.lemmas
            kb_entropy = self._calculate_shannon_entropy(kb_formulas)
            
            # Update manifold divergence
            div = self._calculate_manifold_divergence(conjectures)
            
            # Mock proof depth and confluence for telemetry
            proof_depth = max([thm.proof_steps for thm in proven_in_cycle]) if proven_in_cycle else 1
            confluence = 0.85 if any("confluent" in str(thm.formula) for thm in proven_in_cycle) else 0.5
            
            current_state = LatentState(
                entropy=kb_entropy,
                attention_coherence=_clamp(coherence * 2.0, 0.0, 1.0), 
                embedding_norm=float(len(kb_formulas)),
                manifold_divergence=div,
                centroid_similarity=1.0 - div
            )
            
            # Publish refined telemetry to TraceChannelRegistry if available
            if hasattr(self.orch, '_telemetry_bus') and self.orch._telemetry_bus:
                bus = self.orch._telemetry_bus
                # We can't easily import the dataclasses here without refactoring, 
                # but we can simulate the L1-to-L0 channel push
                pass

        session.stats = {
            "total_axioms": len(self.axioms),
            "total_lemmas": len(self.lemmas),
            "total_discoveries": len(session.theorems),
            "final_risk": self.orch.accumulated_risk,
            "peak_depth": proof_depth if 'proof_depth' in locals() else 0
        }
        return session

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

if __name__ == "__main__":
    # Test Run
    explorer = GovernedOperandicsExplorer(min_interestingness=0.1)
    session = explorer.governed_discovery_cycle(max_cycles=500)
    explorer.report(session)
