#!/usr/bin/env python3
"""Vergleich Modellprognosen vs. Messungen an vielen Flugorten (Version 2).

  python vergleich/sammeln2.py prognose morgen    # 05:15 MEZ: heute, morgen, übermorgen
  python vergleich/sammeln2.py prognose nachtrag  # 07:15 MEZ: nur Modelle, die um 05:15 fehlten
  python vergleich/sammeln2.py prognose abend     # 17:15 MEZ: morgen und übermorgen
  python vergleich/sammeln2.py messung            # stündlich: Messwerte aller Stationen

Orte und Stationen stehen in vergleich/orte.json.
Alle Zeiten werden in UTC gespeichert. Ablage:
  data/v2/stationen.json                         aufgelöste Koordinaten/Höhen/IDs
  data/v2/prognosen/JJJJ-MM/JJJJ-MM-TT_HHMM_<lauf>.csv.gz   eine Datei je Abruf
  data/v2/messungen/JJJJ-MM/JJJJ-MM-TT_<quelle>.csv          eine Datei je Tag und Quelle
"""
import csv
import gzip
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data", "v2")
LOCAL = ZoneInfo("Europe/Berlin")
UTC = timezone.utc
UA = {"User-Agent": "flugwetter-vergleich/2.0 (privat, github.com/SalamanderCreator/flugwetter)"}

# ---------------------------------------------------------------- Modelle & Größen
MODELS = [  # Morgenlauf: alle Modelle (regionale Modelle liefern nur in ihrem Gebiet)
    "icon_d2", "icon_eu",
    "meteoswiss_icon_ch1", "meteoswiss_icon_ch2",
    "geosphere_arome_austria", "meteofrance_arome_france_hd",
    "knmi_harmonie_arome_europe", "dmi_harmonie_arome_europe",
    "italia_meteo_arpae_icon_2i",
    "ecmwf_ifs", "ecmwf_aifs025_single", "gfs_seamless",
]
MODELS_ABEND = ["icon_d2", "icon_eu", "meteoswiss_icon_ch2", "knmi_harmonie_arome_europe", "ecmwf_ifs", "gfs_seamless"]
# Open-Meteo-Name -> Spaltenname (20 Größen = Gewicht 2 je Ort im Open-Meteo-Kontingent)
FC_VARS = {
    "wind_speed_10m": "wind", "wind_gusts_10m": "boeen", "wind_direction_10m": "richtung",
    "temperature_2m": "temp", "dew_point_2m": "taupunkt", "relative_humidity_2m": "rf",
    "precipitation": "niederschlag", "weather_code": "wetter",
    "cloud_cover": "wolken", "cloud_cover_low": "wolken_tief", "cloud_cover_mid": "wolken_mittel", "cloud_cover_high": "wolken_hoch",
    "shortwave_radiation": "strahlung", "sunshine_duration": "sonne", "surface_pressure": "druck",
    "cape": "cape", "boundary_layer_height": "grenzschicht", "freezing_level_height": "nullgrad",
    "wind_speed_850hPa": "wind_850", "wind_direction_850hPa": "richtung_850",
}
FC_FIELDS = ["abruf", "lauf", "modell", "ort", "zeit", "vorlauf_h", "modellhoehe"] + list(FC_VARS.values())
HOURS_UTC = range(3, 21)  # 04–22 Uhr MEZ – Flugtag inkl. Dämmerung

OBS_FIELDS = ["zeit", "ort", "quelle", "station", "intervall_min", "wind", "boeen", "richtung", "temp", "taupunkt", "rf",
              "niederschlag", "sonne_min", "strahlung", "druck", "druck_meer", "bewoelkung", "sicht_km",
              "wolkenbasis1", "wolkenmenge1", "wolkenbasis2", "wolkenmenge2"]


# ---------------------------------------------------------------- Hilfsfunktionen
def get(url, binary=False, tries=3):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                raise
            last = e
        except Exception as e:  # Netzwerkfehler: kurz warten, erneut versuchen
            last = e
        time.sleep(3 * (k + 1))
    raise last


def r1(v, nd=1):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    if math.isnan(f):
        return ""
    return round(f, nd) if nd else int(round(f))


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")


def dist_km(a, b, c, d):
    r = math.pi / 180
    h = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def load_orte():
    with open(os.path.join(HERE, "orte.json"), encoding="utf-8") as f:
        return json.load(f)["orte"]


