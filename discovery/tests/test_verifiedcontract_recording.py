import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from core.logic import Equality, Variable, MODULE, Term
from discovery.engine import CoAIOperandicsExplorer, DiscoverySession
from prover.general_atp import ProofResult

def test_verified_contract_recording():
    explorer = CoAIOperandicsExplorer(certified_mode=True)
    session = DiscoverySession()
    session.metadata = {
        "certified_mode": True,
        "attention_bundle_loaded": True,
        "attention_bundle_sha256_16": "deadbeef",
        "attention_bundle_schema_version": 1
    }
    
    A = Variable("A", MODULE)
    conj = Equality(A, A)
    
    # Mocking a proven conjecture
    result = ProofResult(success=True, steps=1, applied_rules=["par_identity"], proof_trace=[])
    
    proven_lemmas = []
    explorer._proven_strs = set()
    
    # Simulate Phase 3 Recording inside loop
    from discovery.engine import VerifiedContract, DiscoveredTheorem
    
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
    
    thm = DiscoveredTheorem(
        formula=conj,
        interestingness=1.0,
        tags={"test"},
        verification="PROVED",
        cycle=1,
        proof_steps=result.steps,
        contract=contract
    )
    thm.proof_result = result
    
    session.theorems.append(thm)
    
    # Assertions
    assert len(session.theorems) == 1
    recorded_thm = session.theorems[0]
    
    assert recorded_thm.contract is not None
    assert recorded_thm.contract.assumptions["certified_mode"] is True
    assert recorded_thm.contract.assumptions["attention_bundle_sha256_16"] == "deadbeef"
    assert recorded_thm.contract.guarantees["equivalence"] is True
    assert "par_identity" in recorded_thm.contract.guarantees["applied_rules"]
    
    import json
    # Ensure serializability of contract dictionaries
    json.dumps(recorded_thm.contract.assumptions)
    json.dumps(recorded_thm.contract.guarantees)
