import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from discovery.orchestral_mesh import OperandicMesh, MeshConfig
from discovery.governed_engine import DiscoveredTheorem
import core.logic as cl

def test_mesh_sync():
    config = MeshConfig(num_agents=2, max_cycles=0)
    mesh = OperandicMesh(config)
    
    # Simulate a discovery by Agent 0
    m1 = cl.Variable("M1", cl.MODULE)
    m2 = cl.Variable("M2", cl.MODULE)
    risk_seq = cl.Function("Risk", (cl.Function("Seq", (m1, m2), cl.MODULE),), cl.REAL)
    risk_sum = cl.Function("add", (cl.Function("Risk", (m1,), cl.REAL), cl.Function("Risk", (m2,), cl.REAL)), cl.REAL)
    formula = cl.Forall(m1, cl.Forall(m2, cl.Equality(risk_seq, risk_sum)))
    
    thm = DiscoveredTheorem(
        formula=formula,
        interestingness=0.99,
        tags={"algebra"},
        verification="PROVED",
        cycle=1
    )
    
    # Inject into Agent 0's session (simulating successful cycle)
    from discovery.governed_engine import DiscoverySession
    session0 = DiscoverySession()
    session0.theorems.append(thm)
    session0.stats = {"final_risk": 0.05}
    mesh.sessions = [session0, DiscoverySession()]
    mesh.sessions[1].stats = {"final_risk": 0.0}
    
    print("Running knowledge sync...")
    mesh.sync_knowledge()
    
    # Verify Agent 1 now knows this theorem
    agent1 = mesh.agents[1]
    assert str(formula) in agent1._proven_strs
    print("SUCCESS: Agent 1 synchronized knowledge from Agent 0.")
    
    # Verify Agent 1's e-graph reflects the congruence
    from discovery.normalization import logic_to_egraph_term
    et_risk_seq = logic_to_egraph_term(risk_seq)
    et_risk_sum = logic_to_egraph_term(risk_sum)
    
    c1 = agent1.egraph.add(et_risk_seq)
    c2 = agent1.egraph.add(et_risk_sum)
    
    assert agent1.egraph.find(c1) == agent1.egraph.find(c2)
    print("SUCCESS: Agent 1 e-graph synchronized congruence from Agent 0.")

if __name__ == "__main__":
    test_mesh_sync()
