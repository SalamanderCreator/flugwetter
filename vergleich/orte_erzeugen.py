#!/usr/bin/env python3
"""Erzeugt vergleich/orte.json – nur Stationen direkt an Startplätzen bzw. auf Fluggipfeln."""
import json, os

# id;name;land;lat;lon  (Holfuy, aktive Startplatzstationen, Stand 19.11.2026)
HOLFUY = """1186;Markbachjoch SP1 (FS Wildschönau);AT;47.43173;12.09459
1796;9erköpfle SP West;AT;47.48258;10.54225
723;Arlberg Galzig;AT;47.13519;10.22104
1862;Bischling Startplatz;AT;47.46394;13.29872
1832;Gaisberg SP Ost;AT;47.80483;13.11422
236;Grünberg Gmunden;AT;47.89866;13.81839
738;Hahnenkamm Grat (Reutte);AT;47.47236;10.643
751;Haimburgerberg;AT;46.71838;14.67268
742;Jochdohlen SP;AT;47.1459;11.3072
1423;Jöchelspitze;AT;47.27511;10.3642
645;Marienberg;AT;47.34927;10.8997
1690;Pfunds Startplatz;AT;46.97166;10.49355
877;Pöllauberg;AT;47.31693;15.85832
388;Rofan Startplatz (Achensee);AT;47.44409;11.76381
1686;Michaelerberg;AT;47.41131;13.89338
1248;Schneiderberg;AT;47.51361;12.43212
665;Schöneben SP;AT;47.22779;14.16074
695;Kleinerberg;AT;47.73362;14.36657
770;Thurnhamberg SP;AT;47.87268;14.09257
666;Spielberg;AT;47.21544;14.84706
1485;Spieljoch (Zillertal);AT;47.33237;11.79462
1689;Hochimst Startplatz;AT;47.25589;10.67704
1266;Wildkogel Bramberg;AT;47.28171;12.29148
533;Wolfratshauser Hütte;AT;47.39093;10.84848
2023;Zwölferhorn St. Gilgen;AT;47.74251;13.35143
2043;Omerskopf;DE;48.64086;8.17131
1343;Brauneck;DE;47.66365;11.52303
1810;Blomberg;DE;47.73443;11.50679
676;Breitenberg Pfronten;DE;47.54662;10.56447
511;Buchenberg Buching;DE;47.60642;10.81141
1345;Dieberg;DE;49.3269;12.86913
588;Hesselberg Süd;DE;49.06776;10.52844
1545;Hörnerbahn Gipfel;DE;47.46523;10.20116
1694;Imberger Horn;DE;47.49212;10.37085
1671;Kammeregg SP;DE;47.56586;10.3085
1882;Messelberg Donzdorf;DE;48.67943;9.83887
906;Nebelhorn 1930m;DE;47.41328;10.3471
1541;Obergrainet;DE;48.8014;13.67213
1322;Ochsenberg;DE;47.50688;10.3995
480;Sommerberg;DE;49.0365;12.74732
1063;Spiesshorn;DE;47.82717;8.03332
905;Tegelberg Startplatz;DE;47.55974;10.77982
424;Unternberg Ruhpolding;DE;47.72844;12.63837
1247;Waldstetten Skihütte;DE;48.75276;9.81533
1951;Willingen Ettelsberg;DE;51.27835;8.59978
1376;Hainberg;DE;50.16253;11.52605
537;Hausstein (Deggendorf);DE;48.87104;13.07332
604;Hochfelln Süd;DE;47.76106;12.55959
1061;Predigtstuhl;DE;47.69155;12.88368
685;Wasserkuppe Nord;DE;50.50227;9.94016
466;Rammelsberg;DE;51.88967;10.43149
1404;Donnersberg;DE;49.62063;7.94166
623;Alp Scheidegg Start;CH;47.30376;8.94319
1547;Arosa Weisshorn;CH;46.78927;9.63907
1990;Lagalb Bergstation;CH;46.42971;10.02155
1571;Parpaner Rothorn;CH;46.74282;9.60307
571;Prodkamm;CH;47.07321;9.26763
1125;Schwyberg;CH;46.67731;7.26095
1221;Stockberg;CH;47.22443;9.23846
960;Zugerberg;CH;47.148;8.53599
1638;Riffelberg (Zermatt);CH;45.99124;7.74715
1000;Decollo Malcesine (Monte Baldo);IT;45.76923;10.86437
931;Decollo Colonei;IT;45.65295;10.81001"""

