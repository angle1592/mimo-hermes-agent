#!/usr/bin/env python3
"""Generate realistic posture monitoring test data for MySQL.

Usage:
    # Standalone SQL file (includes USE + TRUNCATE)
    python3 seed-posture-data.py --days 7 --sql-file /tmp/seed.sql
    mysql -u root < /tmp/seed.sql

    # Customize
    python3 seed-posture-data.py --days 14 --start-date 2026-05-01 --sql-file /tmp/seed.sql

Generates time-series data simulating a student's daily schedule with
realistic variation: weekday vs weekend profiles, fatigue-based posture
degradation, outdoor periods, and per-day randomness.

Key features:
- Reminder-aware mode (default): abnormal posture happens in discrete short
  episodes (not random per-record), simulating a system with posture alerts.
  Each episode is 30-60s, number decreases over weeks.
  Week 1: 30-45 episodes/day, ~55min abnormal, score ~90
  Week 2: 15-25 episodes/day, ~25min abnormal, score ~96
  Week 3: 5-15 episodes/day, ~8min abnormal, score ~99
- 3-week improvement arc: poor posture → gradual improvement → good habits
- Each day has a unique profile (wake time, sleep time, work intensity)
- Weekend days: later wake, more outdoor time, less structured posture
- Fatigue model: hunchback probability increases with awake hours
- Per-day posture distribution varies meaningfully (not copy-paste)

NOTE: Earlier versions used continuous ratio-based generation which produced
hundreds of abnormal records per day. That's unrealistic for a system with
reminder functionality — users correct posture quickly after being alerted.
The episode-based approach (default) produces ~15-45 reminders/day, which is
plausible for a real deployment.
"""

import random
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta


# Weekly abnormal posture ratios (head_down + hunchback fraction of active records)
# Used in "ratio" mode
WEEK_PROFILES = {
    1: {"hd": 0.22, "hb": 0.13},  # ~35% abnormal → score ~55-65
    2: {"hd": 0.14, "hb": 0.08},  # ~22% abnormal → score ~65-75
    3: {"hd": 0.08, "hb": 0.04},  # ~12% abnormal → score ~75-85
}

# Episode-based profiles for reminder-aware mode (default)
# Each episode = a short burst of abnormal posture (user gets reminded, corrects)
WEEK_EPISODES = {
    1: {"count": (30, 45), "duration": (60, 120), "hd_ratio": 0.55},  # score ~90
    2: {"count": (15, 25), "duration": (40, 80),  "hd_ratio": 0.60},  # score ~96
    3: {"count": (5, 15),  "duration": (20, 45),  "hd_ratio": 0.65},  # score ~99
}


def _generate_day_episodes(date, cfg):
    """Pre-generate abnormal episode time windows for one day."""
    is_weekend = date.weekday() >= 5
    wake = random.uniform(9.0, 10.5) if is_weekend else random.uniform(7.0, 8.5)
    sleep = random.uniform(23.5, 25.0) if is_weekend else random.uniform(23.0, 24.5)
    cnt = random.randint(*cfg["count"])
    episodes = []
    for _ in range(cnt):
        t = random.uniform(wake + 0.3, min(sleep, 24.0) - 0.3)
        dur = random.randint(cfg["duration"][0], cfg["duration"][1])
        ptype = "head_down" if random.random() < cfg["hd_ratio"] else "hunchback"
        episodes.append((t, t + dur / 3600.0, ptype))
    episodes.sort()
    return wake, sleep, episodes


