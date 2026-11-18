# Model Card: Fragility and Capacity

## Intended use

- A research case study in measuring factor exit risk and capacity.
- A reusable capacity-model template for allocators and researchers.
- A benchmark test for crowding overlays: any new signal should beat a
  volatility-managed portfolio at equal average exposure.

## Not intended for

- Live trading, position sizing, or capital allocation.
- Claims about other investors' actual positioning.
- Causal claims about crowding and factor returns.
- Generalization beyond large US equities and the three factors studied.

## Inputs

- Daily split- and dividend-adjusted closes and reported volume from `yfinance`.
- Current S&P 500/400 membership as a candidate pool.
- Assumed impact coefficient (`c = 0.314`), execution horizon (10 days),
  participation (10%), spread (3bp), and borrow (50bp).

## Outputs

- A fragility composite per factor per week.
- A capacity curve, cost-drag AUM, retention AUM, and sensitivity tables.
- A tail study with quantile regression, expected shortfall, and an overlay
  comparison against static, exposure-matched, volatility-managed, and random
  controls.

## Performance and limitations

- The sample is survivor-only: zero delistings in 895 names. Factor premia and
  capacity levels are biased upward.
- The fragility composite is about 40% correlated with realized volatility; H2
  fails. It is a volatility proxy more than a crowding measure.
- The overlay loses to volatility management on true expected shortfall across
  all three factors.
- The capacity level is a model output, not a measurement. It moves by roughly
  20x across the execution horizon and by orders of magnitude across premium
  assumptions.
- The study is in-sample and exploratory. The construction was revised after
  results were inspected; see `docs/trial_ledger.md`.

## Ethical and operational notes

- No personal data, credentials, or proprietary holdings are used.
- The data source is public and mutable; each run records a SHA256 of the cached
  panel, but the cache is not committed.
- Results are not investment advice.
