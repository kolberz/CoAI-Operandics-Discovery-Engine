import pytest
import math
from grounding.intervals import Interval, ModuleMeasurement, IntervalPropagator, iv_min, iv_max
from grounding.dimensions import DIMENSIONLESS, ENERGY, BITS

class TestIntervals:
    def test_creation_and_basic_props(self):
        i1 = Interval(1.0, 2.0, DIMENSIONLESS)
        assert i1.lo == 1.0
        assert i1.hi == 2.0
        assert i1.width() == 1.0
        assert i1.midpoint() == 1.5
        
        # Test swap
        i2 = Interval(2.0, 1.0)
        assert i2.lo == 1.0
        assert i2.hi == 2.0

    def test_arithmetic(self):
        a = Interval(1, 2)
        b = Interval(3, 4)
        
        # Add: [1+3, 2+4] = [4, 6]
        c = a + b
        assert c.lo == 4 and c.hi == 6
        
        # Sub: [1-4, 2-3] = [-3, -1]
        d = a - b
        assert d.lo == -3 and d.hi == -1
        
        # Scale
        e = a.scale(2.0)
        assert e.lo == 2.0 and e.hi == 4.0
        
        # Mul: [1,2]*[-1,1] => min(-1, 2), max(-1, 2) => [-1, 2]? 
        # 1*-1=-1, 1*1=1, 2*-1=-2, 2*1=2 -> [-2, 2]
        f = Interval(1, 2) * Interval(-1, 1)
        assert f.lo == -2 and f.hi == 2

    def test_validation_logic(self):
        # NOTE: This test anticipates the new `validate()` method
        # Valid measurement
        m = ModuleMeasurement(
            name="Test",
            risk=Interval(0.0, 0.1),
            cost=Interval(1e-9, 2e-9, ENERGY),
            security=Interval(100, 110, BITS),
            complexity=Interval(500, 510, BITS)
        )
        # assert m.validate() is True (to be implemented)
        
        # Invalid risk
        m_bad_risk = ModuleMeasurement(
            name="BadRisk",
            risk=Interval(-0.1, 0.5), # Negative risk
            cost=Interval(0, 0, ENERGY),
            security=Interval(0, 0, BITS),
            complexity=Interval(0, 0, BITS)
        )
        # assert m_bad_risk.validate() is False

class TestPropagation:
    def setup_method(self):
        self.prop = IntervalPropagator()
        self.m1 = ModuleMeasurement(
            "M1", Interval(0.1, 0.2), Interval(10, 20, ENERGY), 
            Interval(50, 60, BITS), Interval(100, 200, BITS)
        )
        self.m2 = ModuleMeasurement(
            "M2", Interval(0.2, 0.3), Interval(5, 15, ENERGY), 
            Interval(60, 70, BITS), Interval(100, 200, BITS)
        )

    def test_seq(self):
        res = self.prop.seq(self.m1, self.m2)
        # Risk adds: [0.3, 0.5]
        assert pytest.approx(res.risk.lo) == 0.3
        assert pytest.approx(res.risk.hi) == 0.5
        # Cost adds: [15, 35]
        assert pytest.approx(res.cost.lo) == 15
        
    def test_par_independent(self):
        # dep=0 -> risk multiplies
        res = self.prop.par(self.m1, self.m2, dep=0.0)
        # [0.1*0.2, 0.2*0.3] = [0.02, 0.06]
        assert pytest.approx(res.risk.lo) == 0.02
        assert pytest.approx(res.risk.hi) == 0.06

    def test_quad_goal(self):
        # Case 1: Risk high -> Pass unconditionally
        m_high_risk = ModuleMeasurement(
            "HighRisk", Interval(0.5, 0.6), Interval(100, 200, ENERGY),
            Interval(0, 0, BITS), Interval(1, 2, BITS)
        )
        res = self.prop.validate_quad_goal(m_high_risk, landauer_factor=1.0)
        assert res["quad_goal_holds"] is True
        
        # Case 2: Risk low, Cost <= Comp -> Pass
        # Comp=100 bits -> energy=100 (factor=1.0)
        # Cost=50..60 -> <= 100 -> Pass
        m_good = ModuleMeasurement(
            "Good", Interval(0.0, 0.001), Interval(50, 60, ENERGY),
            Interval(10, 10, BITS), Interval(100, 100, BITS)
        )
        res = self.prop.validate_quad_goal(m_good, landauer_factor=1.0)
        assert res["quad_goal_holds"] is True
        
        # Case 3: Risk low, Cost > Comp -> Fail
        # Comp=10 bits -> 10 energy
        # Cost=20..30 -> > 10 -> Fail
        m_bad = ModuleMeasurement(
            "Bad", Interval(0.0, 0.001), Interval(20, 30, ENERGY),
            Interval(0, 0, BITS), Interval(10, 10, BITS)
        )
        res = self.prop.validate_quad_goal(m_bad, landauer_factor=1.0)
        assert res["quad_goal_holds"] is False
