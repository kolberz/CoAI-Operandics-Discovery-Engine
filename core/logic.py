"""
core/logic.py

Complete logic foundation with all formula types needed
for the CoAI Operandics calculus.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set, FrozenSet, Dict, Any, Iterable
from abc import ABC, abstractmethod
import copy


# ═══════════════════════════════════════════════════
# SORTS
# ═══════════════════════════════════════════════════

@dataclass(frozen=True)
class Sort:
    name: str
    def __repr__(self): return self.name


# Standard sorts used throughout the system
MODULE = Sort("Module")
REAL = Sort("Real")
PROB = Sort("Probability")
PRED = Sort("Predicate")
BOOL = Sort("Bool")


# ═══════════════════════════════════════════════════
# TERMS
# ═══════════════════════════════════════════════════

class Term(ABC):
    """Base class for all terms."""
    @abstractmethod
    def variables(self) -> Set['Variable']:
        pass
    
    @abstractmethod
    def substitute(self, mapping: Dict['Variable', 'Term']) -> 'Term':
        pass
    
    @abstractmethod
    def depth(self) -> int:
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Total number of nodes in term tree."""
        pass
    
    @abstractmethod
    def functions(self) -> Set[str]:
        """All function symbols appearing in this term."""
        pass


@dataclass(frozen=True)
class Variable(Term):
    name: str
    sort: Sort = field(default_factory=lambda: MODULE)
    
    def variables(self) -> Set['Variable']:
        return {self}
    
    def substitute(self, mapping: Dict['Variable', 'Term']) -> 'Term':
        return mapping.get(self, self)
    
    def depth(self) -> int:
        return 0
    
    def size(self) -> int:
        return 1
    
    def functions(self) -> Set[str]:
        return set()
    
    def __repr__(self): return self.name
    def __hash__(self): return hash((self.name, self.sort))
    def __eq__(self, other):
        return isinstance(other, Variable) and self.name == other.name and self.sort == other.sort


@dataclass(frozen=True)
class Constant(Term):
    name: str
    sort: Sort = field(default_factory=lambda: MODULE)
    
    def variables(self) -> Set[Variable]:
        return set()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Term':
        return self
    
    def depth(self) -> int:
        return 0
    
    def size(self) -> int:
        return 1
    
    def functions(self) -> Set[str]:
        return set()
    
    def __repr__(self): return self.name
    def __hash__(self): return hash((self.name, self.sort))
    def __eq__(self, other):
        return isinstance(other, Constant) and self.name == other.name and self.sort == other.sort


@dataclass(frozen=True)
class Function(Term):
    symbol: str
    args: Tuple[Term, ...] = field(default_factory=tuple)
    sort: Sort = field(default_factory=lambda: MODULE)
    
    def __post_init__(self):
        if isinstance(self.args, list):
            object.__setattr__(self, 'args', tuple(self.args))
        validate_application(self.symbol, self.args, self.sort)
    
    def variables(self) -> Set[Variable]:
        result = set()
        for arg in self.args:
            result |= arg.variables()
        return result
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Term':
        new_args = tuple(arg.substitute(mapping) for arg in self.args)
        return Function(self.symbol, new_args, self.sort)
    
    def depth(self) -> int:
        if not self.args:
            return 1
        return 1 + max(arg.depth() for arg in self.args)
    
    def size(self) -> int:
        return 1 + sum(arg.size() for arg in self.args)
    
    def functions(self) -> Set[str]:
        result = {self.symbol}
        for arg in self.args:
            result |= arg.functions()
        return result
    
    def __repr__(self):
        if not self.args:
            return self.symbol
        return f"{self.symbol}({', '.join(map(str, self.args))})"
    
    def __hash__(self):
        return hash((self.symbol, self.args, self.sort))
    
    def __eq__(self, other):
        return (isinstance(other, Function) and 
                self.symbol == other.symbol and 
                self.args == other.args and 
                self.sort == other.sort)


# ═══════════════════════════════════════════════════
# FORMULAS
# ═══════════════════════════════════════════════════

