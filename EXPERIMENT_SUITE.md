VERBOSE EXPERIMENT SUITE
OPERANDICS DISCOVERY ENGINE
==============================================

This document enumerates a complete set of structured experiments
designed to evaluate the Operandics Discovery Engine across multiple
research domains. Each experiment includes objectives, symbolic
grammars, experimental procedures, evaluation metrics, and expected
outcomes.

The experiments are designed to demonstrate:

• automated symbolic discovery
• formal verification of discovered identities
• compression-driven abstraction discovery
• computational performance improvements
• emergence of algebraic structure

All discovered equivalences must be verified using Lean before being
considered valid results.

==============================================

1. MACHINE LEARNING SYSTEMS
Automated Discovery of Tensor Optimization Rules
==============================================

Objective
---------

Demonstrate that the discovery engine can autonomously generate algebraic
rewrite rules for tensor programs that reduce computational complexity
and memory usage.

Background
----------

Modern deep learning systems rely heavily on optimized tensor
computation graphs. Many optimizations depend on algebraic
identities that are currently written manually by engineers.

This experiment tests whether the engine can discover such identities
automatically.

Symbolic Grammar
----------------

Operators
  matmul(A,B)
  transpose(A)
  add(A,B)
  scale(A,c)
  softmax(A)

Variables
  Q, K, V

Expression Examples
-------------------

matmul(matmul(Q, transpose(K)), V)
matmul(Q, matmul(transpose(K), V))
matmul(softmax(matmul(Q, transpose(K))), V)

Procedure
---------

1. Generate 200–500 candidate tensor expressions using the MCTS grammar.
2. Feed expressions into the equality-saturation engine.
3. Apply compression-guided rewrite scheduling.
4. Evaluate candidate equivalences.
5. Verify equivalence in Lean.
6. Export verified rules.

Evaluation Metrics
------------------

number_of_verified_rewrite_rules
FLOP_reduction
memory_reduction
interaction_rank_reduction

Expected Discoveries
--------------------

matmul(matmul(Q, transpose(K)), V)
→ matmul(Q, matmul(transpose(K), V))

Impact
------

Such rules eliminate large intermediate tensors and significantly
reduce memory requirements in transformer attention blocks.

Potential Venues
----------------

MLSys
NeurIPS Systems Track

==============================================
2. AUTOMATED THEOREM PROVING
Discovery of Algebraic Lemmas
==============================================

Objective
---------

Evaluate the ability of the engine to rediscover classical algebraic
identities and generate reusable lemma libraries.

Background
----------

Many automated theorem provers rely on human-written libraries of
helper lemmas. The goal of this experiment is to determine whether the
engine can automatically generate these lemmas.

Symbolic Grammar
----------------

Operators
  add(A,B)
  multiply(A,B)
  transpose(A)
  identity()

Variables
  A, B, C

Procedure
---------

1. Remove known algebraic identities from the rule set.
2. Run the discovery engine for N iterations.
3. Allow equality saturation to explore equivalence classes.
4. Rank lemmas by proof complexity and compression.
5. Verify all lemmas using Lean.

Metrics
-------

lemma_count
proof_complexity
derivational_centrality
compression_ratio

Expected Rediscoveries
----------------------

(A · B) · C = A · (B · C)
A · I = A

Impact
------

Demonstrates the engine's capacity to reconstruct mathematical
structure autonomously.

Potential Venues
----------------

CADE
IJCAR

==============================================
3. PROGRAM SYNTHESIS
Automatic Operator Discovery
==============================================

Objective
---------

Detect and promote frequently occurring symbolic patterns as new
operators.

Background
----------

Human programmers frequently abstract repeated code patterns into
functions or APIs. This experiment tests whether the engine can perform
similar abstraction automatically.

Grammar
-------

Operators
  map(f,x)
  compose(f,g)
  filter(f,x)
  fold(f,x)

Variables
  f, g, x

Procedure
---------

1. Collect subexpressions appearing frequently in proofs.
2. Compute compression gain from replacing the pattern.
3. Introduce new symbolic operators.
4. Re-run discovery with expanded grammar.

Metrics
-------

operator_count
compression_gain
proof_length_reduction

Example Discovery
-----------------

map(f, map(g, x))
→ map(compose(f,g), x)

Impact
------

This demonstrates automated abstraction discovery.

Potential Venues
----------------

POPL
ICFP

