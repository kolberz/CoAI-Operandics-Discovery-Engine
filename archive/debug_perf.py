import time
import core.logic as cl
from discovery.normalization import egraph_term_to_logic, EApp, ESym, EVar

def test_perf():
    # Construct a nested ETerm
    # Seq(Barrier(M1, P_TRUE), Risk(M1))
    term = EApp("Seq", (
        EApp("Barrier", (EVar("M1"), ESym("P_TRUE"))),
        EApp("Risk", (EVar("M1"),))
    ))
    
    print("Starting performance test...")
    start = time.time()
    for i in range(100000):
        _ = egraph_term_to_logic(term)
    end = time.time()
    print(f"100,000 conversions took {end - start:.4f} seconds")

if __name__ == "__main__":
    test_perf()
