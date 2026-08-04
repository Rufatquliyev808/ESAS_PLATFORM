# ESAS Platform — Strategy Module Contract

Version: 1.0.0  
Lifecycle: **EXPERIMENTAL**

## Purpose

Strategy modules turn versioned, closed-bar technical indicators into deterministic
research observations. They do not create BUY/SELL signals, orders, positions, or
capital-risk decisions.

## Required boundaries

- Every strategy has a stable `strategy_id`, semantic version, lifecycle, description,
  required feature list, and explicit parameters.
- Every result is bound to the source dataset, bar, and indicator fingerprints.
- Only closed bars and causal indicator values may be read. A later bar must never
  change an earlier observation.
- Warm-up observations remain visible as `insufficient_data`.
- Identical inputs and parameters must produce an identical result fingerprint.
- Each strategy lives in its own independently testable module.
- Experimental observations are labelled `research_observation_not_trading_signal`.

## Reference module

`ema_close_relation` version `1.0.0` classifies each closed bar as `above_ema`,
`below_ema`, or `at_ema`. It is a reference implementation, not a trade recommendation.

`rsi_regime_observation` version `1.0.0` independently classifies causal RSI values as
`low_rsi` (value <= low threshold), `high_rsi` (value >= high threshold), or
`neutral_rsi` (strictly between the thresholds). It remains a research observation.

## Result lineage

Every result includes symbol, timeframe, parameters, dataset fingerprint, bar
fingerprint, indicator fingerprint, observations, summary counts, and its own SHA-256
fingerprint. A consumer must invalidate the result if an upstream fingerprint changes.

## Historical outcome evaluation

`forward_closed_bar_outcome` version `1.0.0` may be attached to any completed strategy
result. It measures the close-to-close percentage change at a positive, explicit future
closed-bar horizon. The evaluator must preserve the original strategy observations;
future prices may label an outcome but may never participate in creating an observation.

Each outcome is `matured`, `immature`, or `not_applicable`. Matured outcomes expose
direction and return, while summaries keep relations separate and remain bound to the
dataset, bar, and strategy fingerprints. These measurements are historical research,
not prediction accuracy, trading signals, or authorization to place an order.

## Promotion rule

An EXPERIMENTAL strategy cannot become SHADOW or ACTIVE here. Promotion requires a
separate evidence package, validation gate, safety review, and explicit approval.