==============================================
4. SCIENTIFIC COMPUTING
Symbolic Discovery of Efficient Tensor Contractions
==============================================

Objective
---------

Discover alternative formulations of tensor contractions that reduce
computational complexity.

Grammar
-------

Operators
  matmul
  add
  sum
  transpose

Variables
  A, B, C

Procedure
---------

1. Generate candidate contraction expressions.
2. Run compression-guided search.
3. Evaluate computational cost.

Metrics
-------

FLOP_reduction
intermediate_tensor_size
numerical_equivalence

==============================================
5. FORMAL METHODS
Verified Compiler Optimization Rules
==============================================

Objective
---------

Automatically generate formally verified rewrite rules for compiler
optimization.

Grammar
-------

Operators
  add
  multiply
  divide
  matmul

Procedure
---------

1. Discover algebraic identities.
2. Verify identities in Lean.
3. Export them as compiler rewrite rules.

Metrics
-------

verified_rule_count
runtime_improvement
proof_size

Example
-------

(A *B)* C → A *(B* C)

Potential Venues
----------------

PLDI
CAV

==============================================
6. CATEGORY THEORY / ABSTRACT ALGEBRA
Emergence of Compositional Laws
==============================================

Objective
---------

Study whether compositional algebraic laws emerge from compression-
driven symbolic search.

Grammar
-------

Operators
  compose
  identity
  tensor

Procedure
---------

1. Run discovery cycles.
2. Construct theorem dependency graph.
3. Analyze central structural laws.

Metrics
-------

associativity_frequency
lemma_centrality

==============================================
7. AI FOR MATHEMATICS
Automatic Lemma Recovery
==============================================

Objective
---------

Test whether the engine can rediscover missing intermediate lemmas in
existing formal proofs.

Procedure
---------

1. Remove helper lemmas from Lean proofs.
2. Run discovery engine.
3. Attempt lemma reconstruction.

Metrics
-------

lemma_recovery_rate
proof_length_reduction

==============================================
8. SYSTEMS OPTIMIZATION
Neural Network Graph Rewrites
==============================================

Objective
---------

Automatically discover graph-level optimizations for neural networks.

Procedure
---------

1. Convert compute graphs into symbolic expressions.
2. Apply equality saturation.
3. Extract optimized graphs.

Metrics
-------

graph_node_reduction
kernel_fusion_opportunities
runtime_improvement

==============================================
9. SYMBOLIC COMPRESSION
Emergent Abstraction Hierarchy
==============================================

Objective
---------

Study how repeated discovery cycles create hierarchical abstractions.

Procedure
---------

1. Enable latent operator discovery.
2. Run long discovery cycles.
3. Track abstraction layers.

Metrics
-------

abstraction_depth
proof_length_reduction
operator_reuse_frequency

==============================================
10. TRANSFORMER ARCHITECTURE DISCOVERY
Rediscovery of Linear Attention
==============================================

Objective
---------

Test whether the engine can derive linear attention structure from
quadratic attention equations.

Starting Expression
-------------------

Attention(Q,K,V) = softmax(QKᵀ)V

Grammar
-------

Operators
  matmul
  transpose
  exp
  feature_map

Variables
  Q, K, V

Procedure
---------

1. Run interaction-rank biased search.
2. Discover factorizations.
3. Verify using Lean.

Expected Discovery
------------------

(QKᵀ)V → Q(KᵀV)

Impact
------

This factorization removes the N×N intermediate tensor and enables
linear attention implementations.

==============================================
FLAGSHIP EXPERIMENT
AUTOMATED DISCOVERY OF LINEAR ATTENTION
==============================================

Goal
----

Demonstrate that the engine can discover algebraic transformations that
reduce quadratic attention computations to more efficient forms.

Procedure
---------

1. Start with quadratic attention expression.
2. Allow only a limited symbolic grammar.
3. Run equality saturation with compression scoring.
4. Extract candidate identities.
5. Verify identities in Lean.
6. Benchmark computational performance.

Evaluation
----------

runtime
peak_memory
intermediate_tensor_size

Benchmark
---------

Implement both quadratic and factorized attention in PyTorch.

Example configuration
---------------------

sequence_length = 2048
embedding_dimension = 64

Expected Outcome
----------------

The factorized computation avoids building the large N×N attention
matrix, reducing memory usage and enabling faster execution.

==============================================
END OF EXPERIMENT SUITE
==============================================
