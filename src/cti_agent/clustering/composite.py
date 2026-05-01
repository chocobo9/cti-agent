"""PDS + FWPD composite distance for domain clustering.

Combines the 7 individual feature distances (M3.1) into a single
composite distance using two components:

  observed = Σ(w_f × dist_f) / Σ(w_f)          for f in shared
  penalty  = Σ(w_f × coverage_f) / Σ(w_f)      for f in partial_missing

  d = (1 - α) × observed + α × penalty

- PDS (Partial Distance Strategy): observed distance is normalized
  over features where BOTH domains have data.
- FWPD (Feature Weighted Penalty Dissimilarity): one-sided missing
  features incur a penalty proportional to that feature's dataset
  coverage rate.  High coverage missing = anomalous = big penalty.
  coverage_rate=None means no penalty (safe default before stats run).
- Both-missing features are excluded entirely.
- Returns NaN when shared features < min_shared_features.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from cti_agent.clustering.distance import (
    FEATURE_NAMES,
    asn_geo_distance,
    domain_string_distance,
    favicon_distance,
    jarm_distance,
    passive_dns_distance,
    registration_time_distance,
    tls_certificate_distance,
)
from cti_agent.enrichment.models import DomainEnrichment


class FeatureConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    weight: float = 1.0
    coverage_rate: float | None = None
    enabled: bool = True

    @field_validator("weight")
    @classmethod
    def _weight_non_negative(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError("weight must be >= 0.0")
        return v

    @field_validator("coverage_rate")
    @classmethod
    def _coverage_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("coverage_rate must be in [0.0, 1.0] or None")
        return v


class WeightConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha: float = 0.5
    min_shared_features: int = 2
    features: dict[str, FeatureConfig] = {}

    @field_validator("alpha")
    @classmethod
    def _alpha_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("alpha must be in [0.0, 1.0]")
        return v

    @field_validator("min_shared_features")
    @classmethod
    def _min_shared_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("min_shared_features must be >= 1")
        return v

    @model_validator(mode="after")
    def _validate_features(self) -> WeightConfig:
        for name in self.features:
            if name not in FEATURE_NAMES:
                raise ValueError(f"Unknown feature: {name!r}. Valid: {FEATURE_NAMES}")
        if self.features and not any(f.enabled for f in self.features.values()):
            raise ValueError("At least one feature must be enabled")
        return self

    def get_active_features(self) -> list[str]:
        return [name for name, fc in self.features.items() if fc.enabled]

    @classmethod
    def default(cls) -> WeightConfig:
        return cls(
            alpha=0.5,
            min_shared_features=2,
            features={name: FeatureConfig() for name in FEATURE_NAMES},
        )

    @classmethod
    def from_yaml(cls, path: Path | str, profile_name: str = "default") -> WeightConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        profiles = raw.get("profiles", {})
        if profile_name not in profiles:
            available = list(profiles.keys())
            raise ValueError(f"Profile {profile_name!r} not found. Available: {available}")
        profile: dict[str, Any] = profiles[profile_name]
        features_raw = profile.get("features", {})
        features = {
            name: FeatureConfig(**cfg) for name, cfg in features_raw.items()
        }
        return cls(
            alpha=profile.get("alpha", 0.5),
            min_shared_features=profile.get("min_shared_features", 2),
            features=features,
        )

    @classmethod
    def from_dataset(
        cls, enrichment_dir: Path | str, auto_coverage: bool = True
    ) -> WeightConfig:
        raise NotImplementedError("Full implementation deferred — use compute_feature_coverage.py")


# ---------------------------------------------------------------------------
# Data presence checks
# ---------------------------------------------------------------------------

def _has_data_for_feature(e: DomainEnrichment, feature: str) -> bool:
    checks: dict[str, bool] = {
        "domain_string": True,
        "registration_time": e.creation_date is not None,
        "tls_certificate": bool(e.certificates),
        "jarm": e.jarm_hash is not None and e.jarm_hash != "0" * 62,
        "favicon": e.favicon_hash is not None,
        "passive_dns": bool(e.passive_dns) or bool(e.dns_record_types),
        "asn_geo": any(g.asn_number is not None for g in e.geoip)
                   or any(g.country is not None for g in e.geoip),
    }
    return checks.get(feature, False)


# ---------------------------------------------------------------------------
# Feature distance dispatch
# ---------------------------------------------------------------------------

def _compute_feature_distance(a: DomainEnrichment, b: DomainEnrichment, feature: str) -> float:
    dispatch = {
        "domain_string": lambda: domain_string_distance(a.domain, b.domain),
        "registration_time": lambda: registration_time_distance(a.creation_date, b.creation_date),
        "tls_certificate": lambda: tls_certificate_distance(a.certificates, b.certificates),
        "jarm": lambda: jarm_distance(a.jarm_hash, b.jarm_hash),
        "favicon": lambda: favicon_distance(a.favicon_hash, b.favicon_hash),
        "passive_dns": lambda: passive_dns_distance(
            a.passive_dns, a.dns_record_types, b.passive_dns, b.dns_record_types,
        ),
        "asn_geo": lambda: asn_geo_distance(a.geoip, b.geoip),
    }
    return dispatch[feature]()


# ---------------------------------------------------------------------------
# Composite distance (PDS + FWPD)
# ---------------------------------------------------------------------------

def composite_distance(
    a: DomainEnrichment,
    b: DomainEnrichment,
    config: WeightConfig | None = None,
) -> float:
    """PDS + FWPD composite distance.

    Returns a float in [0, 1] or NaN when shared features < min_shared.
    """
    cfg = config if config is not None else WeightConfig.default()
    active = cfg.get_active_features()

    shared: list[str] = []
    partial_missing: list[str] = []

    for feat in active:
        has_a = _has_data_for_feature(a, feat)
        has_b = _has_data_for_feature(b, feat)
        if has_a and has_b:
            shared.append(feat)
        elif has_a or has_b:
            partial_missing.append(feat)

    if len(shared) < cfg.min_shared_features:
        return float("nan")

    # PDS: observed distance — normalized over shared features only
    obs_weighted = sum(cfg.features[f].weight * _compute_feature_distance(a, b, f) for f in shared)
    obs_weight_sum = sum(cfg.features[f].weight for f in shared)
    observed = obs_weighted / obs_weight_sum if obs_weight_sum > 0.0 else 0.0

    # FWPD: penalty — normalized over partial_missing features only
    if partial_missing:
        pen_weighted = 0.0
        pen_weight_sum = 0.0
        for f in partial_missing:
            fc = cfg.features[f]
            pen_weight_sum += fc.weight
            if fc.coverage_rate is not None:
                pen_weighted += fc.weight * fc.coverage_rate
        penalty = pen_weighted / pen_weight_sum if pen_weight_sum > 0.0 else 0.0
    else:
        penalty = 0.0

    if partial_missing:
        d = (1.0 - cfg.alpha) * observed + cfg.alpha * penalty
    else:
        d = observed
    return min(max(d, 0.0), 1.0)
