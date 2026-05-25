#!/usr/bin/env python3
"""Seed `weather_obs` from Open-Meteo Marine.

Run this once (or on demand) to backfill / top up. The n8n workflow
`marine-weather-isafjordur` keeps it fresh on a 30-min cron from then on.
"""
import json
import os
import subprocess
import sys
import urllib.request

LAT = os.environ.get("MARINE_LAT", "66.20")
LON = os.environ.get("MARINE_LON", "-23.20")
STATION = os.environ.get("MARINE_STATION", "open-meteo:isafjardardjup")
PAST_DAYS = os.environ.get("PAST_DAYS", "2")
FORECAST_DAYS = os.environ.get("FORECAST_DAYS", "2")

VARS = [
    "wave_height", "wave_period", "wave_direction",
    "swell_wave_height", "swell_wave_period", "swell_wave_direction",
    "ocean_current_velocity", "ocean_current_direction",
    "sea_surface_temperature",
]

URL = (
    f"https://marine-api.open-meteo.com/v1/marine"
    f"?latitude={LAT}&longitude={LON}"
    f"&hourly={','.join(VARS)}"
    f"&past_days={PAST_DAYS}&forecast_days={FORECAST_DAYS}"
    f"&timezone=UTC&cell_selection=sea"
)

print(f"[seed-weather] GET {URL}", file=sys.stderr)

with urllib.request.urlopen(URL, timeout=30) as resp:
    payload = json.load(resp)

h = payload["hourly"]
times = h["time"]
n = len(times)
print(f"[seed-weather] {n} hourly rows ({times[0]} → {times[-1]})", file=sys.stderr)


def lit(v):
    if v is None:
        return "NULL"
    return str(v)


sql_lines = []
for i in range(n):
    vals = [
        f"'{STATION}'",
        f"'{times[i]}:00Z'::timestamp",
        lit(h["wave_height"][i]),
        lit(h["wave_period"][i]),
        lit(h["wave_direction"][i]),
        lit(h["swell_wave_height"][i]),
        lit(h["swell_wave_period"][i]),
        lit(h["swell_wave_direction"][i]),
        lit(h["ocean_current_velocity"][i]),
        lit(h["ocean_current_direction"][i]),
        lit(h["sea_surface_temperature"][i]),
    ]
    cols = (
        "station, ts, wave_h_m, wave_period_s, wave_dir, "
        "swell_h_m, swell_period_s, swell_dir, "
        "current_v_ms, current_dir, sea_temp_c"
    )
    sql_lines.append(
        f"INSERT INTO weather_obs ({cols}) VALUES ({', '.join(vals)}) "
        f"ON CONFLICT (station, ts) DO UPDATE SET "
        f"wave_h_m=EXCLUDED.wave_h_m, wave_period_s=EXCLUDED.wave_period_s, "
        f"wave_dir=EXCLUDED.wave_dir, swell_h_m=EXCLUDED.swell_h_m, "
        f"swell_period_s=EXCLUDED.swell_period_s, swell_dir=EXCLUDED.swell_dir, "
        f"current_v_ms=EXCLUDED.current_v_ms, current_dir=EXCLUDED.current_dir, "
        f"sea_temp_c=EXCLUDED.sea_temp_c;"
    )

sql = "\n".join(sql_lines) + "\n"

print(sql)
