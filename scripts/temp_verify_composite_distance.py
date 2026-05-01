"""Temporary one-off: sample enrichment JSONs and print composite_distance pairs.

Run from repo root (cti-agent):
    python scripts/temp_verify_composite_distance.py

Optional:
    python scripts/temp_verify_composite_distance.py --seed 42 --count 4
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (default: nondeterministic)")
    parser.add_argument("--count", type=int, default=4, help="Number of domains to sample (default: 4)")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    # Imports after ROOT is known; run with cwd = ROOT or PYTHONPATH set
    sys.path.insert(0, str(ROOT / "src"))
    from cti_agent.clustering.composite import WeightConfig, composite_distance
    from cti_agent.enrichment.models import DomainEnrichment

    cfg_path = ROOT / "config/clustering_profiles/coverage_weighted.yaml"
    cfg = WeightConfig.from_yaml(cfg_path, "coverage_weighted")

    pattern = str(ROOT / "data" / "enrichment" / "*.json")
    files = glob(pattern)
    if not files:
        print(f"No JSON files under {pattern}", file=sys.stderr)
        return 1

    k = min(args.count, len(files))
    chosen = random.sample(files, k)
    sample: list[DomainEnrichment] = []
    for fpath in chosen:
        with open(fpath, encoding="utf-8") as f:
            sample.append(DomainEnrichment.model_validate(json.loads(f.read())))

    print(f"profile=coverage_weighted  samples={k}  pairs={k * (k - 1) // 2}\n")
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            d = composite_distance(sample[i], sample[j], config=cfg)
            di = sample[i].domain
            dj = sample[j].domain
            if math.isnan(d):
                print(f"{di} vs {dj}: nan (insufficient shared features)")
            else:
                print(f"{di} vs {dj}: {d:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
