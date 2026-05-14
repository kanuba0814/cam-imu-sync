# Hypothesis: reject aggregate run_count mismatch

The final artifact generator currently checks that `pass_count` matches the
number of run summaries, but it should also reject an aggregate whose reported
`run_count` differs from the actual `runs` list length.

Expected fix:
- Require `run_count == len(runs)`.
- Add a synthetic self-test case where `run_count=4` while only three run
  summaries are present.

This is final-gate integrity only and does not change replay behavior.
