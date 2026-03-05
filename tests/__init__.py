"""
Merged (conceptually): Gate 3 v1.2 is now the active, integrated implementation in the working tree.

State after merge

Gate 3 verdict logic: PASS iff errors==0 and unknown_required==0
Current metrics: 0 errors, 0 required unknowns, 60 coverage unknowns (sample reported deterministically)
Determinism/idempotency: verified
Docs: walkthrough.md baseline output generalized (Sample: <var@axiom...>, ...)
Artifacts in place

grounding/dim_constraints.py (new)
grounding/dimensions.py (updated to use Rename → Collect → Solve → Validate → Report)
tests/test_dim_constraints.py (acceptance suite)
walkthrough.md (updated)
Note: your environment reports no .git directory, so there’s no literal git merge to run here—these changes are already applied directly to the filesystem.

Post-merge follow-ons (tracked separately)

Remove deprecated DimConstraintSolver after soak period
Add axiom-order shuffle determinism test
Add explicit divide() inference unit test (if not already present)
Add CI performance baseline for Gate 3 runtime
"""
