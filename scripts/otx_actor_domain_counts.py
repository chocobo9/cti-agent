"""Export OTX domain IOCs with pulse provenance for enrichment downstream.

Outputs one CSV row per domain indicator:

    domain,actor,pulse_id,pulse_name,created

Session B `enrich_domain()` adds TLS/JARM/favicons/pDNS/ASN/etc.; this script only
collects what OTX pulses expose.

Usage:
    python -m scripts.otx_actor_domain_counts --discover-actors --limit-actors 10 \\
      --output-csv data/raw/otx_domain_pulse_iocs.csv

Background (WSL):
    nohup python -m scripts.otx_actor_domain_counts --discover-actors --loop \\
      --loop-interval-seconds 7200 --no-stdout-csv \\
      --output-csv data/raw/otx_domain_pulse_iocs.csv \\
      > data/raw/otx_crawler.log 2>&1 &
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from collections.abc import Iterable
from pathlib import Path

import httpx

from cti_agent.enrichment.config import get_settings

OTX_BASE_URL = "https://otx.alienvault.com"
SEARCH_PULSES_PATH = "/api/v1/search/pulses"
PULSE_INDICATORS_PATH = "/api/v1/pulses/{pulse_id}/indicators"
ADVERSARIES_PATH = "/otxapi/adversaries/"
DOMAIN_TYPES = {"domain"}
DOMAIN_CSV_FIELDS = ["domain", "actor", "pulse_id", "pulse_name", "created"]
IndicatorCache = dict[str, list[dict[str, object]]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", action="append", default=[], help="Actor/adversary name. Can be repeated.")
    parser.add_argument("--actors-file", type=Path, help="Text file with one actor/adversary name per line.")
    parser.add_argument(
        "--discover-actors",
        action="store_true",
        help="Load adversary names from OTX /otxapi/adversaries/ when no actor list is provided.",
    )
    parser.add_argument("--limit-actors", type=int, default=0, help="Only process the first N actors.")
    parser.add_argument("--max-pulses-per-actor", type=int, default=500, help="Search result cap per actor.")
    parser.add_argument("--page-size", type=int, default=50, help="OTX API page size.")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent pulse indicator requests.")
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=Path("data/raw/otx_pulse_indicator_cache.json"),
        help="Local pulse indicator cache file.",
    )
    parser.add_argument("--timeout", type=float, help="HTTP timeout seconds. Defaults to HTTP_TIMEOUT from .env.")
    parser.add_argument("--retries", type=int, help="HTTP retries. Defaults to MAX_RETRIES from .env.")
    parser.add_argument("--retry-delay", type=float, help="Base retry delay seconds. Defaults to RETRY_BASE_DELAY.")
    parser.add_argument("--include-hostname", action="store_true", help="Also export hostname-typed indicators.")
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="CSV path: domain,actor,pulse_id,pulse_name,created",
    )
    parser.add_argument(
        "--append-csv",
        action="store_true",
        help="If CSV exists, do not truncate it (resume-friendly).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run forever: repeat after --loop-interval-seconds (Ctrl+C to stop).",
    )
    parser.add_argument(
        "--loop-interval-seconds",
        type=int,
        default=3600,
        help="Sleep between full passes when --loop is set.",
    )
    parser.add_argument(
        "--skip-actors-in-csv",
        action="store_true",
        help="Skip actor names that already appear in the output CSV (actor column).",
    )
    parser.add_argument(
        "--truncate-each-loop",
        action="store_true",
        help="With --loop: overwrite CSV at the start of each pass (only if rows will be written).",
    )
    parser.add_argument(
        "--no-stdout-csv",
        action="store_true",
        help="Do not print CSV rows to stdout (useful with nohup).",
    )
    parser.add_argument(
        "--save-cache-every",
        type=int,
        default=1,
        help="Write pulse cache every N actors (1=every actor).",
    )
    return parser.parse_args()


def make_client(api_key: str, timeout: float | None = None) -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=OTX_BASE_URL,
        timeout=httpx.Timeout(timeout or settings.http_timeout),
        headers={
            "User-Agent": settings.user_agent,
            "X-OTX-API-KEY": api_key,
        },
        follow_redirects=True,
    )


def make_async_client(api_key: str, timeout: float | None = None) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=OTX_BASE_URL,
        timeout=httpx.Timeout(timeout or settings.http_timeout),
        headers={
            "User-Agent": settings.user_agent,
            "X-OTX-API-KEY": api_key,
        },
        follow_redirects=True,
    )


def read_actors(
    args: argparse.Namespace,
    client: httpx.Client,
    retries: int,
    retry_delay: float,
) -> list[str]:
    actors = list(args.actor)
    if args.actors_file:
        actors.extend(
            line.strip()
            for line in args.actors_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not actors and args.discover_actors:
        actors = discover_actors(client, retries, retry_delay)
    deduped = list(dict.fromkeys(actors))
    if args.limit_actors > 0:
        return deduped[: args.limit_actors]
    return deduped


def discover_actors(client: httpx.Client, retries: int, retry_delay: float) -> list[str]:
    actors: list[str] = []

    for page in paginated_get(
        client,
        ADVERSARIES_PATH,
        {"limit": 100, "page": 1},
        retries=retries,
        retry_delay=retry_delay,
    ):
        results = page.get("results", [])
        if isinstance(results, list):
            actors.extend(
                str(result.get("value") or "").strip()
                for result in results
                if isinstance(result, dict) and result.get("value")
            )

    return filter_actor_names(actors)


def filter_actor_names(names: Iterable[str]) -> list[str]:
    skip_exact = {
        "Searching",
        "Searching...",
        "Sort:",
        "Ascending",
        "Name Ascending",
        "Recently Modified",
        "Most Pulses",
        "Most Members",
        "All",
        "All Time",
        "Reset Filters",
        "Show:",
        "Filter by:",
        "Loading more Pulses",
        "Loading more users",
        "Loading more groups",
        "Join a Private Group",
        "Indicators Search",
        "Show expired indicators",
        "Indicator Type",
        "Role",
    }
    skip_prefixes = ("Also known as:", "Category:")
    skip_suffixes = ("pulse", "pulses")

    actors = [
        name.strip()
        for name in names
        if name.strip()
        and name.strip() not in skip_exact
        and not name.strip().startswith(skip_prefixes)
        and not name.strip().endswith(skip_suffixes)
        and "(" not in name.strip()
    ]
    return list(dict.fromkeys(actors))


def request_json_with_retries(
    client: httpx.Client,
    url: str,
    params: dict[str, object] | None,
    retries: int,
    retry_delay: float,
) -> dict[str, object]:
    retryable_statuses = {429, 500, 502, 503, 504}
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = client.get(url, params=params)
            if response.status_code in retryable_statuses:
                response.raise_for_status()
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return {}
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(retry_delay * (2**attempt))

    if last_exc is not None:
        raise last_exc
    return {}


def paginated_get(
    client: httpx.Client,
    path: str,
    params: dict[str, object],
    retries: int,
    retry_delay: float,
) -> Iterable[dict[str, object]]:
    next_url: str | None = path
    next_params: dict[str, object] | None = params

    while next_url:
        data = request_json_with_retries(client, next_url, next_params, retries, retry_delay)
        yield data
        next_url = data.get("next")
        next_params = None


async def request_json_with_retries_async(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, object] | None,
    retries: int,
    retry_delay: float,
) -> dict[str, object]:
    retryable_statuses = {429, 500, 502, 503, 504}
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.get(url, params=params)
            if response.status_code in retryable_statuses:
                response.raise_for_status()
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return {}
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            await asyncio.sleep(retry_delay * (2**attempt))

    if last_exc is not None:
        raise last_exc
    return {}


async def paginated_get_async(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, object],
    retries: int,
    retry_delay: float,
) -> list[dict[str, object]]:
    pages: list[dict[str, object]] = []
    next_url: str | None = path
    next_params: dict[str, object] | None = params

    while next_url:
        data = await request_json_with_retries_async(client, next_url, next_params, retries, retry_delay)
        pages.append(data)
        next_url = data.get("next")
        next_params = None

    return pages


def search_actor_pulses(
    client: httpx.Client,
    actor: str,
    page_size: int,
    max_pulses: int,
    retries: int,
    retry_delay: float,
) -> list[dict[str, object]]:
    query = f'adversary:"{actor}"'
    pulses: list[dict[str, object]] = []

    for page in paginated_get(
        client,
        SEARCH_PULSES_PATH,
        {"q": query, "limit": page_size, "page": 1},
        retries,
        retry_delay,
    ):
        results = page.get("results", [])
        if isinstance(results, list):
            pulses.extend(result for result in results if isinstance(result, dict))
        if len(pulses) >= max_pulses:
            break

    return pulses[:max_pulses]


async def get_pulse_indicators_async(
    client: httpx.AsyncClient,
    pulse_id: str,
    page_size: int,
    retries: int,
    retry_delay: float,
) -> list[dict[str, object]]:
    indicators: list[dict[str, object]] = []
    path = PULSE_INDICATORS_PATH.format(pulse_id=pulse_id)

    for page in await paginated_get_async(
        client,
        path,
        {"limit": page_size, "page": 1, "include_inactive": 0},
        retries,
        retry_delay,
    ):
        results = page.get("results", [])
        if isinstance(results, list):
            indicators.extend(result for result in results if isinstance(result, dict))

    return indicators


async def fetch_missing_indicators(
    client: httpx.AsyncClient,
    pulse_ids: list[str],
    page_size: int,
    retries: int,
    retry_delay: float,
    concurrency: int,
) -> IndicatorCache:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def fetch_one(pulse_id: str) -> tuple[str, list[dict[str, object]]]:
        async with semaphore:
            indicators = await get_pulse_indicators_async(client, pulse_id, page_size, retries, retry_delay)
            return pulse_id, indicators

    results = await asyncio.gather(*(fetch_one(pulse_id) for pulse_id in pulse_ids))
    return dict(results)


def indicators_from_pulse(pulse: dict[str, object]) -> list[dict[str, object]] | None:
    indicators = pulse.get("indicators")
    if isinstance(indicators, list):
        return [indicator for indicator in indicators if isinstance(indicator, dict)]
    return None


def indicator_created(indicator: dict[str, object]) -> str:
    for key in ("created", "created_on", "date_added", "first_seen"):
        raw = indicator.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def pulse_name_of(pulse: dict[str, object]) -> str:
    for key in ("name", "title"):
        raw = pulse.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def build_domain_rows_for_actor(
    actor: str,
    pulses: list[dict[str, object]],
    indicators_by_pulse: IndicatorCache,
    indicator_types: set[str],
) -> list[dict[str, str]]:
    pulse_by_id: dict[str, dict[str, object]] = {}
    for pulse in pulses:
        pid = str(pulse.get("id") or "")
        if pid:
            pulse_by_id[pid] = pulse

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for pulse_id, indicators in indicators_by_pulse.items():
        pulse = pulse_by_id.get(pulse_id, {})
        pname = pulse_name_of(pulse)
        for indicator in indicators:
            indicator_type = str(indicator.get("type") or "").strip().lower()
            if indicator_type not in indicator_types:
                continue
            domain = str(indicator.get("indicator") or "").strip()
            if not domain:
                continue
            created = indicator_created(indicator)
            dedupe_key = (pulse_id, domain.lower(), created)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "domain": domain,
                    "actor": actor,
                    "pulse_id": pulse_id,
                    "pulse_name": pname,
                    "created": created,
                }
            )

    return rows


async def export_actor_domain_iocs(
    client: httpx.Client,
    async_client: httpx.AsyncClient,
    actor: str,
    page_size: int,
    max_pulses: int,
    indicator_types: set[str],
    retries: int,
    retry_delay: float,
    concurrency: int,
    cache: IndicatorCache,
) -> list[dict[str, str]]:
    pulses = search_actor_pulses(client, actor, page_size, max_pulses, retries, retry_delay)
    indicators_by_pulse: IndicatorCache = {}
    missing_pulse_ids: list[str] = []
    seen_pulse_ids: set[str] = set()

    for pulse in pulses:
        pulse_id = str(pulse.get("id") or "")
        if not pulse_id or pulse_id in seen_pulse_ids:
            continue
        seen_pulse_ids.add(pulse_id)

        embedded = indicators_from_pulse(pulse)
        if embedded is not None:
            indicators_by_pulse[pulse_id] = embedded
            cache[pulse_id] = embedded
        elif pulse_id in cache:
            indicators_by_pulse[pulse_id] = cache[pulse_id]
        else:
            missing_pulse_ids.append(pulse_id)

    if missing_pulse_ids:
        fetched = await fetch_missing_indicators(
            async_client,
            missing_pulse_ids,
            page_size,
            retries,
            retry_delay,
            concurrency,
        )
        indicators_by_pulse.update(fetched)
        cache.update(fetched)

    return build_domain_rows_for_actor(actor, pulses, indicators_by_pulse, indicator_types)


def write_csv_header_only(path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def append_csv_rows(path: Path, rows: Iterable[dict[str, str]], write_header: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DOMAIN_CSV_FIELDS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_cache(path: Path | None) -> IndicatorCache:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {
        str(pulse_id): [indicator for indicator in indicators if isinstance(indicator, dict)]
        for pulse_id, indicators in data.items()
        if isinstance(indicators, list)
    }


def save_cache(path: Path | None, cache: IndicatorCache) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def load_actors_from_csv(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames or "actor" not in fieldnames:
            return set()
        return {str(r.get("actor", "")).strip() for r in reader if r.get("actor")}


def prepare_csv_for_pass(args: argparse.Namespace, loop_idx: int, will_write_rows: bool) -> None:
    if not args.output_csv:
        return
    path = args.output_csv
    if args.truncate_each_loop:
        if will_write_rows:
            write_csv_header_only(path, DOMAIN_CSV_FIELDS)
        return
    if loop_idx > 1:
        return
    exists_nonempty = path.exists() and path.stat().st_size > 0
    if args.append_csv and exists_nonempty:
        return
    write_csv_header_only(path, DOMAIN_CSV_FIELDS)


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.otx_api_key:
        print("Missing OTX_API_KEY. Put it in .env or export it before running.", file=sys.stderr)
        return 2

    indicator_types = set(DOMAIN_TYPES)
    if args.include_hostname:
        indicator_types.add("hostname")

    retries = args.retries if args.retries is not None else settings.max_retries
    retry_delay = args.retry_delay if args.retry_delay is not None else settings.retry_base_delay
    cache = load_cache(args.cache_file)
    save_every = max(1, args.save_cache_every)

    loop_idx = 0
    stdout_header_written = False

    while True:
        loop_idx += 1
        print(f"# pass {loop_idx} starting", file=sys.stderr)

        with make_client(settings.otx_api_key, args.timeout) as client:
            actors = read_actors(args, client, retries, retry_delay)
            if not actors:
                print(
                    "No actors to process. Use --actor, --actors-file, or --discover-actors.",
                    file=sys.stderr,
                )
                return 2

            if args.skip_actors_in_csv and args.output_csv:
                done = load_actors_from_csv(args.output_csv)
                actors = [a for a in actors if a not in done]

            prepare_csv_for_pass(args, loop_idx, bool(actors))

            if not actors:
                print(
                    f"# pass {loop_idx}: no new actors (all already in CSV or empty after skip)",
                    file=sys.stderr,
                )
            else:
                if not args.no_stdout_csv:
                    if not stdout_header_written:
                        stdout_writer = csv.DictWriter(sys.stdout, fieldnames=DOMAIN_CSV_FIELDS)
                        stdout_writer.writeheader()
                        sys.stdout.flush()
                        stdout_header_written = True
                    else:
                        stdout_writer = csv.DictWriter(sys.stdout, fieldnames=DOMAIN_CSV_FIELDS)
                else:
                    stdout_writer = None

                processed = 0
                async with make_async_client(settings.otx_api_key, args.timeout) as async_client:
                    for actor in actors:
                        try:
                            rows = await export_actor_domain_iocs(
                                client=client,
                                async_client=async_client,
                                actor=actor,
                                page_size=args.page_size,
                                max_pulses=args.max_pulses_per_actor,
                                indicator_types=indicator_types,
                                retries=retries,
                                retry_delay=retry_delay,
                                concurrency=args.concurrency,
                                cache=cache,
                            )
                        except httpx.HTTPError as exc:
                            print(f"# actor={actor!r} failed: {exc}", file=sys.stderr)
                            rows = []

                        processed += 1
                        for row in rows:
                            if stdout_writer is not None:
                                stdout_writer.writerow(row)
                        if stdout_writer is not None:
                            sys.stdout.flush()
                        if args.output_csv and rows:
                            append_csv_rows(args.output_csv, rows, write_header=False)

                        if processed % save_every == 0:
                            save_cache(args.cache_file, cache)

                save_cache(args.cache_file, cache)

        if args.output_csv:
            print(f"# pass {loop_idx} finished; CSV: {args.output_csv}", file=sys.stderr)
        if args.cache_file:
            print(f"# pulse cache: {args.cache_file}", file=sys.stderr)

        if not args.loop:
            break

        print(f"# sleeping {args.loop_interval_seconds}s until next pass", file=sys.stderr)
        await asyncio.sleep(max(1, args.loop_interval_seconds))

    return 0


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
