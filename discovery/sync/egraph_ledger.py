"""
discovery/sync/egraph_ledger.py

Global E-Graph synchronization layer for the CoAI Operandics Orchestral Mesh.
Maintains a canonical union-find state for all proved identities in the mesh.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
import logging

from discovery.normalization import RiskEGraph, ETerm, ERewrite

logger = logging.getLogger("orchestral.sync")

@dataclass
class SyncUpdate:
    """A batch of unions and rewrites to be applied to the global state."""
    unions: List[Tuple[ETerm, ETerm]] = field(default_factory=list)
    rewrites: List[ERewrite] = field(default_factory=list)
    agent_id: int = -1

class EGraphLedger:
    """
    Central repository for logical congruence.
    Agents 'check-in' their local discoveries and 'pull' the global context.
    """
    
    def __init__(self):
        self.global_egraph = RiskEGraph()
        self.global_rewrites: List[ERewrite] = []
        self._seen_rewrites: Set[str] = set()
        
    def record_update(self, update: SyncUpdate):
        """Merges an agent's discoveries into the global ledger."""
        logger.info(f"Processing update from Agent {update.agent_id} ({len(update.unions)} unions, {len(update.rewrites)} rewrites).")
        
        for lhs, rhs in update.unions:
            id_l = self.global_egraph.add(lhs)
            id_r = self.global_egraph.add(rhs)
            self.global_egraph.union(id_l, id_r)
            
        for rw in update.rewrites:
            if rw.name not in self._seen_rewrites:
                self.global_rewrites.append(rw)
                self._seen_rewrites.add(rw.name)
                
    def get_global_state(self) -> Tuple[RiskEGraph, List[ERewrite]]:
        """Returns the current canonical e-graph state."""
        return self.global_egraph, self.global_rewrites

    def sync_agent(self, agent_egraph: RiskEGraph, agent_rewrites: List[ERewrite]):
        """
        In-place synchronization of an agent's local e-graph with the global ledger.
        This pulls global congruence into the local instance.
        """
        from collections import defaultdict
        
        # 1. Group global terms by their root class in the ledger
        global_classes = defaultdict(list)
        for term, cid in self.global_egraph._term_class.items():
            root = self.global_egraph.find(cid)
            global_classes[root].append(term)
            
        # 2. Re-apply Global Unions to local e-graph
        for root, terms in global_classes.items():
            if len(terms) > 1:
                t0_id = agent_egraph.add(terms[0])
                for tn in terms[1:]:
                    tn_id = agent_egraph.add(tn)
                    agent_egraph.union(t0_id, tn_id)
        
        logger.info("Agent local e-graph synchronized with global ledger.")

# Logic for integrating into OperandicMesh
def patch_mesh_with_ledger(mesh: 'OperandicMesh'):
    """Wires the EGraphLedger into an existing OperandicMesh instance."""
    from discovery.orchestral_mesh import OperandicMesh
    
    mesh.ledger = EGraphLedger()
    
    # Wrap sync_knowledge to use the ledger
    original_sync = mesh.sync_knowledge
    
    def ledged_sync():
        logger.info("Starting LEDGER-based synchronization...")
        for agent in mesh.agents:
            # 1. Capture local state from agent (mocked for now, needs agent introspection)
            # In a real impl, GovernedOperandicsExplorer would track 'new' unions
            pass
            
        # 2. Call original to handle formula strings
        original_sync()
        
        # 3. Distributed E-Graph sync
        for agent in mesh.agents:
            mesh.ledger.sync_agent(agent.egraph, [])
            
    mesh.sync_knowledge = ledged_sync
