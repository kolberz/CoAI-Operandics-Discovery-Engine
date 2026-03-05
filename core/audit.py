"""
core/audit.py

MetaShield & The Sidecar Ledger.
Provides cryptographic provenance and integrity tracking for the discovery engine.
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class AuditEntry:
    formula_str: str
    provenance: str
    beta_cost: float
    timestamp: float
    parent_hashes: List[str]
    entry_hash: str

class MetaShieldLedger:
    """
    Sidecar ledger that maintains a verifiable chain of discovery events.
    """
    def __init__(self):
        self.entries: List[AuditEntry] = []
        self._current_chain_hash: str = "0" * 64

    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        # Canonical JSON for consistent hashing
        dump = json.dumps(data, sort_keys=True)
        return hashlib.sha256(dump.encode('utf-8')).hexdigest()

    def record_discovery(self, formula: Any, provenance: str, beta_cost: float, parent_hashes: Optional[List[str]] = None) -> str:
        """
        Records a discovery event and returns its integrity hash.
        """
        if parent_hashes is None:
            parent_hashes = [self._current_chain_hash]
            
        data = {
            "formula": str(formula),
            "provenance": provenance,
            "beta_cost": beta_cost,
            "timestamp": time.time(),
            "parent_hashes": parent_hashes
        }
        
        entry_hash = self._calculate_hash(data)
        
        entry = AuditEntry(
            formula_str=data["formula"],
            provenance=data["provenance"],
            beta_cost=data["beta_cost"],
            timestamp=data["timestamp"],
            parent_hashes=data["parent_hashes"],
            entry_hash=entry_hash
        )
        
        self.entries.append(entry)
        self._current_chain_hash = entry_hash
        return entry_hash

    def verify_integrity(self) -> bool:
        """
        Verifies that no entries have been tampered with.
        Useful for out-of-band audit verification.
        """
        for entry in self.entries:
            data = {
                "formula": entry.formula_str,
                "provenance": entry.provenance,
                "beta_cost": entry.beta_cost,
                "timestamp": entry.timestamp,
                "parent_hashes": entry.parent_hashes
            }
            if self._calculate_hash(data) != entry.entry_hash:
                return False
        return True

    def export_ledger(self) -> str:
        """Returns a JSON string of the entire audit trail."""
        return json.dumps([asdict(e) for e in self.entries], indent=2)
