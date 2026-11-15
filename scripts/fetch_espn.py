"""Descarga los partidos de la Liga BetPlay desde la API pública de ESPN y los guarda en data/raw/."""
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/col.1/scoreboard?dates={year}&limit=1000"
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "liga_betplay_espn_2022_2026.json"


def side(comp, home_away):
    t = next(c for c in comp["competitors"] if c["homeAway"] == home_away)
    return {"id": t["team"]["id"], "name": t["team"]["displayName"], "abbr": t["team"].get("abbreviation"),
            "score": t.get("score"), "winner": t.get("winner"), "form": t.get("form"),
            "stats": {s["name"]: s["displayValue"] for s in t.get("statistics", [])}}


def parse(event):
    comp = event["competitions"][0]
    venue = comp.get("venue") or {}
    note = "; ".join(n.get("headline", "") for n in comp.get("notes", [])) or comp.get("altGameNote")
    return {
        "id": event["id"], "date": event["date"], "year": event["season"]["year"], "stage": event["season"]["slug"],
        "status": event["status"]["type"]["name"], "completed": event["status"]["type"]["completed"],
        "venue": venue.get("fullName"), "city": (venue.get("address") or {}).get("city"),
        "attendance": comp.get("attendance"), "note": note,
        "home": side(comp, "home"), "away": side(comp, "away"),
        "events": [{"type": (d.get("type") or {}).get("text"), "clock": (d.get("clock") or {}).get("displayValue"),
                    "team": (d.get("team") or {}).get("id"), "goal": d.get("scoringPlay"), "pen": d.get("penaltyKick"),
                    "og": d.get("ownGoal"), "yc": d.get("yellowCard"), "rc": d.get("redCard"),
                    "player": "|".join(a["displayName"] for a in d.get("athletesInvolved", []))}
                   for d in comp.get("details", [])],
    }


def main(years):
    matches = []
    for year in years:
        req = urllib.request.Request(URL.format(year=year), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            events = json.load(resp).get("events", [])
        done = [parse(e) for e in events if e["status"]["type"]["completed"]]
        print(f"{year}: {len(done)} partidos terminados")
        matches += done
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(matches, ensure_ascii=False), encoding="utf-8")
    print(f"guardado {OUT} ({len(matches)} partidos)")


if __name__ == "__main__":
    main([int(y) for y in sys.argv[1:]] or range(2022, 2027))
