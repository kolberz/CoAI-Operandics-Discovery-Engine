"""
discovery/liveness.py

Büchi Automata Liveness Enforcement.
Ensures formal progress and termination of discovery loops.
"""

from enum import Enum, auto
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

class DiscoveryState(Enum):
    INIT = auto()
    RESEARCHING = auto()
    CONJECTURING = auto()
    PROVING = auto()
    PROGRESS_MADE = auto()
    TERMINATED = auto()

class BuchiMonitor:
    """
    Monitors the discovery state machine as a Büchi automaton.
    Verifies that 'Progress' or 'Exhaustion' is infinitely often reached (Liveness).
    In our finite loop, this means ensuring we don't stall in RESEARCHING/CONJECTURING.
    """
    def __init__(self, marathon_mode: bool = False):
        self.state_history: List[DiscoveryState] = [DiscoveryState.INIT]
        self.progress_count = 0
        self.cycle_count = 0
        self.stalled_cycles = 0
        self.marathon_mode = marathon_mode
        self.max_stall = 50 if marathon_mode else 5 # Generous threshold for marathon

    def observe_state(self, state: DiscoveryState, additional_info: Optional[Dict[str, Any]] = None):
        """Transition the automaton and verify liveness properties."""
        self.state_history.append(state)
        
        if state == DiscoveryState.PROGRESS_MADE:
            self.progress_count += 1
            self.stalled_cycles = 0
        elif state in (DiscoveryState.RESEARCHING, DiscoveryState.CONJECTURING):
            self.stalled_cycles += 1
            
        self.cycle_count += 1
        
        # Liveness check: Progress must be made within 'max_stall' cycles
        if self.stalled_cycles > self.max_stall:
            raise RuntimeError(
                f"LIVENESS_VIOLATION: Discovery stalled for {self.stalled_cycles} cycles. "
                "Architectural adherence failed (possible infinite loop)."
            )

    def heartbeat(self, stats: Dict[str, Any]):
        """Analyze engine stats to determine if progress was made."""
        new_nodes = stats.get("new_enodes", 0)
        new_theorems = stats.get("new_theorems", 0)
        
        if new_nodes > 0 or new_theorems > 0:
            self.observe_state(DiscoveryState.PROGRESS_MADE)
        else:
            # We assume it's researching/conjecturing if no actual results yet
            self.observe_state(DiscoveryState.CONJECTURING)

    @property
    def liveness_proved(self) -> bool:
        """Returns True if progress has been made or the cycle correctly terminated."""
        return self.progress_count > 0 or self.state_history[-1] == DiscoveryState.TERMINATED