class Formula(ABC):
    """Base class for all formulas."""
    @abstractmethod
    def variables(self) -> Set[Variable]:
        pass
    
    @abstractmethod
    def free_variables(self) -> Set[Variable]:
        pass
    
    @abstractmethod
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        pass
    
    @abstractmethod
    def functions(self) -> Set[str]:
        pass
    
    @abstractmethod
    def depth(self) -> int:
        pass
    
    @abstractmethod
    def size(self) -> int:
        pass

    def negate(self) -> 'Formula':
        return Not(self)


def _term_functions(t: Term) -> Set[str]:
    return t.functions()


@dataclass(frozen=True)
class Atom(Formula):
    predicate: str
    args: Tuple[Term, ...] = field(default_factory=tuple)
    
    def __post_init__(self):
        if isinstance(self.args, list):
            object.__setattr__(self, 'args', tuple(self.args))
    
    def variables(self) -> Set[Variable]:
        result = set()
        for arg in self.args:
            result |= arg.variables()
        return result
    
    def free_variables(self) -> Set[Variable]:
        return self.variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        new_args = tuple(arg.substitute(mapping) for arg in self.args)
        return Atom(self.predicate, new_args)
    
    def functions(self) -> Set[str]:
        result = set()
        for arg in self.args:
            result |= arg.functions()
        return result
    
    def depth(self) -> int:
        if not self.args:
            return 1
        return 1 + max(arg.depth() for arg in self.args)
    
    def size(self) -> int:
        return 1 + sum(arg.size() for arg in self.args)
    
    def __repr__(self):
        if not self.args:
            return self.predicate
        return f"{self.predicate}({', '.join(map(str, self.args))})"
    
    def __hash__(self):
        return hash((self.predicate, self.args))


@dataclass(frozen=True)
class Equality(Formula):
    left: Term
    right: Term
    
    def __post_init__(self):
        if self.left.sort != self.right.sort:
            raise ValueError(
                f"Equality sort mismatch: left({self.left}) has sort {self.left.sort}, "
                f"right({self.right}) has sort {self.right.sort}"
            )
    
    def variables(self) -> Set[Variable]:
        return self.left.variables() | self.right.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        return Equality(self.left.substitute(mapping), self.right.substitute(mapping))
    
    def functions(self) -> Set[str]:
        return self.left.functions() | self.right.functions()
    
    def depth(self) -> int:
        return max(self.left.depth(), self.right.depth())
    
    def size(self) -> int:
        return 1 + self.left.size() + self.right.size()
    
    def __repr__(self):
        return f"{self.left} = {self.right}"
    
    def __hash__(self):
        return hash(("=", self.left, self.right))


@dataclass(frozen=True)
class Not(Formula):
    formula: Formula
    
    def variables(self) -> Set[Variable]:
        return self.formula.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.formula.free_variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        return Not(self.formula.substitute(mapping))
    
    def functions(self) -> Set[str]:
        return self.formula.functions()
    
    def depth(self) -> int:
        return self.formula.depth()
    
    def size(self) -> int:
        return 1 + self.formula.size()

    def negate(self) -> 'Formula':
        return self.formula
    
    def __repr__(self):
        return f"~{self.formula}"
    
    def __hash__(self):
        return hash(("not", self.formula))


@dataclass(frozen=True)
class And(Formula):
    left: Formula
    right: Formula
    
    def variables(self) -> Set[Variable]:
        return self.left.variables() | self.right.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.left.free_variables() | self.right.free_variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        return And(self.left.substitute(mapping), self.right.substitute(mapping))
    
    def functions(self) -> Set[str]:
        return self.left.functions() | self.right.functions()
    
    def depth(self) -> int:
        return 1 + max(self.left.depth(), self.right.depth())
    
    def size(self) -> int:
        return 1 + self.left.size() + self.right.size()
    
    def __repr__(self):
        return f"({self.left} & {self.right})"
    
    def __hash__(self):
        return hash(("and", self.left, self.right))