# id;name;lat;lon  (OpenWindMap/Pioupiou, aktive Startplatzstationen)
OWM = """159;Déco Montendry 1282m;45.52909;6.25312
195;Décollage SO de Planoise;47.20465;5.97789
286;Déco de Sodkopf;48.71299;8.1533
309;Décollage des Crêts;46.12978;6.17129
348;Métabief déco Ouest;46.75007;6.344
353;Courchevel Col de la Loze 2300m;45.40761;6.60212
372;Balise du Kemberg;48.25659;6.93201
813;Décollage Téton;45.37083;6.48133
816;Mont Mourex;46.341;6.10534
817;Refuge du col de Balme;46.02669;6.97005
922;Col du Petit St Bernard;45.6715;6.87545
985;Schneckenkopf;47.77045;7.90916
1319;Decollo GAS (Reutte);47.57315;10.63803
1321;Decollo GAS (Garda);45.61211;10.74757
1328;Décollage Nord de Vieilley;47.32522;6.08586
1335;L'Ormont;48.30419;6.99603
1339;Startplatz Rebberg;47.76908;8.96815
1351;Decollo Rialto Ovest;45.65081;11.23746
1359;Decollo Felci;45.50712;7.81003
1366;Mont Poupet Nord;46.97174;5.87789
1378;Col de la Merquière;45.47286;6.02595
1424;Sommet Lauzière;45.44396;6.35876
1427;Décollage Le Pré Bozel;45.45602;6.65731
1430;Décollage Ney Nord;46.73215;5.89345
1433;Takeoff Kanzelhöhe (Gerlitzen);46.67373;13.89617
1439;Urenkopf;48.27233;8.1121
1455;Decollo della Magdeleine 1760m;45.81457;7.60828
1457;Decollo San Simeone 1150m;46.33037;13.10133
1469;Startplatz Greber;47.39927;9.92588
1470;Crêt du Loup La Clusaz;45.89096;6.45178
1509;Startplatz Foppa;47.13739;9.54282
1545;Vigiljoch Startplatz 1400m;46.62418;11.11867
1551;Décollage les Monts;45.45788;6.64099
1568;Décollage de Montlambert;45.55304;6.10458
1594;Décollage Moyenmont;48.00899;6.89691
1615;Hesselberg Nord;49.06732;10.53519
1656;Fürmannalm/Irlberg;47.79334;12.83862
1659;Decollo alto S.Elisabetta 1565m;45.44075;7.64294
1660;Frutigen Helgisberg;46.58669;7.62956
1670;Mont de Vannes;47.7574;6.62204
1676;Hochzellberg Startplatz;49.07546;13.1307
1681;Ehrsberg;47.75061;7.90644
1686;Gampilalm 2100m;46.91589;11.7051
1691;Biollène Valmorel;45.44383;6.41499
1699;Hardheim Hockenberg;49.60686;9.48821
1701;Tuniberg;47.97166;7.6782
1702;Tête de Balme;46.03002;6.96176
1709;Startplatz Eggberge;46.90302;8.65209
1719;Decollo Monte Bernadia 730m;46.22645;13.2641
1741;Décollage de Varan;45.94464;6.68223
1758;Madeleine Valmorel;45.43154;6.3953
1775;Zundelberg;48.06381;8.75017
2036;Les Plagnes Valmorel;45.4408;6.45254
2042;Gelaz Valmorel;45.46102;6.42448
2043;Höllenberg;49.18852;7.88848
2046;Calmongoutte;47.96418;6.81628
2060;Cermis Paion Decollo;46.24307;11.50324
2069;Veitsberg;50.06283;10.99949
2073;Decollo Castiverio Corno d'Aquilio;45.66824;10.97201
2077;Osterfelder Nord Startplatz;47.43944;11.05204
2083;Wixberg Süd;51.31864;7.66767
2129;Decollo Cuarnan 1180m;46.27446;13.17588
2131;Buchberg;49.51579;12.03061
2174;Aviano decollo Est;46.09757;12.54479
2175;Piccolo Matro decollo Nord;46.13666;8.98034
2179;Almkopf 1805m;47.41549;10.76474
2185;Crêtes de Thyon;46.16926;7.36845
2191;Kuhhelle Startplatz;51.1273;8.09217
2195;Schöneberg Funkturm;47.95517;7.80511
2231;Col du Belvédère Bellecombe;45.67936;6.9037
2233;Burgberg Kallmünz;49.01765;12.07454
2340;Decollo Monte Valinis (Meduno);46.23091;12.80619
2390;Col des Frètes;45.85558;6.24716"""