def write_daily(quelle, rows):
    """Messwerte in Tagesdateien je Quelle einsortieren (Duplikate werden ersetzt)."""
    by_day = {}
    for r in rows:
        by_day.setdefault(r["zeit"][:10], []).append(r)
    total = 0
    for day, rs in by_day.items():
        path = os.path.join(DATA, "messungen", day[:7], f"{day}_{quelle}.csv")
        data = {}
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    data[(row["ort"], row["zeit"])] = row
        for r in rs:
            full = {k: r.get(k, "") for k in OBS_FIELDS}
            full["quelle"] = quelle
            data[(full["ort"], full["zeit"])] = full
            total += 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OBS_FIELDS, lineterminator="\n")
            w.writeheader()
            for k in sorted(data):
                w.writerow(data[k])
    return total


# ---------------------------------------------------------------- Stationen auflösen (Koordinaten, Höhen, DWD-IDs)
def resolve_stations(orte):
    path = os.path.join(DATA, "stationen.json")
    cache = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    need = [o for o in orte if o["id"] not in cache]
    arso = dmi_meta = dwd_list = None
    for o in need:
        info = {"lat": o.get("lat"), "lon": o.get("lon"), "hoehe": o.get("hoehe"), "station": o["station"]}
        try:
            if o["quelle"] == "arso":
                arso = arso or parse_arso(get(ARSO_URL))
                s = arso.get(o["station"])
                if s:
                    info.update(lat=s["lat"], lon=s["lon"], hoehe=s["hoehe"])
            elif o["quelle"] == "dmi":
                j = json.loads(get(f"https://opendataapi.dmi.dk/v2/metObs/collections/station/items?stationId={o['station']}&status=Active"))
                feats = j.get("features", [])
                if feats:
                    lon, lat = feats[-1]["geometry"]["coordinates"][:2]
                    info.update(lat=lat, lon=lon, hoehe=feats[-1]["properties"].get("stationHeight"))
            elif o["quelle"] == "dwd":
                dwd_list = dwd_list or parse_dwd_stations(get(DWD_BASE + "wind/now/zehn_now_ff_Beschreibung_Stationen.txt"))
                s = dwd_find(dwd_list, o["station"], o.get("lat"), o.get("lon"))
                if s:
                    info.update(station=s["id"], name_dwd=s["name"], lat=s["lat"], lon=s["lon"], hoehe=s["hoehe"])
            elif o["quelle"] == "holfuy" and not o.get("hoehe"):
                html = get(f"https://holfuy.com/de/weather/{o['station']}")
                m = re.search(r"(\d{2,4})\s*m\s*\(AMSL\)", html)
                if m:
                    info["hoehe"] = int(m.group(1))
                time.sleep(1)
        except Exception as e:
            print("Station nicht aufgelöst:", o["id"], e)
        if o["quelle"] == "dwd" and not re.fullmatch(r"\d{5}", str(info.get("station"))):
            print("DWD-Station nicht gefunden:", o["station"])
            continue
        if info.get("lat") is not None:
            cache[o["id"]] = info
            print("Station aufgelöst:", o["id"], info)
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
    return cache