@dataclass(frozen=True)
class Or(Formula):
    left: Formula
    right: Formula
    
    def variables(self) -> Set[Variable]:
        return self.left.variables() | self.right.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.left.free_variables() | self.right.free_variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        return Or(self.left.substitute(mapping), self.right.substitute(mapping))
    
    def functions(self) -> Set[str]:
        return self.left.functions() | self.right.functions()
    
    def depth(self) -> int:
        return 1 + max(self.left.depth(), self.right.depth())
    
    def size(self) -> int:
        return 1 + self.left.size() + self.right.size()
    
    def __repr__(self):
        return f"({self.left} | {self.right})"
    
    def __hash__(self):
        return hash(("or", self.left, self.right))


@dataclass(frozen=True)
class Implies(Formula):
    antecedent: Formula
    consequent: Formula
    
    def variables(self) -> Set[Variable]:
        return self.antecedent.variables() | self.consequent.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.antecedent.free_variables() | self.consequent.free_variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        return Implies(
            self.antecedent.substitute(mapping),
            self.consequent.substitute(mapping)
        )
    
    def functions(self) -> Set[str]:
        return self.antecedent.functions() | self.consequent.functions()
    
    def depth(self) -> int:
        return 1 + max(self.antecedent.depth(), self.consequent.depth())
    
    def size(self) -> int:
        return 1 + self.antecedent.size() + self.consequent.size()
    
    def __repr__(self):
        return f"({self.antecedent} -> {self.consequent})"
    
    def __hash__(self):
        return hash(("implies", self.antecedent, self.consequent))


@dataclass(frozen=True)
class Forall(Formula):
    variable: Variable
    body: Formula
    
    def variables(self) -> Set[Variable]:
        return {self.variable} | self.body.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.body.free_variables() - {self.variable}
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        if self.variable in mapping:
            new_mapping = {k: v for k, v in mapping.items() if k != self.variable}
        else:
            new_mapping = mapping
        return Forall(self.variable, self.body.substitute(new_mapping))
    
    def functions(self) -> Set[str]:
        return self.body.functions()
    
    def depth(self) -> int:
        return 1 + self.body.depth()
    
    def size(self) -> int:
        return 1 + self.body.size()
    
    def __repr__(self):
        return f"Forall {self.variable}.{self.body}"
    
    def __hash__(self):
        return hash(("forall", self.variable, self.body))


@dataclass(frozen=True)
class Exists(Formula):
    variable: Variable
    body: Formula
    
    def variables(self) -> Set[Variable]:
        return {self.variable} | self.body.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.body.free_variables() - {self.variable}
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        if self.variable in mapping:
            new_mapping = {k: v for k, v in mapping.items() if k != self.variable}
        else:
            new_mapping = mapping
        return Exists(self.variable, self.body.substitute(new_mapping))
    
    def functions(self) -> Set[str]:
        return self.body.functions()
    
    def depth(self) -> int:
        return 1 + self.body.depth()
    
    def size(self) -> int:
        return 1 + self.body.size()
    
    def __repr__(self):
        return f"Exists {self.variable}.{self.body}"
    
    def __hash__(self):
        return hash(("exists", self.variable, self.body))


@dataclass(frozen=True)
class LessEq(Formula):
    """Inequality: left <= right"""
    left: Term
    right: Term
    
    def variables(self) -> Set[Variable]:
        return self.left.variables() | self.right.variables()
    
    def free_variables(self) -> Set[Variable]:
        return self.variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Formula':
        return LessEq(self.left.substitute(mapping), self.right.substitute(mapping))
    
    def functions(self) -> Set[str]:
        return self.left.functions() | self.right.functions()
    
    def depth(self) -> int:
        return max(self.left.depth(), self.right.depth())
    
    def size(self) -> int:
        return 1 + self.left.size() + self.right.size()
    
    def __repr__(self):
        return f"{self.left} <= {self.right}"
    
    def __hash__(self):
        return hash(("<=", self.left, self.right))


# ═══════════════════════════════════════════════════
# CLAUSE NORMAL FORM STRUCTURES
# ═══════════════════════════════════════════════════

@dataclass(frozen=True)
class Literal:
    atom: Formula  # Atom, Equality, or LessEq
    positive: bool = True
    
    def negate(self) -> 'Literal':
        return Literal(self.atom, not self.positive)
    
    def variables(self) -> Set[Variable]:
        return self.atom.variables()
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Literal':
        return Literal(self.atom.substitute(mapping), self.positive)
    
    def __repr__(self):
        if self.positive:
            return str(self.atom)
        return f"~{self.atom}"
    
    def __hash__(self):
        return hash((self.atom, self.positive))