# Offizielle Stationen direkt auf Fluggipfeln bzw. an Startplätzen (mit Temperatur, Feuchte, Strahlung, Sonne, Niederschlag …)
OFFIZIELL = [
    {"id": "geo_hahnenkamm", "name": "Hahnenkamm/Ehrenbachhöhe (Kitzbühel)", "quelle": "geosphere", "station": "11135", "lat": 47.4183, "lon": 12.3592, "hoehe": 1794},
    {"id": "geo_kanzelhoehe", "name": "Kanzelhöhe (Gerlitzen)", "quelle": "geosphere", "station": "11216", "lat": 46.6772, "lon": 13.9019, "hoehe": 1520},
    {"id": "geo_loferer_alm", "name": "Loferer Alm", "quelle": "geosphere", "station": "11337", "lat": 47.5978, "lon": 12.6461, "hoehe": 1619},
    {"id": "geo_schmittenhoehe", "name": "Schmittenhöhe (Zell am See)", "quelle": "geosphere", "station": "11340", "lat": 47.3286, "lon": 12.7381, "hoehe": 1956},
    {"id": "geo_patscherkofel", "name": "Patscherkofel", "quelle": "geosphere", "station": "11126", "lat": 47.2089, "lon": 11.4622, "hoehe": 2251},
    {"id": "geo_feuerkogel", "name": "Feuerkogel (Ebensee)", "quelle": "geosphere", "station": "11155", "lat": 47.8167, "lon": 13.7178, "hoehe": 1618},
    {"id": "geo_villacher_alpe", "name": "Villacher Alpe (Dobratsch)", "quelle": "geosphere", "station": "11265", "lat": 46.6036, "lon": 13.6728, "hoehe": 2117},
    {"id": "geo_rax", "name": "Rax Bergstation", "quelle": "geosphere", "station": "11180", "lat": 47.7175, "lon": 15.7786, "hoehe": 1547},
    {"id": "geo_schoeckl", "name": "Schöckl", "quelle": "geosphere", "station": "11241", "lat": 47.1986, "lon": 15.4664, "hoehe": 1443},
    {"id": "arso_kanin", "name": "Kanin (Bovec, Nähe Stol)", "quelle": "arso", "station": "KANIN_", "lat": None, "lon": None, "hoehe": 2260},
    {"id": "arso_vogel", "name": "Vogel", "quelle": "arso", "station": "VOGEL_", "lat": None, "lon": None, "hoehe": 1515},
    {"id": "dmi_hvidesande", "name": "Hvide Sande", "quelle": "dmi", "station": "06058", "lat": None, "lon": None, "hoehe": None},
    {"id": "dmi_fjaltring", "name": "Fjaltring (Bovbjerg)", "quelle": "dmi", "station": "24025", "lat": None, "lon": None, "hoehe": None},
    {"id": "dwd_wasserkuppe", "name": "Wasserkuppe (DWD)", "quelle": "dwd", "station": "Wasserkuppe", "lat": 50.50, "lon": 9.94, "hoehe": None},
    {"id": "dwd_arber", "name": "Großer Arber (DWD)", "quelle": "dwd", "station": "Großer Arber", "lat": 49.11, "lon": 13.13, "hoehe": None},
    {"id": "dwd_feldberg", "name": "Feldberg/Schwarzwald (DWD)", "quelle": "dwd", "station": "Feldberg/Schwarzwald", "lat": 47.87, "lon": 8.00, "hoehe": None},
    {"id": "dwd_wendelstein", "name": "Wendelstein (DWD)", "quelle": "dwd", "station": "Wendelstein", "lat": 47.70, "lon": 12.01, "hoehe": None},
]
LAND_OFF = {"geosphere": "AT", "arso": "SI", "dmi": "DK", "dwd": "DE"}


