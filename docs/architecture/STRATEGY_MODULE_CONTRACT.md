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

## Result lineage

Every result includes symbol, timeframe, parameters, dataset fingerprint, bar
fingerprint, indicator fingerprint, observations, summary counts, and its own SHA-256
fingerprint. A consumer must invalidate the result if an upstream fingerprint changes.

## Promotion rule

An EXPERIMENTAL strategy cannot become SHADOW or ACTIVE here. Promotion requires a
separate evidence package, validation gate, safety review, and explicit approval.
