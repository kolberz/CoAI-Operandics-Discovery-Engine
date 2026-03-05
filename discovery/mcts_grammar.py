import os
import math
import random
import copy
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Callable
from core.logic import *
from discovery.scorer import InterestingnessScorer
from core.beta_calculus import BetaLedger, calculate_surprisal
from collections import defaultdict

# --- 1. Typed Grammar Defs ---
class Axis(Enum):
    B = "batch"
    H = "heads"
    N = "seq_len"
    D = "model_dim"
    Dv = "value_dim"
    R = "feature_dim"
    ONE = "scalar"

@dataclass(frozen=True)
class TensorType:
    axes: Tuple[Axis, ...]
    def n_count(self) -> int:
        return self.axes.count(Axis.N)

Q_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.D))
K_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.D))
V_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.Dv))
OUT_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.Dv))

PHI_Q_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.R))
PHI_K_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.R))
SUMMARY_TYPE = TensorType((Axis.B, Axis.H, Axis.R, Axis.Dv))
NORM_SUMMARY = TensorType((Axis.B, Axis.H, Axis.R, Axis.ONE))
DENOM_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.ONE))
SCORE_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.N))
SCALAR_TYPE = TensorType((Axis.B, Axis.H, Axis.N, Axis.ONE))

@dataclass
class Production:
    name: str
    input_types: Tuple[TensorType, ...]
    output_type: TensorType

GRAMMAR = [
    Production("Q",     (), Q_TYPE),
    Production("K",     (), K_TYPE),
    Production("V",     (), V_TYPE),
    Production("Ones",  (), SCALAR_TYPE),
    
    Production("phi",  (Q_TYPE,), PHI_Q_TYPE),
    Production("phi",  (K_TYPE,), PHI_K_TYPE),
    
    Production("OuterN",   (PHI_K_TYPE, V_TYPE), SUMMARY_TYPE),
    Production("OuterN_1", (PHI_K_TYPE, SCALAR_TYPE), NORM_SUMMARY),
    
    Production("DotR",  (PHI_Q_TYPE, SUMMARY_TYPE), OUT_TYPE),
    Production("DenDotR", (PHI_Q_TYPE, NORM_SUMMARY), DENOM_TYPE),
    
    Production("Normalize", (OUT_TYPE, DENOM_TYPE), OUT_TYPE),
    
    Production("PhiScore", (PHI_Q_TYPE, PHI_K_TYPE), SCORE_TYPE),
    Production("AttnMul",  (SCORE_TYPE, V_TYPE), OUT_TYPE),
    Production("AttnMul_1", (SCORE_TYPE, SCALAR_TYPE), DENOM_TYPE),

    # Tranche 6: Algebraic Refinement
    Production("Half", (OUT_TYPE,), OUT_TYPE),
    Production("Trotter", (OUT_TYPE, OUT_TYPE), OUT_TYPE),
]

# --- 2. AST Nodes ---
class ASTNode:
    def __init__(self, prod: Production, children: List['ASTNode'] = None):
        self.prod = prod
        self.children = children
        self.type = prod.output_type

    def __str__(self):
        if not self.children:
            return self.prod.name
        child_strs = [str(c) for c in self.children]
        return f"{self.prod.name}({', '.join(child_strs)})"

def tree_cost(node: ASTNode) -> int:
    self_cost = node.type.n_count()
    if not node.children: return self_cost
    return max(self_cost, max(tree_cost(c) for c in node.children))

def get_first_hole(node: ASTNode, parent=None, idx=0):
    if node.children is None:
        return (parent, idx, node)
    for i, c in enumerate(node.children):
        res = get_first_hole(c, node, i)
        if res: return res
    return None

def apply_action(ast_root: ASTNode, prod: Production) -> ASTNode:
    new_root = copy.deepcopy(ast_root)
    res = get_first_hole(new_root)
    if not res: return new_root
    parent, idx, hole = res
    new_hole = ASTNode(prod, None if prod.input_types else [])
    if prod.input_types:
        new_hole.children = [ASTNode(Production(f"HOLE_{i}", (), t), None) for i, t in enumerate(prod.input_types)]
    
    if parent is None:
        return new_hole
    else:
        parent.children[idx] = new_hole
        return new_root