# ---------------------------------------------------------------- Prognosen (Open-Meteo)
def fetch_model(model, pts):
    """Viele Orte je Anfrage. Deckt das Modell nicht alle Orte ab, wird die Gruppe halbiert, bis nur noch
    gültige Orte übrig sind. Gedrosselt auf ca. 500 gewichtete Abrufe pro Minute (Open-Meteo-Grenze 600)."""
    def url(sub):
        q = {
            "latitude": ",".join(str(p["lat"]) for p in sub), "longitude": ",".join(str(p["lon"]) for p in sub),
            "elevation": ",".join("nan" for _ in sub), "models": model, "timezone": "UTC",
            "forecast_days": 4, "wind_speed_unit": "kmh", "hourly": ",".join(FC_VARS),
        }
        return "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q, safe=",")

    out = []

    def run(sub):
        try:
            j = json.loads(get(url(sub)))
            ok = not (isinstance(j, dict) and j.get("error"))
        except Exception:
            j, ok = None, False
        time.sleep(len(sub) * 2 / 500 * 60)
        if ok:
            out.extend(zip(sub, j if isinstance(j, list) else [j]))
        elif len(sub) > 1:
            run(sub[:len(sub) // 2]); run(sub[len(sub) // 2:])
    for k in range(0, len(pts), 80):
        run(pts[k:k + 80])
    return out


def prognose(lauf, orte, st, now):
    today = now.astimezone(LOCAL).date()
    if lauf == "abend":
        days = {today + timedelta(days=1), today + timedelta(days=2)}
    else:
        days = {today, today + timedelta(days=1), today + timedelta(days=2)}
    pts = [{"id": o["id"], "lat": st[o["id"]]["lat"], "lon": st[o["id"]]["lon"]} for o in orte if o["id"] in st]

    have = set()
    if lauf == "nachtrag":  # nur Modelle nachholen, die im Morgenlauf fehlten
        mdir = os.path.join(DATA, "prognosen", now.strftime("%Y-%m"))
        for fn in sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []:
            if fn.startswith(today.isoformat()) and "_morgen" in fn:
                with gzip.open(os.path.join(mdir, fn), "rt", encoding="utf-8") as f:
                    have |= {(r["modell"], r["ort"]) for r in csv.DictReader(f)}

    rows, summary = [], {}
    for model in (MODELS_ABEND if lauf == "abend" else MODELS):
        todo = [p for p in pts if (model, p["id"]) not in have]
        if not todo:
            continue
        n = 0
        for p, j in fetch_model(model, todo):
            h = j.get("hourly") or {}
            times = h.get("time") or []
            for i, t in enumerate(times):
                dt = datetime.fromisoformat(t).replace(tzinfo=UTC)
                if dt.hour not in HOURS_UTC or dt.astimezone(LOCAL).date() not in days:
                    continue
                if (h.get("wind_speed_10m") or [None])[i] is None and (h.get("temperature_2m") or [None])[i] is None:
                    continue
                row = {"abruf": iso(now), "lauf": lauf, "modell": model, "ort": p["id"], "zeit": iso(dt),
                       "vorlauf_h": int((dt - now).total_seconds() // 3600), "modellhoehe": r1(j.get("elevation"), 0)}
                for om, col in FC_VARS.items():
                    arr = h.get(om)
                    v = arr[i] if arr and i < len(arr) else None
                    row[col] = r1(v, 0 if col in ("wetter", "rf", "wolken", "wolken_tief", "wolken_mittel", "wolken_hoch", "richtung",
                                                 "richtung_850", "grenzschicht", "nullgrad", "cape", "sonne") else 1)
                rows.append(row)
                n += 1
        summary[model] = n
    if not rows:
        print("Nachtrag: nichts nachzuholen" if lauf == "nachtrag" else "Keine Prognosedaten erhalten")
        return
    path = os.path.join(DATA, "prognosen", now.strftime("%Y-%m"), f"{now.strftime('%Y-%m-%d_%H%M')}_{lauf}.csv.gz")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FC_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "Prognosewerte gespeichert:", ", ".join(f"{k} {v}" for k, v in summary.items()))


# ---------------------------------------------------------------- Messungen: Holfuy
def parse_holfuy(html, now_local):
    """15-Minuten-Tabelle (letzte ~8 h) der öffentlichen Stationsseite; Zeiten lokal -> UTC."""
    m = re.search(r'<table class="hour_table">(.*?)</table>', html, re.S)
    if not m:
        raise ValueError("Holfuy-Tabelle nicht gefunden")
    rows = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        c = [re.sub(r"<[^>]+>", " ", x.replace("<br>", " ")).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not c:
            continue
        h = c[0]
        key = ("zeit" if h.startswith("Zeit") else "wind" if h.startswith("Geschw") else "boeen" if h.startswith("Böen")
               else "richtung" if h.startswith("Richtung") and "Deg" in h else "temp" if h.startswith("Temp") else None)
        if key:
            rows[key] = c[1:]
    times = []
    for lab in rows.get("zeit", []):
        a, b = re.match(r"(\d{1,2}):(\d{2})", lab), re.match(r"(\d{1,2})h", lab)
        times.append((int(a.group(1)), int(a.group(2))) if a else (int(b.group(1)), 0) if b else (0, 0))
    out, day, prev = [], now_local.date(), None
    for idx in range(len(times) - 1, -1, -1):
        hm = times[idx]
        if (prev is None and hm > (now_local.hour, now_local.minute)) or (prev is not None and hm > prev):
            day -= timedelta(days=1)
        prev = hm
        dt = datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=now_local.tzinfo)

        def val(k, pat=r"-?\d+(?:\.\d+)?"):
            arr = rows.get(k, [])
            f = re.findall(pat, arr[idx]) if idx < len(arr) else []
            return f[-1] if f else ""
        out.append({"zeit": iso(dt), "intervall_min": 15, "wind": val("wind"), "boeen": val("boeen"),
                    "richtung": val("richtung", r"\d+(?=°)"), "temp": val("temp")})
    return list(reversed(out))


def obs_holfuy(orte, st, now):
    rows = []
    for o in orte:
        try:
            for r in parse_holfuy(get(f"https://holfuy.com/de/weather/{o['station']}"), now.astimezone(LOCAL)):
                r.update(ort=o["id"], station=o["station"])
                rows.append(r)
        except Exception as e:
            print("Holfuy Fehler", o["id"], e)
        time.sleep(2)
    return rows


# ---------------------------------------------------------------- Messungen: OpenWindMap (Pioupiou/Windbird)
def obs_owm(orte, st, now):
    rows = []
    for o in orte:
        try:
            j = json.loads(get(f"https://api.pioupiou.fr/v1/archive/{o['station']}?start=last-day&stop=now&format=json"))
            leg = j["legend"]
            ix = {k: leg.index(k) for k in ("time", "wind_speed_avg", "wind_speed_max", "wind_heading")}
            for d in j.get("data", []):
                t = datetime.fromisoformat(d[ix["time"]].replace("Z", "+00:00"))
                rows.append({"zeit": iso(t), "ort": o["id"], "station": o["station"], "intervall_min": 4,
                             "wind": r1(d[ix["wind_speed_avg"]]), "boeen": r1(d[ix["wind_speed_max"]]), "richtung": r1(d[ix["wind_heading"]], 0)})
        except Exception as e:
            print("OpenWindMap Fehler", o["id"], e)
        time.sleep(1)
    return rows


# ---------------------------------------------------------------- Messungen: GeoSphere Austria (TAWES, 10 min)
GEO_PAR = {"FF": "wind", "FFX": "boeen", "DD": "richtung", "TL": "temp", "TP": "taupunkt", "RF": "rf",
           "RR": "niederschlag", "SO": "sonne_min", "GLOW": "strahlung", "P": "druck", "PRED": "druck_meer"}


def obs_geosphere(orte, st, now):
    ids = {o["station"]: o["id"] for o in orte}
    start, end = iso(now - timedelta(hours=7)), iso(now)
    url = ("https://dataset.api.hub.geosphere.at/v1/station/historical/tawes-v1-10min?parameters=" + ",".join(GEO_PAR) +
           "&station_ids=" + ",".join(ids) + f"&start={start}&end={end}&output_format=geojson")
    j = json.loads(get(url))
    times = j["timestamps"]
    rows = []
    for feat in j["features"]:
        sid = str(feat["properties"]["station"])
        par = feat["properties"]["parameters"]
        for i, t in enumerate(times):
            r = {"zeit": iso(datetime.fromisoformat(t)), "ort": ids.get(sid, sid), "station": sid, "intervall_min": 10}
            for k, col in GEO_PAR.items():
                v = par.get(k, {}).get("data", [None] * len(times))[i]
                if v is None:
                    r[col] = ""
                elif col in ("wind", "boeen"):
                    r[col] = r1(v * 3.6)  # m/s -> km/h
                elif col == "sonne_min":
                    r[col] = r1(v / 60)   # s -> min
                else:
                    r[col] = r1(v)
            if r["wind"] != "" or r["temp"] != "":
                rows.append(r)
    return rows


# ---------------------------------------------------------------- Messungen: ARSO Slowenien (aktueller Stand, stündlich gesammelt)
ARSO_URL = "https://meteo.arso.gov.si/uploads/probase/www/observ/surface/text/sl/observationAms_si_latest.xml"


def _tag(seg, name):
    m = re.search(rf"<{name}>([^<]*)</{name}>", seg)
    return m.group(1).strip() if m else ""


def parse_arso(xml):
    out = {}
    for seg in re.findall(r"<metData>(.*?)</metData>", xml, re.S):
        sid = _tag(seg, "domain_meteosiId")
        try:
            t = datetime.strptime(_tag(seg, "tsValid_issued_UTC").replace(" UTC", ""), "%d.%m.%Y %H:%M").replace(tzinfo=UTC)
        except ValueError:
            continue
        nn = _tag(seg, "nn_val")
        out[sid] = {
            "lat": r1(_tag(seg, "domain_lat"), 4), "lon": r1(_tag(seg, "domain_lon"), 4), "hoehe": r1(_tag(seg, "domain_altitude"), 0),
            "row": {"zeit": iso(t), "station": sid, "intervall_min": 30,
                    "wind": r1(_tag(seg, "ffavg_val_kmh") or _tag(seg, "ff_val_kmh")), "boeen": r1(_tag(seg, "ffmax_val_kmh")),
                    "richtung": r1(_tag(seg, "ddavg_val") or _tag(seg, "dd_val"), 0), "temp": r1(_tag(seg, "t")),
                    "taupunkt": r1(_tag(seg, "td")), "rf": r1(_tag(seg, "rh"), 0), "niederschlag": r1(_tag(seg, "rr_val")),
                    "strahlung": r1(_tag(seg, "gSunRadavg") or _tag(seg, "gSunRad"), 0), "druck": r1(_tag(seg, "p")),
                    "druck_meer": r1(_tag(seg, "msl")),
                    "bewoelkung": r1(float(nn) * 0.8, 1) if nn else "",   # ARSO: Zehntel*? -> Achtel (Rohwert 0–10)
                    "sicht_km": r1(_tag(seg, "vis_val")),
                    # Wolkenschichten: Höhe wie von ARSO geliefert (Rohwert), Menge in Achtel
                    "wolkenbasis1": _tag(seg, "hhs1_val"), "wolkenmenge1": r1(float(_tag(seg, "ns1_val")) * 0.8) if _tag(seg, "ns1_val") else "",
                    "wolkenbasis2": _tag(seg, "hhs2_val"), "wolkenmenge2": r1(float(_tag(seg, "ns2_val")) * 0.8) if _tag(seg, "ns2_val") else ""},
        }
    return out


def obs_arso(orte, st, now):
    data = parse_arso(get(ARSO_URL))
    rows = []
    for o in orte:
        s = data.get(o["station"])
        if s:
            r = dict(s["row"]); r["ort"] = o["id"]
            rows.append(r)
        else:
            print("ARSO Station fehlt:", o["station"])
    return rows


# ---------------------------------------------------------------- Messungen: DMI Dänemark
DMI_PAR = {"wind_speed": "wind", "wind_max": "boeen", "wind_dir": "richtung", "temp_dry": "temp", "temp_dew": "taupunkt",
           "humidity": "rf", "precip_past10min": "niederschlag", "sun_last10min_glob": "sonne_min", "radia_glob": "strahlung",
           "pressure": "druck", "pressure_at_sea": "druck_meer", "cloud_cover": "bewoelkung", "visibility": "sicht_km",
           "cloud_height": "wolkenbasis1"}


def obs_dmi(orte, st, now):
    rows = []
    start = (now - timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:00Z")
    for o in orte:
        try:
            j = json.loads(get(f"https://opendataapi.dmi.dk/v2/metObs/collections/observation/items?stationId={o['station']}&datetime={start}/..&limit=10000"))
            by_t = {}
            for f in j.get("features", []):
                p = f["properties"]
                col = DMI_PAR.get(p["parameterId"])
                if not col:
                    continue
                v = p["value"]
                if col in ("wind", "boeen"):
                    v = v * 3.6
                elif col == "bewoelkung":
                    v = v / 12.5          # % -> Achtel
                elif col == "sicht_km":
                    v = v / 1000
                t = iso(datetime.fromisoformat(p["observed"].replace("Z", "+00:00")))
                by_t.setdefault(t, {"zeit": t, "ort": o["id"], "station": o["station"], "intervall_min": 10})[col] = r1(v)
            rows.extend(by_t.values())
        except Exception as e:
            print("DMI Fehler", o["id"], e)
        time.sleep(0.5)
    return rows


# ---------------------------------------------------------------- Messungen: DWD (10 min, "now" = heutiger Tag)
DWD_BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/"
DWD_FILES = {  # Ordner, Dateikürzel, Spalten -> (Feld, Umrechnung)
    "wind": ("wind/now/", "wind", {"FF_10": ("wind", 3.6), "DD_10": ("richtung", 1)}),
    "extreme_wind": ("extreme_wind/now/", "extrema_wind", {"FX_10": ("boeen", 3.6)}),
    "air_temperature": ("air_temperature/now/", "TU", {"TT_10": ("temp", 1), "TD_10": ("taupunkt", 1), "RF_10": ("rf", 1), "PP_10": ("druck", 1)}),
    "precipitation": ("precipitation/now/", "nieder", {"RWS_10": ("niederschlag", 1)}),
    "solar": ("solar/now/", "SOLAR", {"GS_10": ("strahlung", 10000 / 600), "SD_10": ("sonne_min", 60)}),  # J/cm² -> W/m², h -> min
}


def parse_dwd_stations(txt):
    out = []
    for line in txt.splitlines():
        m = re.match(r"\s*(\d{5})\s+(\d{8})\s+(\d{8})\s+(-?\d+)\s+([\d.]+)\s+([\d.]+)\s+(.+?)\s{2,}", line)
        if m:
            out.append({"id": m.group(1), "bis": m.group(3), "hoehe": int(m.group(4)), "lat": float(m.group(5)),
                        "lon": float(m.group(6)), "name": m.group(7).strip()})
    return out


def dwd_find(stations, name, lat, lon):
    cand = [s for s in stations if name.lower() in s["name"].lower()]
    if not cand and lat is not None:  # Name nicht gefunden: nur Stationen im Umkreis von 15 km
        cand = [s for s in stations if dist_km(lat, lon, s["lat"], s["lon"]) < 15]
    if not cand:
        return None
    cand.sort(key=lambda s: (-(s["bis"] >= datetime.now().strftime("%Y%m%d")), dist_km(lat or s["lat"], lon or s["lon"], s["lat"], s["lon"])))
    return cand[0]


def parse_dwd_csv(text, cols):
    lines = [l for l in text.splitlines() if l.strip()]
    head = [h.strip() for h in lines[0].split(";")]
    res = {}
    for l in lines[1:]:
        v = [x.strip() for x in l.split(";")]
        if len(v) < len(head):
            continue
        d = dict(zip(head, v))
        try:
            t = datetime.strptime(d["MESS_DATUM"], "%Y%m%d%H%M").replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        r = res.setdefault(iso(t), {})
        for c, (field, fac) in cols.items():
            x = d.get(c)
            if x in (None, "", "-999"):
                continue
            try:
                r[field] = r1(float(x) * fac, 0 if field == "richtung" else 1)
            except ValueError:
                pass
    return res


def obs_dwd(orte, st, now):
    rows = {}
    for o in orte:
        sid = st.get(o["id"], {}).get("station")
        if not sid or not re.fullmatch(r"\d{5}", str(sid)):
            print("DWD Station unbekannt:", o["id"])
            continue
        for key, (folder, short, cols) in DWD_FILES.items():
            url = f"{DWD_BASE}{folder}10minutenwerte_{short}_{sid}_now.zip"
            try:
                z = zipfile.ZipFile(io.BytesIO(get(url, binary=True)))
                name = next(n for n in z.namelist() if n.lower().endswith(".txt"))
                for t, vals in parse_dwd_csv(z.read(name).decode("latin-1"), cols).items():
                    r = rows.setdefault((o["id"], t), {"zeit": t, "ort": o["id"], "station": sid, "intervall_min": 10})
                    r.update(vals)
            except Exception as e:
                print("DWD", key, o["id"], "nicht verfügbar:", e)
            time.sleep(0.3)
    # nur die letzten 8 Stunden schreiben (die Datei enthält den ganzen Tag)
    cut = iso(now - timedelta(hours=8))
    return [r for r in rows.values() if r["zeit"] >= cut]


OBS = {"holfuy": obs_holfuy, "owm": obs_owm, "geosphere": obs_geosphere, "arso": obs_arso, "dmi": obs_dmi, "dwd": obs_dwd}
# Abrufrhythmus (UTC-Stunde % n == 0); ARSO bietet nur den aktuellen Stand -> jede Stunde
EVERY_H = {"holfuy": 6, "owm": 6, "geosphere": 3, "arso": 1, "dmi": 3, "dwd": 3}


def messung(orte, st, now, force=False):
    for q, fn in OBS.items():
        if not force and now.hour % EVERY_H[q] != 0:
            continue
        sub = [o for o in orte if o["quelle"] == q]
        if not sub:
            continue
        try:
            rows = fn(sub, st, now)
            print(q, write_daily(q, rows), "Messwerte gespeichert")
        except Exception as e:
            print("Fehler bei", q, e)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    orte = load_orte()
    st = resolve_stations(orte)
    if mode == "prognose":
        prognose(sys.argv[2] if len(sys.argv) > 2 else "morgen", orte, st, now)
    elif mode == "messung":
        messung(orte, st, now, force=len(sys.argv) > 2 and sys.argv[2] == "alle")
    else:
        print(__doc__)
        sys.exit(1)
