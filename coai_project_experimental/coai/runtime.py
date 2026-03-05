"""
coai/runtime.py  (v3.1.1)

Operational L1 layer. All composition and risk logic delegates to interface.py.
"""
try:
    from .interface import (
        PhysInterval,
        Contract,
        CompositionResult,
        RiskProfile,
        ValueParams,
        SMTCompatibilityChecker,
        CompatibilityVerdict,
        compute_value_objective_interval,
        DIM_DIMENSIONLESS,
        Dimension,
    )
except ImportError:
    from interface import (
        PhysInterval, Contract, CompositionResult, RiskProfile, ValueParams,
        SMTCompatibilityChecker, CompatibilityVerdict, compute_value_objective_interval,
        DIM_DIMENSIONLESS, Dimension,
    )
import warnings

class VerifiableModule:
    def __init__(
        self,
        name: str,
        contract: Contract,
        cost_j: PhysInterval,
        info_bits: PhysInterval,
    ):
        self.name = name
        self.contract = contract
        self.cost_j = cost_j
        self.info_bits = info_bits
        self._h_compat_status: CompatibilityVerdict = CompatibilityVerdict.UNTRUSTED

    def seq_compose(
        self, other: "VerifiableModule", checker=None
    ) -> "VerifiableModule":
        """
        Sequential composition with exhaustive verdict handling.
        Only PROVEN yields a formally-backed bound.
        """
        verdict = self.contract.check_compatibility(other.contract, checker)

        if verdict == CompatibilityVerdict.REFUTED:
            raise ValueError(
                f"Composition BLOCKED: h_compat violated between "
                f"{self.name} and {other.name}."
            )

        formally_verified = verdict == CompatibilityVerdict.PROVEN

        if not formally_verified:
            warnings.warn(
                f"Composition {self.name} -> {other.name}: "
                f"h_compat status is {verdict.name}. "
                f"The epsilon1+epsilon2 bound is not formally supported.",
                stacklevel=2,
            )

        comp_result = CompositionResult.seq_compose(
            self.contract, other.contract
        )

        composed = VerifiableModule(
            name=f"Seq({self.name}, {other.name})",
            contract=Contract(
                assumption=self.contract.assumption,
                guarantee=other.contract.guarantee,
                epsilon=comp_result.epsilon_bound,
                assumption_smt=self.contract.assumption_smt,
                guarantee_smt=other.contract.guarantee_smt,
            ),
            cost_j=self.cost_j + other.cost_j,
            info_bits=self.info_bits + other.info_bits,
        )
        composed._h_compat_status = verdict
        return composed

if __name__ == "__main__":
    # Recommended execution: python -m coai.runtime
    smt_checker = SMTCompatibilityChecker()
    params = ValueParams(lambda_R=3.0, lambda_C=0.7, lambda_v=100.0)

    # Note the proper SMT-LIB2 prefix syntax: (- 10)
    c1 = Contract(
        assumption=lambda s: True,
        guarantee=lambda s: s > 0,
        epsilon=0.01,
        guarantee_smt="(> s 0)",
    )
    c2 = Contract(
        assumption=lambda s: s > -10,
        guarantee=lambda s: True,
        epsilon=0.02,
        assumption_smt="(> s (- 10))",
    )

    DIM_ENERGY = Dimension(energy=1)
    DIM_INFO = Dimension(info=1)

    m1 = VerifiableModule(
        "Retriever", c1,
        PhysInterval(10, 15, DIM_ENERGY),
        PhysInterval(1e6, 1e6, DIM_INFO),
    )
    m2 = VerifiableModule(
        "Generator", c2,
        PhysInterval(490, 500, DIM_ENERGY),
        PhysInterval(1e7, 1e7, DIM_INFO),
    )

    print(f"\n[L1] Composing {m1.name} -> {m2.name}...")
    pipeline = m1.seq_compose(m2, checker=smt_checker)

    status = (
        "PROVEN"
        if pipeline._h_compat_status == CompatibilityVerdict.PROVEN
        else "UNVERIFIED"
    )
    print(f"  Risk bound (epsilon): {pipeline.contract.epsilon} [{status}]")

    risk_profile = RiskProfile(
        epsilon=pipeline.contract.epsilon, consequence=10000.0
    )
    risk_interval = PhysInterval(
        lo=0.0, hi=risk_profile.expected_risk, dim=DIM_DIMENSIONLESS
    )

    normalized_tco = PhysInterval(
        pipeline.cost_j.lo / 100,
        pipeline.cost_j.hi / 100,
        DIM_DIMENSIONLESS,
    )
    utility_interval = PhysInterval(90.0, 100.0, DIM_DIMENSIONLESS)

    v = compute_value_objective_interval(
        utility_interval, risk_interval, normalized_tco, params
    )
    print(f"  J_robust envelope: [{v.lo:.2f}, {v.hi:.2f}]")
