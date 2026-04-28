#!/usr/bin/env python3
"""Replay the JSON payloads in data/prod into InfluxDB 3 Core."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "prod"
DEFAULT_HOST = os.getenv("INFLUXDB3_HOST_URL", "http://127.0.0.1:8181")
DEFAULT_DATABASE = os.getenv("INFLUXDB3_DATABASE_NAME", "prod_replay")
DEFAULT_TOKEN = os.getenv("INFLUXDB3_AUTH_TOKEN", "")
DEFAULT_TABLE = "prod_sensor_events"
DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class ReplayTemplate:
    line_prefix: str
    source_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Flatten the JSON files in data/prod and replay them into InfluxDB 3 Core "
            "at a controlled events-per-second rate until interrupted."
        )
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="InfluxDB host URL. Defaults to %(default)s or INFLUXDB3_HOST_URL.",
    )
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help="InfluxDB database name. Defaults to %(default)s or INFLUXDB3_DATABASE_NAME.",
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE,
        help="InfluxDB table name created on first write. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--token",
        default=DEFAULT_TOKEN,
        help="InfluxDB auth token. Optional when auth is disabled.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing JSON payloads to replay. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--events-per-second",
        type=int,
        help="Target number of points to insert per second. If omitted, the script prompts.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Maximum points per write request. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        help="Optional ceiling on total inserted points. Omit to run until interrupted.",
    )
    parser.add_argument(
        "--report-every",
        type=float,
        default=5.0,
        help="Seconds between progress reports. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Use InfluxDB no_sync writes for lower latency.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the line protocol templates and print a summary without writing anything.",
    )
    return parser.parse_args()


def prompt_positive_int(prompt: str) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number greater than zero.", file=sys.stderr)
            continue
        if value <= 0:
            print("Enter a whole number greater than zero.", file=sys.stderr)
            continue
        return value


def escape_measurement(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def escape_tag(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(" ", "\\ ")
        .replace("=", "\\=")
    )


def escape_field_key(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def escape_field_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def normalize_integer(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered == "true":
        return 1
    if lowered in {"false", "flase"}:
        return 0
    if text.startswith("-") and text[1:].isdigit():
        return int(text)
    if text.isdigit():
        return int(text)
    return None


def build_line_prefix(
    table: str,
    tags: Dict[str, str],
    fields: Dict[str, object],
) -> str:
    tag_parts = [
        f"{escape_tag(key)}={escape_tag(value)}"
        for key, value in tags.items()
        if value not in (None, "")
    ]
    field_parts: List[str] = []
    for key, value in fields.items():
        field_key = escape_field_key(key)
        if isinstance(value, bool):
            field_parts.append(f"{field_key}={'true' if value else 'false'}")
        elif isinstance(value, int):
            field_parts.append(f"{field_key}={value}i")
        elif isinstance(value, float):
            field_parts.append(f"{field_key}={value}")
        else:
            field_parts.append(f'{field_key}="{escape_field_string(str(value))}"')

    measurement = escape_measurement(table)
    if tag_parts:
        return f"{measurement},{','.join(tag_parts)} {','.join(field_parts)}"
    return f"{measurement} {','.join(field_parts)}"


def load_templates(data_dir: Path, table: str) -> List[ReplayTemplate]:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    templates: List[ReplayTemplate] = []
    for path in sorted(data_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        location_id = str(payload.get("location_id", ""))
        location_name = str(payload.get("location_name", ""))
        bu = str(payload.get("bu", ""))
        for device_index, device in enumerate(payload.get("data", []), start=1):
            device_tags = {
                "source_file": path.stem,
                "location_id": location_id,
                "location_name": location_name,
                "bu": bu,
                "entity_id": str(device.get("entity_id", "")),
                "device_id": str(device.get("device_id", "")),
                "device_name": str(device.get("device_name", "")),
                "device_type": str(device.get("device_type", "")),
                "device_index": str(device_index),
            }
            for sensor_index, sensor in enumerate(device.get("sensors", []), start=1):
                tags = {
                    **device_tags,
                    "sensor_index": str(sensor_index),
                    "sensor_name": str(sensor.get("sensor_name", "")),
                    "sensor_tag": str(sensor.get("sensor_tag", "")),
                    "sensor_id": str(sensor.get("sensor_id", "")),
                    "sensor_type": str(sensor.get("sensor_type", "")),
                }
                raw_value = str(sensor.get("normal_value", ""))
                fields: Dict[str, object] = {
                    "normal_value_raw": raw_value,
                }
                normalized_value = normalize_integer(raw_value)
                if normalized_value is not None:
                    fields["normal_value_code"] = normalized_value
                templates.append(
                    ReplayTemplate(
                        line_prefix=build_line_prefix(table, tags, fields),
                        source_file=path.name,
                    )
                )

    if not templates:
        raise RuntimeError(f"No JSON templates found under {data_dir}")
    return templates


def write_batch(
    host: str,
    database: str,
    token: str,
    lines: Iterable[str],
    no_sync: bool,
    timeout: float = 30.0,
) -> None:
    query_params = {
        "db": database,
        "precision": "nanosecond",
        "accept_partial": "false",
        "no_sync": "true" if no_sync else "false",
    }
    url = f"{host.rstrip('/')}/api/v3/write_lp?{urllib.parse.urlencode(query_params)}"
    payload = "\n".join(lines).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    request.add_header("Content-Type", "text/plain; charset=utf-8")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if status not in (200, 204):
                raise RuntimeError(f"Unexpected InfluxDB status code: {status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise RuntimeError(
                "InfluxDB rejected the write with HTTP 401. Provide a valid token with "
                "--token or export INFLUXDB3_AUTH_TOKEN before running the replay."
            ) from exc
        raise RuntimeError(
            f"InfluxDB write failed with HTTP {exc.code}: {body.strip()}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"InfluxDB write failed: {exc.reason}") from exc


def replay(args: argparse.Namespace) -> int:
    events_per_second = args.events_per_second or prompt_positive_int(
        "How many events should be inserted per second? "
    )
    if events_per_second <= 0:
        raise ValueError("events-per-second must be greater than zero")
    if args.batch_size <= 0:
        raise ValueError("batch-size must be greater than zero")

    templates = load_templates(args.data_dir, args.table)
    batch_size = min(args.batch_size, events_per_second)
    template_cycle = itertools.cycle(templates)

    print(
        f"Loaded {len(templates):,} point templates from {args.data_dir}. "
        f"Target host={args.host} database={args.database} table={args.table} "
        f"rate={events_per_second:,} events/sec batch_size={batch_size:,}."
    )
    print("Press Ctrl+C to stop the replay.")

    if args.dry_run:
        now_ns = time.time_ns()
        for index, template in enumerate(templates[:3], start=1):
            print(f"[sample {index}] {template.line_prefix} {now_ns + index}")
        return 0

    inserted_total = 0
    started_at = time.monotonic()
    last_report_at = started_at
    next_deadline = started_at

    try:
        while args.max_events is None or inserted_total < args.max_events:
            remaining = None
            if args.max_events is not None:
                remaining = args.max_events - inserted_total
                if remaining <= 0:
                    break
            current_batch_size = (
                min(batch_size, remaining) if remaining is not None else batch_size
            )
            batch_start_ns = time.time_ns()
            lines = [
                f"{next(template_cycle).line_prefix} {batch_start_ns + offset}"
                for offset in range(current_batch_size)
            ]
            write_batch(
                host=args.host,
                database=args.database,
                token=args.token,
                lines=lines,
                no_sync=args.no_sync,
            )
            inserted_total += current_batch_size

            now = time.monotonic()
            if now - last_report_at >= args.report_every:
                elapsed = now - started_at
                rate = inserted_total / elapsed if elapsed > 0 else 0.0
                cycles = inserted_total / len(templates)
                print(
                    f"Inserted {inserted_total:,} points in {elapsed:.1f}s "
                    f"({rate:.1f} points/s average, {cycles:.2f} template cycles)."
                )
                last_report_at = now

            next_deadline += current_batch_size / events_per_second
            sleep_for = next_deadline - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        print("\nReplay stopped by user.")
    finally:
        elapsed = time.monotonic() - started_at
        rate = inserted_total / elapsed if elapsed > 0 else 0.0
        cycles = inserted_total / len(templates) if templates else 0.0
        print(
            f"Final totals: inserted={inserted_total:,} elapsed={elapsed:.1f}s "
            f"average_rate={rate:.1f} points/s template_cycles={cycles:.2f}"
        )

    return 0


def main() -> int:
    args = parse_args()
    try:
        return replay(args)
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint should be blunt.
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
