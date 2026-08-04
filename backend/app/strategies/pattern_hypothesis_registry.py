from dataclasses import dataclass
import hashlib
import json


REGISTRY_VERSION = "1.0.0"
INTERPRETATION = "research_hypothesis_not_trading_signal"


@dataclass(frozen=True)
class PatternHypothesis:
    hypothesis_id: str
    version: str
    title: str
    family: str
    direction: str
    lifecycle: str
    readiness: str
    question: str
    required_observations: tuple[str, ...]
    invalidation_observations: tuple[str, ...]
    required_timeframes: tuple[str, ...]
    evidence_status: str = "conceptual_reference_not_validated_evidence"
    interpretation: str = INTERPRETATION


def _hypotheses() -> tuple[PatternHypothesis, ...]:
    return (
        PatternHypothesis(
            "market_structure_long", "1.0.0", "Yüksələn bazar strukturu", "market_structure", "long",
            "idea", "definition_ready",
            "Yalnız bağlanmış barlarda ardıcıl HH və HL müşahidəsi sonrakı nəticə paylanmasını dəyişirmi?",
            ("closed_bar_swing_high", "closed_bar_swing_low", "higher_high", "higher_low"),
            ("lower_low", "structure_ambiguity", "insufficient_closed_swings"), ("M15", "H1"),
        ),
        PatternHypothesis(
            "market_structure_short", "1.0.0", "Enən bazar strukturu", "market_structure", "short",
            "idea", "definition_ready",
            "Yalnız bağlanmış barlarda ardıcıl LH və LL müşahidəsi sonrakı nəticə paylanmasını dəyişirmi?",
            ("closed_bar_swing_high", "closed_bar_swing_low", "lower_high", "lower_low"),
            ("higher_high", "structure_ambiguity", "insufficient_closed_swings"), ("M15", "H1"),
        ),
        PatternHypothesis(
            "liquidity_sweep_reclaim_long", "1.0.0", "Aşağı səviyyə süpürülməsi və geri alınma", "liquidity_sweep", "long",
            "idea", "definition_ready",
            "Əvvəlki bərabər diblərin altına keçib bağlanışla səviyyəni geri alan bar ayrıca tarixi davranış yaradırmı?",
            ("equal_lows_tolerance", "low_sweep", "closed_bar_reclaim"),
            ("close_below_swept_level", "missing_reference_lows", "open_bar"), ("M5", "M15"),
        ),
        PatternHypothesis(
            "liquidity_sweep_reclaim_short", "1.0.0", "Yuxarı səviyyə süpürülməsi və geri alınma", "liquidity_sweep", "short",
            "idea", "definition_ready",
            "Əvvəlki bərabər təpələrin üstünə keçib bağlanışla səviyyənin altına qayıdan bar ayrıca tarixi davranış yaradırmı?",
            ("equal_highs_tolerance", "high_sweep", "closed_bar_reclaim"),
            ("close_above_swept_level", "missing_reference_highs", "open_bar"), ("M5", "M15"),
        ),
        PatternHypothesis(
            "structure_break_long", "1.0.0", "Yuxarı struktur qırılması və retest", "bos_choch_retest", "long",
            "idea", "needs_precise_detector",
            "Təsdiqlənmiş swing səviyyəsinin bağlanışla yuxarı qırılması və səbəbli retest ayrıca yoxlanmağa dəyərmi?",
            ("confirmed_swing_high", "closed_break_above", "causal_retest"),
            ("close_back_below_level", "ambiguous_swing", "retest_before_break"), ("M5", "M15", "H1"),
        ),
        PatternHypothesis(
            "structure_break_short", "1.0.0", "Aşağı struktur qırılması və retest", "bos_choch_retest", "short",
            "idea", "needs_precise_detector",
            "Təsdiqlənmiş swing səviyyəsinin bağlanışla aşağı qırılması və səbəbli retest ayrıca yoxlanmağa dəyərmi?",
            ("confirmed_swing_low", "closed_break_below", "causal_retest"),
            ("close_back_above_level", "ambiguous_swing", "retest_before_break"), ("M5", "M15", "H1"),
        ),
        PatternHypothesis(
            "fvg_order_block_deferred", "1.0.0", "FVG və order block ailəsi", "zone_model", "neutral",
            "idea", "definition_incomplete",
            "Zona sərhədi, yaranma vaxtı və invalidasiya qaydası əvvəlcədən dəqiqləşdirildikdən sonra bu ailə yoxlanmalıdırmı?",
            ("versioned_zone_definition", "causal_creation_time", "explicit_invalidation"),
            ("subjective_zone_selection", "future_leakage", "definition_missing"), ("M5", "M15", "H1"),
        ),
    )


def get_pattern_hypothesis_registry() -> dict[str, object]:
    hypotheses = _hypotheses()
    payload = {
        "registry_version": REGISTRY_VERSION,
        "lifecycle": "idea",
        "interpretation": INTERPRETATION,
        "source_policy": "examples_are_conceptual_references_not_validated_evidence",
        "execution_boundary": "no_signal_no_order_no_position_sizing",
        "hypotheses": [hypothesis.__dict__ for hypothesis in hypotheses],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["fingerprint"] = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    return payload
