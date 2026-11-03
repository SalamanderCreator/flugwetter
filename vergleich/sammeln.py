#!/usr/bin/env python3
"""Sammelt Daten für den Vergleich Prognose vs. Messung am Markbachjoch Startplatz 1.

  python vergleich/sammeln.py prognose   -> Modellprognosen (Open-Meteo) für heute sichern
  python vergleich/sammeln.py messung    -> 15-Minuten-Messwerte der Holfuy-Station sichern

Die Daten landen in data/prognosen.csv und data/messungen.csv.
Läuft automatisch über GitHub Actions (.github/workflows/vergleich.yml).
"""
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Markbachjoch Startplatz 1 (DHV) – dort steht die Holfuy-Station "FS Wildschönau", 1450 m
LAT, LON = 47.43205, 12.09398
STATION_URL = "https://holfuy.com/de/weather/1186"
TZ = ZoneInfo("Europe/Vienna")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
MODELS = {
    "icon_d2": "ICON-D2",
    "icon_eu": "ICON-EU",
    "meteoswiss_icon_ch1": "ICON-CH1",
    "geosphere_arome_austria": "AROME Austria",
    "meteofrance_arome_france_hd": "AROME France HD",
    "ecmwf_ifs": "ECMWF IFS",
}
UA = {"User-Agent": "flugwetter-vergleich/1.0 (privat, github.com/SalamanderCreator/flugwetter)"}

PROG_FIELDS = ["datum", "modell", "zeit", "wind", "boeen", "richtung", "temp", "abruf"]
MESS_FIELDS = ["zeit", "wind", "boeen", "richtung", "temp"]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def merge_csv(path, fields, rows, key):
    """Neue Zeilen einfügen; vorhandene Zeilen mit gleichem Schlüssel werden ersetzt."""
    data = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                data[key(row)] = row
    for row in rows:
        data[key(row)] = row
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for k in sorted(data):
            w.writerow(data[k])
    return len(rows)


def prognose(now):
    today = now.strftime("%Y-%m-%d")
    rows = []
    for mid, name in MODELS.items():
        url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&elevation=nan&models=%s"
               "&timezone=Europe%%2FVienna&forecast_days=2&wind_speed_unit=kmh"
               "&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m,temperature_2m") % (LAT, LON, mid)
        try:
            j = json.loads(get(url))
        except Exception as e:  # ein ausgefallenes Modell soll die anderen nicht stoppen
            print("Fehler", name, e)
            continue
        if j.get("error"):
            print("Fehler", name, j.get("reason"))
            continue
        h = j["hourly"]
        for i, t in enumerate(h["time"]):
            if not t.startswith(today) or h["wind_speed_10m"][i] is None:
                continue
            rows.append({"datum": today, "modell": name, "zeit": t,
                         "wind": h["wind_speed_10m"][i], "boeen": h["wind_gusts_10m"][i],
                         "richtung": h["wind_direction_10m"][i], "temp": h["temperature_2m"][i],
                         "abruf": now.strftime("%Y-%m-%dT%H:%M")})
    n = merge_csv(os.path.join(DATA, "prognosen.csv"), PROG_FIELDS, rows, lambda r: (r["modell"], r["zeit"]))
    print(n, "Prognosewerte gespeichert")


def _cells(row_html):
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
    return [re.sub(r"<[^>]+>", " ", c.replace("<br>", " ")).strip() for c in cells]


def parse_holfuy(html, now):
    """Liest die 15-Minuten-Tabelle (letzte 8 Stunden) und ordnet jedem Wert Datum und Uhrzeit zu."""
    m = re.search(r'<table class="hour_table">(.*?)</table>', html, re.S)
    if not m:
        raise ValueError("Messwert-Tabelle nicht gefunden – Holfuy-Seite hat sich geändert?")
    rows = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        c = _cells(tr)
        if not c:
            continue
        head = c[0]
        if head.startswith("Zeit"):
            rows["zeit"] = c[1:]
        elif head.startswith("Geschw"):
            rows["wind"] = c[1:]
        elif head.startswith("Böen"):
            rows["boeen"] = c[1:]
        elif head.startswith("Richtung") and "Deg" in head:
            rows["richtung"] = c[1:]
        elif head.startswith("Temp"):
            rows["temp"] = c[1:]
    labels = rows.get("zeit", [])
    times = []
    for lab in labels:
        mm = re.match(r"(\d{1,2}):(\d{2})", lab)
        mh = re.match(r"(\d{1,2})h", lab)
        if mm:
            times.append((int(mm.group(1)), int(mm.group(2))))
        elif mh:
            times.append((int(mh.group(1)), 0))
        else:  # Wochentag (Mon, Tue …) steht für Mitternacht
            times.append((0, 0))
    # Datum rückwärts vom aktuellen Zeitpunkt zuordnen
    out = []
    day = now.date()
    prev = None
    for idx in range(len(times) - 1, -1, -1):
        hm = times[idx]
        if prev is None:
            if hm > (now.hour, now.minute):
                day -= timedelta(days=1)
        elif hm > prev:
            day -= timedelta(days=1)
        prev = hm
        zeit = "%sT%02d:%02d" % (day.isoformat(), hm[0], hm[1])

        def val(key, pattern=r"-?\d+(?:\.\d+)?"):
            arr = rows.get(key, [])
            if idx >= len(arr):
                return ""
            f = re.findall(pattern, arr[idx])
            return f[-1] if f else ""

        out.append({"zeit": zeit, "wind": val("wind"), "boeen": val("boeen"),
                    "richtung": val("richtung", r"\d+(?=°)"), "temp": val("temp")})
    return list(reversed(out))


def messung(now):
    rows = parse_holfuy(get(STATION_URL), now)
    n = merge_csv(os.path.join(DATA, "messungen.csv"), MESS_FIELDS, rows, lambda r: r["zeit"])
    print(n, "Messwerte gespeichert, von", rows[0]["zeit"] if rows else "-", "bis", rows[-1]["zeit"] if rows else "-")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    now = datetime.now(TZ)
    if mode == "prognose":
        prognose(now)
    elif mode == "messung":
        messung(now)
    else:
        print(__doc__)
        sys.exit(1)