@dataclass(frozen=True)
class Clause:
    literals: FrozenSet[Literal] = field(default_factory=frozenset)
    source: str = ""  # Track provenance
    
    def is_empty(self) -> bool:
        return len(self.literals) == 0
    
    def is_unit(self) -> bool:
        return len(self.literals) == 1
    
    def variables(self) -> Set[Variable]:
        result = set()
        for lit in self.literals:
            result |= lit.variables()
        return result
    
    def substitute(self, mapping: Dict[Variable, Term]) -> 'Clause':
        return Clause(
            frozenset(lit.substitute(mapping) for lit in self.literals),
            self.source
        )
    
    def size(self) -> int:
        return sum(lit.atom.size() for lit in self.literals)
    
    def __repr__(self):
        if self.is_empty():
            return "[]"
        return " | ".join(str(l) for l in sorted(self.literals, key=str))
    
    def __hash__(self):
        return hash(self.literals)
    
    def __eq__(self, other):
        return isinstance(other, Clause) and self.literals == other.literals
    
    def __lt__(self, other):
        return str(self) < str(other)


# ═══════════════════════════════════════════════════
# UTILITY: Term complexity for scoring
# ═══════════════════════════════════════════════════

def term_complexity(term: Term) -> int:
    """Count total nodes in term tree."""
    return term.size()

def formula_complexity(formula: Formula) -> int:
    """Count total nodes in formula tree."""
    return formula.size()

def formula_depth(formula: Formula) -> int:
    """Maximum nesting depth of formula."""
    return formula.depth()


# ---------------------------------------------------------------------------
# OPERAD_SIGNATURES (Coloured Operads)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signature:
    arg_sorts: Optional[Tuple[Sort, ...]]
    result_sort: Sort
    variadic: bool = False

def _term_sort(t: Term) -> Sort:
    s = getattr(t, "sort", None)
    if s is None:
        raise ValueError(f"Untyped leaf term: {t!r} has no .sort")
    return s

