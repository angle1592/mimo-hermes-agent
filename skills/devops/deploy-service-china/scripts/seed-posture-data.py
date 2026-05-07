#!/usr/bin/env python3
"""Generate realistic posture monitoring test data for MySQL.

Usage:
    python3 seed_posture_data.py | mysql -u USER -p'PASS' -h 127.0.0.1 DATABASE
    python3 seed_posture_data.py --days 7 --output /tmp/seed.sql

Generates time-series data simulating a student's daily study schedule
with realistic posture distributions, ambient light levels, and fill light states.
"""

import random
import argparse
import sys
from datetime import datetime, timedelta

POSTURE_TYPES = ["normal", "head_down", "hunchback", "no_person"]

# Weighted by time of day: morning=alert, afternoon=tired, evening=most tired
WEIGHTS_BY_SESSION = {
    "morning":   [0.50, 0.22, 0.13, 0.15],  # 8-12: focused
    "afternoon": [0.40, 0.20, 0.25, 0.15],  # 14-18: getting tired
    "evening":   [0.35, 0.25, 0.25, 0.15],  # 20-23: most tired
}

SESSIONS = [(8, 12, "morning"), (14, 18, "afternoon"), (20, 23, "evening")]

def generate_records(days=7, start_date="2026-05-01", seed=42):
    random.seed(seed)
    base = datetime.strptime(start_date, "%Y-%m-%d")
    records = []

    for day_offset in range(days):
        day_start = base + timedelta(days=day_offset)
        for s_start, s_end, session_name in SESSIONS:
            weights = WEIGHTS_BY_SESSION[session_name]
            current = day_start.replace(hour=s_start, minute=random.randint(0, 15))
            end = day_start.replace(hour=s_end, minute=0)

            while current < end:
                pt = random.choices(POSTURE_TYPES, weights=weights)[0]
                person_present = 1 if pt != "no_person" else 0

                # Daytime: 80-350 lux; Night: 5-40 lux
                if 8 <= current.hour < 18:
                    lux = round(random.uniform(80, 350), 1)
                else:
                    lux = round(random.uniform(5, 40), 1)

                fill_light = 1 if lux < 50 else 0
                onenet_time = current.strftime("%Y-%m-%d %H:%M:%S.") + f"{random.randint(0,999):03d}"

                records.append(
                    f"('main', '{pt}', {person_present}, {lux}, {fill_light}, '{onenet_time}')"
                )
                current += timedelta(minutes=random.randint(10, 30))

    return records

def main():
    parser = argparse.ArgumentParser(description="Generate posture test data SQL")
    parser.add_argument("--days", type=int, default=7, help="Number of days (default: 7)")
    parser.add_argument("--start-date", default="2026-05-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--table", default="posture_records", help="Table name")
    args = parser.parse_args()

    records = generate_records(args.days, args.start_date, args.seed)
    sql = f"INSERT INTO {args.table} (device_id, posture_type, person_present, ambient_lux, fill_light_on, onenet_time)\nVALUES\n"
    sql += ",\n".join(records) + ";"

    if args.output:
        with open(args.output, "w") as f:
            f.write(sql)
        print(f"Generated {len(records)} records → {args.output}", file=sys.stderr)
    else:
        print(sql)
        print(f"-- Generated {len(records)} records", file=sys.stderr)

if __name__ == "__main__":
    main()
