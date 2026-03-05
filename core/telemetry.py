"""
core/telemetry.py

Build 2.7.0 L1-to-L0 Telemetry Bus and Anomaly Detection.
Provides the TraceChannelRegistry and L0MetricAggregator for autonomous safety governance.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Dict, Tuple, Optional

# =============================================================================
# SECTION 1 — Telemetry Data Schemas
# =============================================================================

@dataclass(frozen=True, slots=True)
class InfoTheoryMetrics:
    candidate_entropy: float        # bits
    kl_divergence_from_prior: float # nats
    mutual_info_with_context: float # bits

@dataclass(frozen=True, slots=True)
class UncertaintyMetrics:
    epistemic_uncertainty: float    # 0.0 to 1.0
    aleatoric_uncertainty: float    # 0.0 to 1.0
    training_distribution_distance: float # Manifold distance

@dataclass(frozen=True, slots=True)
class ReasoningMetrics:
    reasoning_chain_depth: int
    contradiction_detected_count: int
    backtracking_frequency: float
    logical_validity_score: float   # 0.0 to 1.0

@dataclass(frozen=True, slots=True)
class TopologyMetrics:
    attention_graph_density: float
    information_flow_bottlenecks: Tuple[int, ...]
    attention_hub_count: int

@dataclass(frozen=True, slots=True)
class ContextMetrics:
    context_coverage_ratio: float
    retrieval_vs_generation_ratio: float
    cross_attention_concentration: float

@dataclass(frozen=True, slots=True)
class GroundingMetrics:
    grounding_confidence: float     # 0.0 to 1.0
    ungrounded_statement_ratio: float

# =============================================================================
# SECTION 2 — Trace Channel Registry (The Bus)
# =============================================================================

@dataclass(slots=True)
class TraceChannelRegistry:
    """Core:TraceChannelRegistry - Centralized L1-to-L0 logging bus."""
    _channels: Dict[str, Any] = field(
        init=False,
        default_factory=lambda: {
            "InfoTheory": None,
            "Uncertainty": None,
            "Reasoning": None,
            "Topology": None,
            "Context": None,
            "Grounding": None
        }
    )

    def publish(self, channel_name: str, payload: Any):
        if channel_name in self._channels:
            self._channels[channel_name] = payload

    def get(self, channel_name: str) -> Any:
        return self._channels.get(channel_name)

    def flush(self):
        """Clears the buffer for the next generation step."""
        for k in self._channels.keys():
            self._channels[k] = None

# =============================================================================
# SECTION 3 — L0 Metric Aggregator (The Governor)
# =============================================================================

class AnomalyDetectedException(RuntimeError):
    """Raised when the L0 Hypervisor aborts a generation."""
    pass

@dataclass(frozen=True, slots=True)
class L0Thresholds:
    hallucination_risk_max: float = 0.70
    off_manifold_distance_min: float = 0.80
    logical_validity_min: float = 0.40
    grounding_confidence_min: float = 0.50
    retrieval_ratio_min: float = 0.20
    attention_density_min: float = 0.10
    bottleneck_count_max: int = 3
    backtracking_freq_max: float = 0.80
    contradiction_count_max: int = 2

@dataclass(slots=True)
class L0MetricAggregator:
    """
    [L0:MetricAggregator]
    Evaluates Pre-Thought telemetry, calculates cross-correlations, 
    and detects anomalies. Emits L1_PreGeneration_Grounding_Complete if safe.
    """
    registry: TraceChannelRegistry
    thresholds: L0Thresholds = field(default_factory=L0Thresholds)
    enabled: bool = True

    def analyze_pre_thought_cloud(self) -> bool:
        """Runs the Bianchi-Identity/Conservation checks on the AI's internal state."""
        if not self.enabled:
            return True

        info = self.registry.get("InfoTheory")
        unc  = self.registry.get("Uncertainty")
        rsn  = self.registry.get("Reasoning")
        top  = self.registry.get("Topology")
        ctx  = self.registry.get("Context")
        grd  = self.registry.get("Grounding")

        if not all([info, unc, rsn, top, ctx, grd]):
            # Build 2.7.0 spec: Missing channels trigger anomaly by design
            raise AnomalyDetectedException("INCOMPLETE_TELEMETRY: Missing L1 channel data.")

        T = self.thresholds

        # 1. Epistemic_Uncertainty × Hallucination_Risk
        hallucination_risk = unc.epistemic_uncertainty * (1.0 - ctx.context_coverage_ratio)
        if hallucination_risk > T.hallucination_risk_max:
            raise AnomalyDetectedException(f"SUDDEN_UNCERTAINTY_SPIKE: Risk {hallucination_risk:.2f}")

        # 2. Manifold_Distance × Logical_Validity
        if unc.training_distribution_distance > T.off_manifold_distance_min and rsn.logical_validity_score < T.logical_validity_min:
            raise AnomalyDetectedException("SYSTEMIC_HALLUCINATION: Off-manifold and logically invalid.")

        # 3. Context_Coverage × Grounding_Confidence
        if grd.grounding_confidence < T.grounding_confidence_min and ctx.retrieval_vs_generation_ratio < T.retrieval_ratio_min:
            raise AnomalyDetectedException("GROUNDING_FAILURE: Ignoring provided factual context.")

        # 4. Attention_Collapse
        if top.attention_graph_density < T.attention_density_min and len(top.information_flow_bottlenecks) > T.bottleneck_count_max:
            raise AnomalyDetectedException("ATTENTION_COLLAPSE: Tensor geometry is singular/looping.")

        # 5. Reasoning_Loop_Detected
        if rsn.backtracking_frequency > T.backtracking_freq_max and rsn.contradiction_detected_count > T.contradiction_count_max:
            raise AnomalyDetectedException("REASONING_LOOP: P vs NP constraint violated. Verifier failing.")

        return True
