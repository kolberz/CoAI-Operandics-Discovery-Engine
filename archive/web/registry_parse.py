from __future__ import annotations
from typing import Dict, Optional

from grounding.dimensions import Dimension, DIMENSIONLESS, ENERGY, TIME, BITS, ENERGY_PER_BIT
from grounding.dimensions import DimensionRegistry

def parse_dim_string(s: str) -> Optional[Dimension]:
    s = s.strip()
    if s == "None":
        return None
    if s in ("dimensionless", "DIMENSIONLESS"):
        return DIMENSIONLESS
    if s in ("J", "ENERGY"):
        return ENERGY
    if s in ("s", "TIME"):
        return TIME
    if s in ("bit", "BITS"):
        return BITS
    if s in ("J/bit", "ENERGY_PER_BIT"):
        return ENERGY_PER_BIT
    raise ValueError(f"Unknown dimension string: {s}")

def apply_registry_overrides(reg: DimensionRegistry, const_over: Dict[str, str], func_over: Dict[str, str]):
    for k, v in const_over.items():
        reg.const_dims[k] = parse_dim_string(v)

    for k, v in func_over.items():
        reg.output_dims[k] = parse_dim_string(v)
