#!/usr/bin/env python3
# powerguard_rest_temps.py
#
# Print PowerGuard REST cycles (Outlet OFF -> Outlet ON) with Tilt + Onewire temps
# immediately before the OFF and immediately after the ON.
#
# Example:
#   python powerguard_rest_temps.py tfdeux.log --controller Fridge --actor Cooling --outlet 3
#
# Optional:
#   --max-gap-sec 600   # only use sensor readings within +/- this many seconds of boundary
#
# Output columns:
#   Controller | OFF_ts | Tilt_before | Onewire_before | ON_ts | Tilt_after | Onewire_after | Rest_s | dTilt | dOnewire

import argparse
import re
from bisect import bisect_left, bisect_right
from datetime import datetime
from typing import List, Optional, Tuple


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}):")

# Example lines:
# 2026-02-03 05:14:23,041:DEBUG:event:notify Event(source='Tilt', endpoint='temperature', data=52.3)
SENSOR_RE = re.compile(
    r"Event\(source='(?P<source>[^']+)',\s*endpoint='(?P<endpoint>[^']+)',\s*data=(?P<data>[-+]?\d+(\.\d+)?)\)"
)

# Example lines:
# 2026-02-03 05:14:36,541:INFO:GembirdActor:Cooling: Outlet 3 confirmed OFF
OUTLET_RE = re.compile(
    r"GembirdActor:(?P<actor>[^:]+): Outlet (?P<outlet>\d+) confirmed (?P<state>ON|OFF)"
)

# Example lines:
# 2026-02-03 05:14:36,541:INFO:controller:Fridge: PowerGuard MaxOn rest ...
PG_REST_RE = re.compile(
    r"controller:(?P<controller>[^:]+): PowerGuard MaxOn rest"
)


def parse_ts(line: str) -> Optional[datetime]:
    m = TS_RE.match(line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f")


def fmt(v: Optional[float], width: int = 8, prec: int = 2) -> str:
    if v is None:
        return "—".rjust(width)
    return f"{v:{width}.{prec}f}"


def find_last_before(
    series: List[Tuple[datetime, float]],
    t: datetime,
    max_gap_sec: Optional[int],
) -> Optional[float]:
    """Last value at or before t, optionally requiring |t - ts| <= max_gap_sec."""
    if not series:
        return None
    i = bisect_right(series, (t, float("inf"))) - 1
    if i < 0:
        return None
    ts, val = series[i]
    if max_gap_sec is not None:
        gap = abs((t - ts).total_seconds())
        if gap > max_gap_sec:
            return None
    return val


def find_first_after(
    series: List[Tuple[datetime, float]],
    t: datetime,
    max_gap_sec: Optional[int],
) -> Optional[float]:
    """First value at or after t, optionally requiring |ts - t| <= max_gap_sec."""
    if not series:
        return None
    i = bisect_left(series, (t, -float("inf")))
    if i >= len(series):
        return None
    ts, val = series[i]
    if max_gap_sec is not None:
        gap = abs((ts - t).total_seconds())
        if gap > max_gap_sec:
            return None
    return val


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", help="Path to tfdeux.log")
    ap.add_argument("--controller", default="Fridge", help="Controller name (default: Fridge)")
    ap.add_argument("--actor", default="Cooling", help="Actor name in GembirdActor logs (default: Cooling)")
    ap.add_argument("--outlet", type=int, default=3, help="Outlet number (default: 3)")
    ap.add_argument(
        "--max-gap-sec",
        type=int,
        default=None,
        help="If set, require sensor readings to be within this many seconds of OFF/ON boundary",
    )
    args = ap.parse_args()

    # Time series for temps
    tilt_temps: List[Tuple[datetime, float]] = []
    onewire_temps: List[Tuple[datetime, float]] = []

    # Rest cycle boundaries based on outlet OFF/ON
    off_times: List[datetime] = []
    on_times: List[datetime] = []

    # Optional sanity: record PG rest lines (not strictly required for pairing)
    pg_rest_times: List[datetime] = []

    controller = args.controller
    actor = args.actor
    outlet = str(args.outlet)

    with open(args.logfile, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = parse_ts(line)
            if ts is None:
                continue

            # Sensor temps
            sm = SENSOR_RE.search(line)
            if sm:
                source = sm.group("source")
                endpoint = sm.group("endpoint")
                if endpoint == "temperature":
                    try:
                        val = float(sm.group("data"))
                    except ValueError:
                        val = None
                    if val is not None:
                        if source == "Tilt":
                            tilt_temps.append((ts, val))
                        elif source == "Onewire":
                            onewire_temps.append((ts, val))

            # Outlet state changes
            om = OUTLET_RE.search(line)
            if om and om.group("actor") == actor and om.group("outlet") == outlet:
                state = om.group("state")
                if state == "OFF":
                    off_times.append(ts)
                else:
                    on_times.append(ts)

            # PG rest marker lines (controller-scoped)
            pm = PG_REST_RE.search(line)
            if pm and pm.group("controller") == controller:
                pg_rest_times.append(ts)

    # Sort series just in case
    tilt_temps.sort()
    onewire_temps.sort()
    off_times.sort()
    on_times.sort()
    pg_rest_times.sort()

    # Pair each OFF with the next ON after it.
    # (This matches: Outlet OFF confirmed -> (minOff blocks...) -> Outlet ON confirmed)
    pairs: List[Tuple[datetime, datetime]] = []
    on_idx = 0
    for off_ts in off_times:
        while on_idx < len(on_times) and on_times[on_idx] <= off_ts:
            on_idx += 1
        if on_idx < len(on_times):
            pairs.append((off_ts, on_times[on_idx]))
            on_idx += 1  # move past used ON

    # Print
    header = (
        "Controller | REST_OFF timestamp        | Tilt_before | Onewire_before | REST_ON timestamp         "
        "| Tilt_after | Onewire_after | Rest_s |  dTilt | dOnewire"
    )
    print(header)
    print("-" * len(header))

    if not pairs:
        print(f"{controller:<10} | (no OFF->ON rest cycles found for {actor} outlet {outlet})")
        return

    for off_ts, on_ts in pairs:
        tilt_before = find_last_before(tilt_temps, off_ts, args.max_gap_sec)
        one_before = find_last_before(onewire_temps, off_ts, args.max_gap_sec)

        tilt_after = find_first_after(tilt_temps, on_ts, args.max_gap_sec)
        one_after = find_first_after(onewire_temps, on_ts, args.max_gap_sec)

        rest_s = int((on_ts - off_ts).total_seconds())
        dtilt = (tilt_after - tilt_before) if (tilt_after is not None and tilt_before is not None) else None
        done = (one_after - one_before) if (one_after is not None and one_before is not None) else None

        print(
            f"{controller:<10} | {off_ts.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} |"
            f"{fmt(tilt_before)} |{fmt(one_before)} | "
            f"{on_ts.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} |"
            f"{fmt(tilt_after)} |{fmt(one_after)} |"
            f"{rest_s:6d} |{fmt(dtilt, width=7, prec=2)} |{fmt(done, width=9, prec=2)}"
        )


if __name__ == "__main__":
    main()

