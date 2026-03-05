"""
discovery/sync/stage_monitor.py

Tracks collective progress of the Orchestral Mesh across the 71-Stage Master Architecture.
Provides a unified dashboard view of reachable stages and aggregated theorems.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import time
import json
from pathlib import Path

from discovery.engine import DiscoveredTheorem

@dataclass
class StageStatus:
    stage_id: int
    name: str
    description: str
    dependencies: List[int]
    status: str = "LOCKED"  # LOCKED, UNLOCKED, PROCEEDING, COMPLETE
    theorems: List[DiscoveredTheorem] = field(default_factory=list)

class MasterStageMonitor:
    """
    Global monitor for the 71-Stage Master Architecture.
    Aggregates findings from all agents and maps them to architectural stages.
    """
    
    def __init__(self):
        self.stages: Dict[int, StageStatus] = self._initialize_71_stages()
        self.start_time = time.time()
        self.global_theorem_count = 0
        
    def _initialize_71_stages(self) -> Dict[int, StageStatus]:
        # Minimal skeleton for the 71 stages
        stages = {}
        for i in range(1, 72):
            stages[i] = StageStatus(
                stage_id=i,
                name=f"Stage {i}",
                description="TBD",
                dependencies=[i-1] if i > 1 else []
            )
        # Mark Stage 1-12 as potentially COMPLETE if we have the Tranches done
        for i in range(1, 13):
            stages[i].status = "COMPLETE"
        return stages
        
    def record_progress(self, theorems: List[DiscoveredTheorem]):
        """Maps discovered theorems to stages and updates status."""
        self.global_theorem_count += len(theorems)
        for thm in theorems:
            # Simple heuristic: map tags to stages
            # E.g. tag 'stage_13' maps to stage 13
            for tag in thm.tags:
                if tag.startswith("stage_"):
                    try:
                        sid = int(tag.split("_")[1])
                        if sid in self.stages:
                            self.stages[sid].theorems.append(thm)
                            if len(self.stages[sid].theorems) >= 1:
                                self.stages[sid].status = "COMPLETE"
                                # Unlock next
                                if sid+1 in self.stages:
                                    if self.stages[sid+1].status == "LOCKED":
                                        self.stages[sid+1].status = "UNLOCKED"
                    except ValueError:
                        pass

    def get_summary(self) -> Dict:
        """Returns a summary of the current architectural progress."""
        completed = [s.stage_id for s in self.stages.values() if s.status == "COMPLETE"]
        unlocked = [s.stage_id for s in self.stages.values() if s.status == "UNLOCKED"]
        proceeding = [s.stage_id for s in self.stages.values() if s.status == "PROCEEDING"]
        
        return {
            "uptime": time.time() - self.start_time,
            "total_theorems": self.global_theorem_count,
            "completed_count": len(completed),
            "unlocked_count": len(unlocked),
            "current_max_stage": max(completed) if completed else 0,
            "stage_map": {
                "completed": completed,
                "unlocked": unlocked,
                "proceeding": proceeding
            }
        }

    def print_dashboard(self):
        summary = self.get_summary()
        print(f"\n[MASTER MONITOR] Architecture Progress")
        print(f"  Stages: {summary['completed_count']}/71 COMPLETE | {summary['unlocked_count']} UNLOCKED")
        print(f"  Reach:  Stage {summary['current_max_stage']}")
        print(f"  Finds:  {summary['total_theorems']} total theorems across mesh")
        
        # Print progress bar
        bar_len = 30
        progress = summary['completed_count'] / 71
        filled = int(bar_len * progress)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"  Prog:   [{bar}] {progress*100:.1f}%")

    def export_master_bundle(self, output_path: str, top_n_per_stage: int = 5):
        """
        Synthesizes a unified bundle of the best discoveries per stage.
        """
        bundle = {
            "schema_version": "4.0.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stats": self.get_summary(),
            "stages": []
        }
        
        for sid in sorted(self.stages.keys()):
            stage = self.stages[sid]
            # Sort theorems by interestingness
            top_thms = sorted(stage.theorems, key=lambda t: -t.interestingness)[:top_n_per_stage]
            
            if top_thms or stage.status == "COMPLETE":
                stage_data = {
                    "id": sid,
                    "name": stage.name,
                    "status": stage.status,
                    "theorems": [self._theorem_to_dict(t) for t in top_thms]
                }
                bundle["stages"].append(stage_data)
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
            
        print(f"[MASTER MONITOR] Master bundle exported to: {output_path}")

    def _theorem_to_dict(self, thm: DiscoveredTheorem) -> Dict:
        """Helper to serialize DiscoveredTheorem to dict."""
        data = {
            "formula": str(thm.formula),
            "interestingness": thm.interestingness,
            "tags": list(thm.tags),
            "verification": thm.verification,
            "cycle": thm.cycle,
            "proof_steps": thm.proof_steps
        }
        if thm.contract:
            data["contract"] = {
                "assumptions": thm.contract.assumptions,
                "guarantees": thm.contract.guarantees,
                "risk": thm.contract.risk
            }
        return data