def land_aus_koord(lat, lon):
    if lat > 54: return "DK"
    if lon < 6.9 and lat < 48.5: return "FR"
    if lat < 46.6 and lon > 13.4: return "SI"
    return "?"


def region(land, lat, lon):
    if land == "DK": return "Dänemark Küste"
    if land == "DE" and lat < 47.9 and lon >= 10.0: return "Bayerische Alpen / Allgäu"
    if land == "DE" and lat < 48.3 and lon < 9.2: return "Schwarzwald / Südwest"
    if land == "DE": return "Deutsche Mittelgebirge"
    if land == "CH": return "Schweiz"
    if land == "FR" and lat >= 46.6: return "Jura / Vogesen"
    if land == "FR": return "Französische Alpen"
    if land == "SI": return "Julische Alpen / Slowenien"
    if land == "IT" and lon >= 12.3: return "Friaul / Südostalpen"
    if land == "IT": return "Italienische Südalpen"
    if land == "AT":
        if lat < 47.0: return "Kärnten / Südösterreich"
        if lon < 11.0: return "Westösterreich (Arlberg/Reutte/Oberland)"
        if lon < 13.0: return "Tirol / Salzburg"
        return "Ostalpen Österreich"
    return "Sonstige"


def land_owm(lat, lon):
    # grobe Zuordnung (OpenWindMap liefert kein Land)
    if lat > 54: return "DK"
    if lat > 47.6 and lon > 7.5: return "DE"
    if lat > 47.7: return "FR" if lon < 7.6 else "DE"
    if lon < 6.95 and lat < 47.6: return "FR" if not (lat > 46.2 and lon > 6.8) else "CH"
    if 5.9 < lon < 10.5 and 45.8 < lat < 47.8 and not (lat < 46.5 and lon > 8.9): return "CH" if not (lon > 9.9 and lat > 47.2) else "AT"
    if lat > 46.9 and lon > 9.5: return "AT"
    if lat < 46.6 and lon > 13.4: return "SI"
    return "IT"


orte = []
for line in HOLFUY.strip().splitlines():
    sid, name, land, lat, lon = line.split(";")
    lat, lon = float(lat), float(lon)
    orte.append({"id": f"hol_{sid}", "name": name, "land": land, "region": region(land, lat, lon), "quelle": "holfuy",
                 "station": sid, "lat": lat, "lon": lon, "hoehe": 1450 if sid == "1186" else None, "typ": "start"})
for line in OWM.strip().splitlines():
    sid, name, lat, lon = line.split(";")
    lat, lon = float(lat), float(lon)
    land = land_owm(lat, lon)
    if sid == "1433": land = "AT"
    if sid in ("1545", "1686", "2060", "1321", "1351", "2073", "1359", "1455", "1659", "2174", "2175", "1719", "1457", "2129", "2340"): land = "IT"
    if sid in ("1319", "2077", "2179", "1469"): land = "AT" if sid in ("2179", "1469") else "DE" if sid == "2077" else "AT"
    orte.append({"id": f"owm_{sid}", "name": name, "land": land, "region": region(land, lat, lon), "quelle": "owm",
                 "station": sid, "lat": lat, "lon": lon, "hoehe": None, "typ": "start"})
for o in OFFIZIELL:
    land = LAND_OFF[o["quelle"]]
    lat = o["lat"] if o["lat"] is not None else {"SI": 46.3, "DK": 56.2}[land]
    o2 = dict(o, land=land, region=region(land, lat, o["lon"] if o["lon"] is not None else 13.6 if land == "SI" else 8.1), typ="berg" if land not in ("DK",) else "kueste")
    orte.append(o2)

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "orte.json"), "w", encoding="utf-8") as f:
    json.dump({"_info": "Vergleichsorte – nur Stationen direkt an Startplätzen/Fluggipfeln. Erzeugt mit orte_erzeugen.py.", "orte": orte},
              f, ensure_ascii=False, indent=1)
from collections import Counter
print(len(orte), "Orte")
for k, v in sorted(Counter(o["region"] for o in orte).items()):
    print(f"  {v:3d}  {k}")
print(Counter(o["quelle"] for o in orte))
