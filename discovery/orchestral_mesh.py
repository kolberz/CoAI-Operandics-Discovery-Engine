"""
discovery/orchestral_mesh.py

Multi-agent coordination layer for the CoAI Operandics Discovery Engine.
Manages a mesh of explorers, synchronizing knowledge and coordinating search.
"""

from __future__ import annotations
import multiprocessing as mp
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Type
import logging

from discovery.governed_engine import GovernedOperandicsExplorer, DiscoverySession
from discovery.engine import DiscoveredTheorem
from discovery.sync.egraph_ledger import EGraphLedger, SyncUpdate
from discovery.sync.stage_monitor import MasterStageMonitor

# Configure logging for the mesh
logging.basicConfig(level=logging.INFO, format="[MESH] %(message)s")
logger = logging.getLogger("orchestral.mesh")

@dataclass
class MeshConfig:
    num_agents: int = 4
    sync_interval_cycles: int = 5
    risk_budget_per_agent: float = 1.0
    max_cycles: int = 10

class OperandicMesh:
    """
    Orchestrates multiple GovernedOperandicsExplorer instances.
    Provides a shared context for distributed discovery.
    """
    
    def __init__(self, config: MeshConfig = MeshConfig()):
        self.config = config
        self.agents: List[GovernedOperandicsExplorer] = []
        self.sessions: List[DiscoverySession] = []
        self.ledger = EGraphLedger()
        self.monitor = MasterStageMonitor()
        
        # Initialize agents
        for i in range(config.num_agents):
            agent = GovernedOperandicsExplorer(
                risk_budget=config.risk_budget_per_agent
            )
            agent.agent_id = i
            self.agents.append(agent)
            
    def add_agent(self):
        """Adds a new agent to the mesh dynamically."""
        new_id = len(self.agents)
        agent = GovernedOperandicsExplorer(
            risk_budget=self.config.risk_budget_per_agent
        )
        agent.agent_id = new_id
        self.agents.append(agent)
        logger.info(f"Dynamically added Agent {new_id} to the mesh.")

    def run_collaborative_discovery(self, cycles: int = None):
        """
        Runs discovery across all agents in the mesh for a set number of cycles.
        """
        run_cycles = cycles or self.config.max_cycles
        logger.info(f"Starting collaborative discovery for {run_cycles} cycles with {len(self.agents)} agents.")
        
        for c in range(run_cycles):
            logger.info(f"--- Global Cycle {c+1}/{run_cycles} ---")
            cycle_sessions = []
            for i, agent in enumerate(self.agents):
                # Each 'agent' cycle here is 1 internal discovery cycle
                session = agent.governed_discovery_cycle(
                    max_cycles=1,
                    verbose=False
                )
                cycle_sessions.append(session)
                self.sessions.append(session)
            
            # 2. Synchronize findings after each global cycle
            self.sync_knowledge()

    def run_until_reach(self, target_stage: int, max_global_cycles: int = 50):
        """
        Discovery Marathon: Runs the mesh until a specific architectural stage is reached.
        """
        logger.info(f"MARATHON START: Targeting Stage {target_stage}")
        
        for c in range(max_global_cycles):
            summary = self.monitor.get_summary()
            current_max = summary["current_max_stage"]
            
            if current_max >= target_stage:
                logger.info(f"MARATHON SUCCESS: Target Stage {target_stage} reached at global cycle {c}.")
                break
                
            logger.info(f"Cycle {c}: Current reach is Stage {current_max}. Progressing...")
            
            # Dynamic scaling: if no progress in 5 cycles, add an agent
            if c > 0 and c % 10 == 0 and current_max < target_stage:
                self.add_agent()

            # Run 1 global cycle across all current agents
            for i, agent in enumerate(self.agents):
                session = agent.governed_discovery_cycle(max_cycles=1, verbose=False)
                self.sessions.append(session)
            
            self.sync_knowledge()
            
        else:
            logger.warning(f"MARATHON TIMEOUT: Failed to reach Stage {target_stage} within {max_global_cycles} cycles.")
        
    def sync_knowledge(self):
        """
        Synchronizes all findings through the shared E-Graph ledger.
        """
        from discovery.normalization import logic_to_egraph_term
        
        logger.info("Starting LEDGER-based synchronization...")
        
        # 1. Capture discoveries from all agents and update ledger
        for i, session in enumerate(self.sessions):
            update = SyncUpdate(agent_id=i)
            for thm in session.theorems:
                # Strip quantifiers to get to the equality
                formula = thm.formula
                while hasattr(formula, 'body'):
                    formula = formula.body
                
                if hasattr(formula, 'left') and hasattr(formula, 'right'):
                    # Add proven equality to ledger unions
                    et_lhs = logic_to_egraph_term(formula.left)
                    et_rhs = logic_to_egraph_term(formula.right)
                    update.unions.append((et_lhs, et_rhs))
            self.ledger.record_update(update)
            
        # 2. Synchronize all agents with the global ledger
        global_asts = []
        for session in self.sessions:
            global_asts.extend(session.mcts_asts)
            
        # Deduplicate ASTs
        unique_asts = []
        seen_ast_strs = set()
        for ast in global_asts:
            s_ast = str(ast)
            if s_ast not in seen_ast_strs:
                unique_asts.append(ast)
                seen_ast_strs.add(s_ast)
        top_seeds = unique_asts[:10]

        for agent in self.agents:
            self.ledger.sync_agent(agent.egraph, [])
            # Also update formula-string cache for high-level deduplication
            for session in self.sessions:
                for thm in session.theorems:
                    agent._proven_strs.add(str(thm.formula))
                    if thm.formula not in agent.lemmas:
                        agent.lemmas.append(thm.formula)
            # Inject top seeds for next cycle (Collaborative MCTS)
            agent.incoming_asts = top_seeds
                        
        # 3. Update Master Stage Monitor (PR 0012)
        for session in self.sessions:
            self.monitor.record_progress(session.theorems)

        logger.info(f"Sync complete. Unified mesh with {len(top_seeds)} MCTS seeds.")
        self.monitor.print_dashboard()

    def report(self):
        """Aggregate report for the entire mesh."""
        print(f"\n{'='*60}")
        print(f"  ORCHESTRAL MESH REPORT (Agents: {len(self.agents)})")
        print(f"{'='*60}")
        
        self.monitor.print_dashboard()
        
        total_thms = sum(len(s.theorems) for s in self.sessions)
        avg_risk = sum(s.stats.get('final_risk', 0) for s in self.sessions) / max(1, len(self.sessions))
        
        print(f"\n  Total Discoveries:       {total_thms}")
        print(f"  Average Risk:            {avg_risk:.4f}")
        
        print(f"\n  Global Top Discoveries (Across Mesh):")
        # Flatten all theorems and sort
        all_thms = []
        for s in self.sessions:
            all_thms.extend(s.theorems)
        all_thms.sort(key=lambda t: -t.interestingness)
        
        for i, thm in enumerate(all_thms[:15], 1):
            print(f"    {i}. {thm}")

if __name__ == "__main__":
    config = MeshConfig(num_agents=2, max_cycles=5)
    mesh = OperandicMesh(config)
    mesh.run_collaborative_discovery()
    mesh.report()