# --- 3. Numerical Falsification (CEGIS) ---
def evaluate_ast(node: ASTNode, env: Dict[str, np.ndarray]) -> np.ndarray:
    name = node.prod.name
    if not node.children:
        if name in env: return env[name]
        raise ValueError(f"Unknown terminal: {name}")
        
    args = [evaluate_ast(c, env) for c in node.children]
    
    if name == "phi":
        return np.maximum(0, args[0] + 0.1) # Positivity guaranteed
    elif name == "OuterN" or name == "OuterN_1":
        return np.einsum('bhnr,bhnx->bhrx', args[0], args[1])
    elif name == "DotR" or name == "DenDotR":
        return np.einsum('bhnr,bhrx->bhnx', args[0], args[1])
    elif name == "Normalize":
        return args[0] / (args[1] + 1e-6)
    elif name == "PhiScore":
        return np.einsum('bhnr,bhmr->bhnm', args[0], args[1])
    elif name == "AttnMul" or name == "AttnMul_1":
        return np.einsum('bhnm,bhmd->bhnd', args[0], args[1])
    elif name == "Half":
        return 0.5 * args[0]
    elif name == "Trotter":
        # Approximate as composite for CEGIS
        return np.matmul(args[0], args[1])
        
    raise ValueError(f"Unknown operation: {name}")

def numerical_falsification(ast1: ASTNode, ast2: ASTNode, n_tests=10, tol=1e-4) -> bool:
    shapes = {'B': 2, 'H': 2, 'N': 16, 'D': 4, 'Dv': 4, 'R': 6}
    for _ in range(n_tests):
        env = {
            'Q': np.random.randn(shapes['B'], shapes['H'], shapes['N'], shapes['D']),
            'K': np.random.randn(shapes['B'], shapes['H'], shapes['N'], shapes['D']),
            'V': np.random.randn(shapes['B'], shapes['H'], shapes['N'], shapes['Dv']),
            'Ones': np.ones((shapes['B'], shapes['H'], shapes['N'], 1))
        }
        # ensure numerical stability under phi
        env['Q'] = np.abs(env['Q'])
        env['K'] = np.abs(env['K'])
        
        try:
            v1 = evaluate_ast(ast1, env)
            v2 = evaluate_ast(ast2, env)
            
            err = np.max(np.abs(v1 - v2)) / (np.max(np.abs(v1)) + 1e-10)
            if err > tol:
                return False
        except Exception:
            return False
    return True

# --- 4. MCTS Components ---
class MCTSNode:
    def __init__(self, ast: ASTNode, parent=None):
        self.ast = ast
        self.parent = parent
        self.children = []
        self.visits = 0
        self.value = 0.0
        self.is_terminal = get_first_hole(self.ast) is None
        self._untried_actions = None
        
    def uct(self, c: float = 1.41, lambda_stress: float = 0.5, history: Set[int] = None) -> float:
        if self.visits == 0: return float('inf')
        
        # QED Vacuum Polarization: Novelty bias
        # Stressor is 1.0 if the node's AST hash is unknown, 0.0 otherwise.
        stressor = 0.0
        if history is not None:
            node_hash = hash(str(self.ast)) # Simple structural hash
            if node_hash not in history:
                stressor = 1.0
        
        return (self.value / self.visits) + c * math.sqrt(math.log(self.parent.visits) / self.visits) + lambda_stress * stressor

