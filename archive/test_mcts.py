from discovery.mcts_grammar import GrammarSynthesizer
from discovery.scorer import InterestingnessScorer

scorer = InterestingnessScorer()
synth = GrammarSynthesizer(scorer, max_depth=6)

print("Running MCTS Synthesizer for 10000 iterations to find O(N) linear attention bounds...")
formulas = synth.synthesize(iterations=10000)

print(f"Generated {len(formulas)} novel formulas.")

for f in formulas:
    print(f"[{scorer.score(f):.2f}] {f}")