OPERAD_SIGNATURES: Dict[str, Signature] = {
    # Attention algebra (MODULE endomorphisms)
    "Compose": Signature((MODULE, MODULE), MODULE),
    "Transpose": Signature((MODULE,), MODULE),
    "phi": Signature((MODULE,), MODULE),
    "Attn": Signature((MODULE, MODULE, MODULE), MODULE),
    "Softmax": Signature((MODULE,), MODULE),
    "Seq": Signature((MODULE,), MODULE, variadic=True),
    "Par_Dyn": Signature((MODULE, MODULE), MODULE),
    
    # Common scalar ops (REAL)
    "add": Signature((REAL, REAL), REAL, variadic=True),
    "multiply": Signature((REAL, REAL), REAL),
    "inverse": Signature((REAL,), REAL),
    "exp": Signature((REAL,), REAL),
    "ResourceCost": Signature((MODULE,), REAL),
    "Comp": Signature((MODULE,), REAL),
    "Risk": Signature((MODULE,), REAL),
    "Ent": Signature((MODULE,), REAL),
    "max": Signature((REAL, REAL), REAL, variadic=True),
    "min": Signature((REAL, REAL), REAL, variadic=True),
    
    # Mixed ops
    "scale": Signature((REAL, MODULE), MODULE),
    "dot_product": Signature((MODULE, MODULE), REAL),
    "Barrier": Signature((MODULE, PRED), MODULE),
    "P_TRUE": Signature(None, PRED),
    "Choice": Signature((MODULE, MODULE, PROB), MODULE),
    "Sec_Filter": Signature((MODULE,), MODULE),
    "Superpose": Signature((MODULE, MODULE), MODULE),
    "Evidence": Signature((MODULE,), MODULE),
    "Dep": Signature((MODULE, MODULE), REAL),
    "minus": Signature((REAL, REAL), REAL),

    # Future/MCTS auxiliary attention symbols
    "Normalize": Signature((MODULE, MODULE), MODULE),
    "DotR": Signature((MODULE, MODULE), MODULE),
    "DenDotR": Signature((MODULE, MODULE), MODULE),
    "OuterN": Signature((MODULE, MODULE), MODULE),
    "OuterN_1": Signature((MODULE, MODULE), MODULE),
    "Attn_Kernel": Signature((MODULE, MODULE, MODULE), MODULE),
    "PhiScore": Signature((MODULE, MODULE), MODULE),
    "AttnMul": Signature((MODULE, MODULE), MODULE),
    "AttnMul_1": Signature((MODULE, MODULE), MODULE),

    # Probability combinators
    "union_bound": Signature((PROB, PROB), PROB, variadic=True),
    "prob_weight": Signature((PROB, REAL), REAL),
    "prob_complement": Signature((PROB,), PROB),

    # Analysis placeholders
    "kernel_error": Signature(None, REAL),
    "DenHat": Signature(None, REAL),
    "NumHat": Signature(None, MODULE),
    "tau": Signature(None, REAL),
    
    # Dummy variables from existing code may need these or they'll be migrated
    # Core constants
    "ID_M": Signature(None, MODULE),
    "ZERO_M": Signature(None, MODULE),
    "R_ZERO": Signature(None, REAL),
    "R_ONE": Signature(None, REAL),
    "R_INF": Signature(None, REAL),
    "R_PENALTY": Signature(None, REAL),
    "ZERO_J": Signature(None, REAL),
    "ZERO_bit": Signature(None, REAL),
    "LANDAUER": Signature(None, REAL),
    "DEP_ZERO": Signature(None, REAL),
    "DEP_ONE": Signature(None, REAL),
    "P_TRUE": Signature(None, PRED),
    "PROB_ZERO": Signature(None, PROB),
    "PROB_ONE": Signature(None, PROB),

    # Dummy variables and domain markers
    "X": Signature(None, MODULE),
    "W_Q": Signature(None, MODULE),
    "W_K": Signature(None, MODULE),
    "V": Signature(None, MODULE),
    "epsilon": Signature(None, REAL),
    "N": Signature(None, REAL),
    "e_hat": Signature(None, REAL),

    # Tranche 6: Deep Algebra & Topological Physics
    "Half": Signature((MODULE,), MODULE),
    "Trotter": Signature((MODULE,), MODULE, variadic=True),
}

def register_sort(name: str) -> Sort:
    """Registers a new sort globally."""
    return Sort(name)

def register_signature(symbol: str, arg_sorts: Optional[Tuple[Sort, ...]], result_sort: Sort, variadic: bool = False):
    """Registers a new function signature globally."""
    OPERAD_SIGNATURES[symbol] = Signature(arg_sorts, result_sort, variadic)

def validate_application(symbol: str, args: Tuple[Term, ...], result_sort: Sort) -> None:
    sig = OPERAD_SIGNATURES.get(symbol)
    if sig is None:
        raise ValueError(
            f"Unknown function symbol '{symbol}'. "
            f"Add it to OPERAD_SIGNATURES to use it."
        )

    if result_sort != sig.result_sort:
        raise ValueError(
            f"Result sort mismatch for '{symbol}': got {result_sort}, expected {sig.result_sort}"
        )

    if sig.arg_sorts is None:
        return

    if sig.variadic:
        if len(args) < 1:
            raise ValueError(f"Variadic '{symbol}' requires at least 1 arg; got {len(args)}")
        want = sig.arg_sorts[0]
        for a in args:
            got = _term_sort(a)
            if got != want:
                raise ValueError(f"Arg sort mismatch for '{symbol}': got {got}, expected {want}")
        return

    if len(args) != len(sig.arg_sorts):
        raise ValueError(
            f"Arity mismatch for '{symbol}': got {len(args)}, expected {len(sig.arg_sorts)}"
        )

    for i, (a, want) in enumerate(zip(args, sig.arg_sorts)):
        got = _term_sort(a)
        if got != want:
            raise ValueError(
                f"Arg sort mismatch for '{symbol}' at index {i}: "
                f"got {got} for term '{a}', expected {want}"
            )
