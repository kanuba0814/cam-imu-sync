# Hypothesis: self-test should verify final output files

The final gate self-test currently checks that the generator exits with success
for a positive aggregate, but the goal also requires concrete final artifacts:
`best_config.yaml`, `decision.md`, and `stability_report.md`.

Expected fix:
- After a positive synthetic aggregate, assert that all expected final output
  files exist.
- Assert that `best_config.yaml` matches the selected settings file.

This is final-gate test coverage only.