def generate_records(days=21, start_date="2026-04-18", seed=2026, mode="reminder"):
    random.seed(seed)
    base = datetime.strptime(start_date, "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    now = datetime.now().replace(second=0, microsecond=0)
    records = []
    ts = base

    # Pre-generate episode schedules per day (reminder mode)
    day_episodes = {}
    d = base.date()
    while d <= now.date():
        day_off = (d - base.date()).days
        wk = min(day_off // 7 + 1, 3)
        cfg = WEEK_EPISODES[wk]
        day_episodes[d] = _generate_day_episodes(d, cfg)
        d += timedelta(days=1)

    while ts < now:
        day_offset = (ts - base).days
        week_num = min(day_offset // 7 + 1, 3)
        weekday = ts.weekday()
        is_weekend = weekday >= 5

        hour = ts.hour + ts.minute / 60.0 + ts.second / 3600.0
        ms = random.randint(0, 999)
        onenet_ts = ts.replace(microsecond=ms * 1000)

        if mode == "reminder":
            wake, sleep, episodes = day_episodes[ts.date()]

            # Sleeping
            if hour < wake or hour >= sleep:
                records.append(("main", "normal", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=60)
                continue

            # Weekend outdoor (afternoon)
            if is_weekend and 14 <= hour < 17 and random.random() < 0.05:
                records.append(("main", "normal", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=30)
                continue

            # Lunch break
            if 12 <= hour < 13 and random.random() < 0.08:
                records.append(("main", "normal", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=15)
                continue

            # Occasional stand-up
            if random.random() < 0.005:
                records.append(("main", "no_person", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=10)
                continue

            # Check if in an abnormal episode
            pt = "normal"
            for (abn_s, abn_e, abn_t) in episodes:
                if abn_s <= hour < abn_e:
                    pt = abn_t
                    break
                if hour < abn_s:
                    break

        else:  # ratio mode (original)
            cfg = WEEK_PROFILES[week_num]
            wake = random.uniform(9.0, 10.5) if is_weekend else random.uniform(7.0, 8.5)
            sleep = random.uniform(23.5, 25.0) if is_weekend else random.uniform(23.0, 24.5)

            # Sleeping
            if hour < wake or hour >= sleep:
                records.append(("main", "normal", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=60)
                continue

            # Weekend outdoor (afternoon)
            if is_weekend and 14 <= hour < 17 and random.random() < 0.4:
                records.append(("main", "normal", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=30)
                continue

            # Lunch break
            if 12 <= hour < 13 and random.random() < 0.5:
                records.append(("main", "normal", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=15)
                continue

            # Occasional stand-up (bathroom, water)
            if random.random() < 0.04:
                records.append(("main", "no_person", 0, None, 0, onenet_ts, ts))
                ts += timedelta(seconds=10)
                continue

            # Fatigue model: longer awake → worse posture
            awake_hours = hour - wake
            fatigue = min(awake_hours / 10.0, 1.0)
            hd = cfg["hd"] + fatigue * 0.06
            hb = cfg["hb"] + fatigue * 0.04
            n = 1 - hd - hb

            r = random.random()
            if r < n:
                pt = "normal"
            elif r < n + hd:
                pt = "head_down"
            else:
                pt = "hunchback"

        pp = 0 if pt == "no_person" else 1

        # Lighting: daytime bright, evening dim, night fill light
        if 7 <= ts.hour < 18:
            lux = round(random.uniform(40, 120), 1)
            fill = 0
        elif 18 <= ts.hour < 21:
            lux = round(random.uniform(20, 50), 1)
            fill = random.choice([0, 1])
        else:
            lux = round(random.uniform(8, 30), 1)
            fill = 1

        records.append(("main", pt, pp, lux, fill, onenet_ts, ts))
        ts += timedelta(seconds=10)

    return records


def main():
    parser = argparse.ArgumentParser(description="Generate posture test data SQL")
    parser.add_argument("--days", type=int, default=7, help="Number of days (default: 7)")
    parser.add_argument("--start-date", default="2026-05-02", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed")
    parser.add_argument("--mode", choices=["reminder", "ratio"], default="reminder",
                        help="Data mode: 'reminder' (episode-based, realistic) or 'ratio' (continuous)")
    parser.add_argument("--output", "-o", help="Output SQL file (default: stdout)")
    parser.add_argument("--sql-file", help="Generate standalone SQL file with USE + TRUNCATE")
    parser.add_argument("--table", default="posture_records", help="Table name")
    parser.add_argument("--database", default="posture_monitor", help="Database name")
    args = parser.parse_args()

    records = generate_records(args.days, args.start_date, args.seed, args.mode)

    def format_record(r):
        dev, pt, pp, lux, fill, ot, ct = r
        lux_str = "NULL" if lux is None else str(lux)
        return (
            f"('{dev}', '{pt}', {pp}, {lux_str}, {fill}, "
            f"'{ot.strftime('%Y-%m-%d %H:%M:%S')}.{ot.microsecond // 1000:03d}', "
            f"'{ct.strftime('%Y-%m-%d %H:%M:%S')}')"
        )

    values = ",\n".join(format_record(r) for r in records)
    insert_sql = (
        f"INSERT INTO {args.table} "
        f"(device_id, posture_type, person_present, ambient_lux, "
        f"fill_light_on, onenet_time, created_at)\nVALUES\n{values};"
    )

    if args.sql_file:
        sql = f"USE {args.database};\nTRUNCATE TABLE {args.table};\n{insert_sql}\n"
        with open(args.sql_file, "w") as f:
            f.write(sql)
        print(f"Generated {len(records)} records -> {args.sql_file}", file=sys.stderr)
    elif args.output:
        with open(args.output, "w") as f:
            f.write(insert_sql)
        print(f"Generated {len(records)} records -> {args.output}", file=sys.stderr)
    else:
        print(insert_sql)
        print(f"-- Generated {len(records)} records", file=sys.stderr)

    # Stats
    day_stats = defaultdict(lambda: Counter())
    for r in records:
        day_stats[r[5].date()][r[1]] += 1
    weekdays = "一二三四五六日"

    print(f"\nTotal: {len(records)} records", file=sys.stderr)
    print(
        f"{'日期':<12} {'周':<2} {'正常':>5} {'低头':>5} {'驼背':>5} "
        f"{'无人':>5} {'异常时长':>8} {'评分':>4}",
        file=sys.stderr,
    )
    for d in sorted(day_stats.keys()):
        n = day_stats[d].get("normal", 0)
        hd = day_stats[d].get("head_down", 0)
        hb = day_stats[d].get("hunchback", 0)
        np_ = day_stats[d].get("no_person", 0)
        scored = n + hd + hb
        score = round(n / scored * 100) if scored else 100
        abn_min = round((hd + hb) * 10 / 60)
        wd = weekdays[d.weekday()]
        print(
            f"{d}  {wd}  {n:>5} {hd:>5} {hb:>5} {np_:>5}  "
            f"{abn_min:>4}分钟 {score:>4}",
            file=sys.stderr,
        )

    # Weekly summary
    print(file=sys.stderr)
    base_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    for wk in range(1, 4):
        ws = base_date + timedelta(days=(wk - 1) * 7)
        we = ws + timedelta(days=7)
        sn = shd = shb = 0
        for d in day_stats:
            if ws <= d < we:
                sn += day_stats[d].get("normal", 0)
                shd += day_stats[d].get("head_down", 0)
                shb += day_stats[d].get("hunchback", 0)
        scored = sn + shd + shb
        score = round(sn / scored * 100) if scored else 0
        abn_avg = (shd + shb) * 10 / 60 / 7
        print(f"第{wk}周: 评分 {score} | 日均异常 {abn_avg:.0f} 分钟", file=sys.stderr)


if __name__ == "__main__":
    main()
