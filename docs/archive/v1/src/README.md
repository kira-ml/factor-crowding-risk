# V1 source (archived)

**Do not run or cite this code.** It produced the invalid V1 results described in
`docs/audit_v1.md`:

- `value_score = -momentum_score`, so the two factors were identical up to sign;
- full-sample standardization;
- an unpurged train/test split;
- no costs or matched controls.

It is preserved only to make the audit reproducible. The current implementation
is in `src/fcr/`.
