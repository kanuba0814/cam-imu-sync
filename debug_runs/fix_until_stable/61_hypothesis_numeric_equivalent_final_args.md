# Hypothesis: final command checks should accept numeric-equivalent replay args

## Observation

The final artifact generator requires run commands to match replay preflight. For numeric launch arguments, exact string matching is too brittle: `rate:=1` and `rate:=1.0` are equivalent, as are `duration:=0` and `duration:=0.0`.

The next planned replay uses defaults, but the final guard should still reject only semantic mismatches, not harmless numeric formatting differences.

## Minimal change

Only update `generate_final_stability_artifacts.py` command validation:

- compare `rate`
- compare `duration`
- compare `play_delay`

as numeric values instead of exact strings.

Do not change replay, parser gates, launch behavior, or SLAM configuration.

## Expected validation signal

A synthetic final aggregate whose commands use `rate:=1`, `duration:=0`, and `play_delay:=2` should be accepted when preflight records `1.0`, `0.0`, and `2.0`. A command with a different numeric value such as `rate:=0.5` should still be rejected.