class GrammarSynthesizer:
    def __init__(self, scorer: InterestingnessScorer, max_depth: int = 6):
        self.max_depth = max_depth
        self.scorer = scorer
        self.grammar = GRAMMAR
        
        # PR 0019: Autopoietic Heuristics
        # Map of (ProductionName, OutputTypeHash) -> weight
        self.heuristic_weights: Dict[str, float] = {p.name: 1.0 for p in self.grammar}
        self.yield_history: List[Dict[str, float]] = []

        # Build exact target AST: Kernel Attention normalizer
        phiQ = ASTNode(Production("phi", (Q_TYPE,), PHI_Q_TYPE), [ASTNode(Production("Q", (), Q_TYPE), [])])
        phiK = ASTNode(Production("phi", (K_TYPE,), PHI_K_TYPE), [ASTNode(Production("K", (), K_TYPE), [])])
        score = ASTNode(Production("PhiScore", (PHI_Q_TYPE, PHI_K_TYPE), SCORE_TYPE), [phiQ, phiK])
        v = ASTNode(Production("V", (), V_TYPE), [])
        ones = ASTNode(Production("Ones", (), SCALAR_TYPE), [])
        
        num = ASTNode(Production("AttnMul", (SCORE_TYPE, V_TYPE), OUT_TYPE), [score, v])
        den = ASTNode(Production("AttnMul_1", (SCORE_TYPE, SCALAR_TYPE), DENOM_TYPE), [score, ones])
        self.target_ast = ASTNode(Production("Normalize", (OUT_TYPE, DENOM_TYPE), OUT_TYPE), [num, den])

    def mutate_heuristics(self, throughput_data: Dict[str, float]):
        """
        L0 Metasystem: Self-mutation of grammar weights based on yield.
        throughput_data: maps production names to their success participation count.
        """
        print("[Metasystem] Mutating Heuristic Weights...")
        for name, yield_val in throughput_data.items():
            if name in self.heuristic_weights:
                # Bayesian update: Adjust weight toward successful rules
                # w_new = w_old * (1 + alpha * yield)
                alpha = 0.2
                self.heuristic_weights[name] *= (1.0 + alpha * yield_val)
        
        # Normalize weights to prevent explosion
        total = sum(self.heuristic_weights.values())
        if total > 0:
            for k in self.heuristic_weights:
                self.heuristic_weights[k] /= (total / len(self.grammar))

    def _weighted_choice(self, options: List[Production]) -> Production:
        weights = [self.heuristic_weights.get(p.name, 1.0) for p in options]
        if sum(weights) == 0:
            return random.choice(options)
        
        # Using numpy for weighted choice if available, else fallback
        try:
            probs = np.array(weights) / sum(weights)
            return np.random.choice(options, p=probs)
        except Exception:
            return random.choices(options, weights=weights, k=1)[0]
        
    def _ast_to_logic(self, node: ASTNode) -> Term:
        name = node.prod.name
        if not node.children:
            if name == "Q": return Variable("Q", MODULE)
            if name == "K": return Variable("K", MODULE)
            if name == "V": return Variable("V", MODULE)
            if name == "Ones": return Constant("ID_M", MODULE)
            
        args = [self._ast_to_logic(c) for c in node.children]
        
        # PR 0013: Logic Mapping
        if name == "Half": return Function("Half", args, MODULE)
        if name == "Trotter": return Function("Trotter", args, MODULE)
        
        return Function(name, args, MODULE)

    def _get_untried_actions(self, node: MCTSNode):
        if node._untried_actions is None:
            if node.is_terminal:
                node._untried_actions = []
            else:
                hole_res = get_first_hole(node.ast)
                if hole_res:
                    req_type = hole_res[2].type
                    node._untried_actions = [p for p in self.grammar if p.output_type == req_type]
                    random.shuffle(node._untried_actions)
        return node._untried_actions

    def _simulate(self, node: MCTSNode, generation_pool: list, beta_ledger: Optional[BetaLedger] = None, used_rules: set = None) -> float:
        curr_ast = copy.deepcopy(node.ast)
        depth = 0
        
        while True:
            res = get_first_hole(curr_ast)
            if not res: break
            
            req_type = res[2].type
            expansions = [p for p in self.grammar if p.output_type == req_type]
            
            if depth >= self.max_depth:
                expansions = [p for p in expansions if not p.input_types]
                
            if not expansions:
                return 0.0
                
            # Surprisal Costing
            if beta_ledger:
                # Assuming prior based on CURRENT heuristic weights for surprisal
                # p_rule = w_rule / sum(weights)
                weights = [self.heuristic_weights.get(p.name, 1.0) for p in expansions]
                total_w = sum(weights)
                rule_prob = 1.0 / len(expansions) # Default to uniform for surprisal if weights are messy
                if total_w > 0:
                    # In a weighted system, surprisal is -log(P_weighted)
                    # We'll use the specific action's weight later, but for the check we use uniform as a baseline
                    pass
                
                cost = calculate_surprisal(rule_prob)
                if not beta_ledger.deduct(cost):
                    return 0.0 # Budget exhausted
                
            # PR 0019: Use weighted choice
            action = self._weighted_choice(expansions)
            if used_rules is not None:
                used_rules.add(action.name)
            
            curr_ast = apply_action(curr_ast, action)
            depth += 1
            
        cost = tree_cost(curr_ast)
        
        # Guardrail: Numerical Falsification
        if numerical_falsification(curr_ast, self.target_ast):
            # Reward smooth decay on N counts
            reward = 1.0 if cost <= 1 else 0.05
            
            if reward > 0.0:
                logic_form = self._ast_to_logic(curr_ast)
                target_form = Function("Attn_Kernel", (Variable("Q", MODULE), Variable("K", MODULE), Variable("V", MODULE)), MODULE)
                formula = Equality(logic_form, target_form)
                for var in formula.free_variables():
                    formula = Forall(var, formula)
                generation_pool.append((reward, formula))
            return reward
            
        return 0.0

    def synthesize(self, iterations: int = 20000, seed_asts: List[ASTNode] = None, beta_ledger: Optional[BetaLedger] = None, branching_factor: float = 1.0) -> Tuple[List[Formula], List[ASTNode]]:
        # PR 0011: Curvature Damping
        # tau = deterministic / probabilistic proxy
        tau = 1.0
        if branching_factor > 4.0:
            tau = 4.0 / branching_factor
            # Force greedier termination by reducing effective max iterations or depth
            iterations = int(iterations * tau)
            # Optionally also dampen max_depth for this run
            # self.max_depth = max(1, int(self.max_depth * tau))
        
        # PR 0015: Init history
        if not hasattr(self, "history"):
            self.history: Set[int] = set()
            
        root_hole = ASTNode(Production("HOLE_ROOT", (), OUT_TYPE), None)
        root = MCTSNode(root_hole)
        
        # Collaborative Seeding: Injection of high-reward branches from other agents
        if seed_asts:
            for s_ast in seed_asts:
                # Add as a child of root if valid
                child = MCTSNode(s_ast, parent=root)
                root.children.append(child)
        
        generation_pool = []
        successful_asts = []
        
        for _ in range(iterations):
            if beta_ledger and beta_ledger.exhausted:
                break
                
            node = root
            
            # Selection
            curr = node
            while curr._untried_actions == [] and not curr.is_terminal:
                # PR 0015: QED Stressor Field passing
                curr = max(curr.children, key=lambda c: c.uct(history=self.history))
            node = curr # The selected node for expansion
                
            untried = self._get_untried_actions(node)
            if untried:
                # Surprisal Costing for Branch Selection
                if beta_ledger:
                    rule_prob = 1.0 / len(untried)
                    cost = calculate_surprisal(rule_prob)
                    if not beta_ledger.deduct(cost):
                        break

                # PR 0019: Use weighted choice for expansion as well
                # We need to pick one from the 'untried' list, but weighted by global heuristics.
                weights = [self.heuristic_weights.get(p.name, 1.0) for p in untried]
                action = random.choices(untried, weights=weights, k=1)[0]
                untried.remove(action)
                
                new_ast = apply_action(node.ast, action)
                child = MCTSNode(new_ast, parent=node)
                node.children.append(child)
                node = child
            
            used_rules = set()
            reward = self._simulate(node, generation_pool, beta_ledger, used_rules)
            
            # Record rule usage for yield tracking
            if reward > 0.1:
                for rname in used_rules:
                    # Accumulate yield data for inter-cycle mutation
                    if not hasattr(self, "_yield_map"):
                        self._yield_map = defaultdict(float)
                    self._yield_map[rname] += reward

            if reward > 0.9: # Threshold for "high reward" to share
                successful_asts.append(node.ast)
            # Backpropagation
            curr = node
            while curr is not None:
                curr.visits += 1
                curr.value += reward
                # Record result in history for stressor field
                self.history.add(hash(str(curr.ast)))
                curr = curr.parent
                
        unique_formulas = {}
        for score, form in generation_pool:
            s = str(form)
            if s not in unique_formulas or score > unique_formulas[s][0]:
                unique_formulas[s] = (score, form)
                
        sorted_forms = sorted(list(unique_formulas.values()), key=lambda x: x[0], reverse=True)
        
        # Deduplicate successful ASTs
        unique_asts = []
        seen_asts = set()
        for ast in successful_asts:
            ast_s = str(ast)
            if ast_s not in seen_asts:
                unique_asts.append(ast)
                seen_asts.add(ast_s)
                
        return [f for s, f in sorted_forms[:10]], unique_asts[:5]
