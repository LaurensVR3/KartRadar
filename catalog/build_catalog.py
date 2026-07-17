"""
Build data/centers_catalog.json — run once, then re-run (or let the scheduler
re-run it daily) whenever you want fresh data.
    python -m catalog.build_catalog
"""

import json, os, re, requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_CENTER_ID = 600

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

OVERRIDES_FILE = BASE_DIR / "catalog_overrides.json"
CATALOG_FILE = DATA_DIR / "centers_catalog.json"

# ── Kart-vs-not-kart filtering ──────────────────────────────────────────────────
# Apex Timing is a generic activity-booking SaaS — the "/gokarts/" URL path is
# legacy branding, not a guarantee of content. Centers running on it turned out
# to include laser tag arenas, bowling alleys, trampoline parks, padel/squash
# clubs, escape rooms, indoor football and more. Two-layer defence:
#
#   1. NON_KART_BLOCKLIST strips individual products that are clearly a
#      different activity, even inside a center that does have real karting
#      (e.g. a karting center's own mini-golf or laser-tag add-on).
#   2. has_kart_word() gates whole centers: a center is only kept if "kart"
#      appears in its name, website, or at least one RAW product/category —
#      checked *before* the blocklist strips anything, so a combo product like
#      "Kart & Bowling" still counts as a signal even though the combo itself
#      gets removed. This trades a little recall (a handful of English-language
#      tracks that only ever say "Race"/"GP"/"Timed Session", never "kart") for
#      much higher precision against the much bigger pollution problem — see
#      catalog_overrides.json for the manual escape hatch for that handful.

NON_KART_BLOCKLIST = [
    "golf",   # mini golf, adventure golf, golf sims/bays, "ultragolf" bundles...
    "laser",  # laser game/tag, "2 lasers", "kara'laser" — never appears in a pure kart SKU
    "bowling",
    "trampoline", "jump park", "trampo",
    "escalade", "climbing", "accrobranche", "clip and climb",
    "padel", "squash", "ping pong",
    "axe throwing", "axe throw",
    "prison", "escape",  # escape room / prison island / "prison infernale" / "vr escapegame"
    "cube master", "cube challenge",
    "quiz", "pubquiz", "muziekbingo", "blind test", "karaoke", "karaoké",
    "foot indoor", "football indoor", "foot outdoor",
    "paintball", "water jump",
    "realite virtuelle", "réalité virtuelle", "virtuelle",
    "ferrari", "lamborghini", "maserati", "corvette", "porsche", "supercar",
    "restaurant", " diner ", "dinner",
    "surf",
    "stand-up", "soiree du 31", "soirée du 31",
    # Motorcycle disciplines — some multi-sport venues (e.g. RACB Spa) sell
    # moto track days through the same product catalog as their karting.
    # Deliberately *not* blocking the bare word "moto": in Czech/Slovak,
    # "motokáry" is the word for go-kart, so that would wrongly strip real
    # karting products at those centers.
    "journée moto", "journee moto", "supermotard", "pitbike", "motocross",
]

def is_blocklisted(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in NON_KART_BLOCKLIST)

def has_kart_word(text: str) -> bool:
    """Catches kart, karting, go-kart, gokart, battlekart, kartbaan, ..."""
    return "kart" in text.lower()

# ── Calendar-track discovery ────────────────────────────────────────────────────
# Some centers also run a second, independent booking system — calendar.php,
# day-based, keyed by track_id — alongside (or instead of) the product catalog
# above. It's how Karting Genk's real "own-kart" offering works: none of its
# rental products cover it, it only exists as calendar.php track_id=10 "Track
# Pro eigen kart". GET calendar.php?center={id} (no track= param) returns every
# configured resource for that center in one cheap request, e.g. Genk's:
#   Track FUN(3), Track PRO(4), GRASVELD(12), Track Pro eigen kart(10),
#   Brasserie(5), Karts stalling(6), Expert(7), GKS & ATELIER(8), ONDERHOUD(11)
# — a mix of real tracks and unrelated facility bookings (restaurant, storage,
# maintenance, workshop), so this needs its own filter, same idea as
# NON_KART_BLOCKLIST but tuned to short resource names instead of product titles.

NON_TRACK_RESOURCE_KWS = [
    "brasserie", "restaurant", "cafe", "café", " bar ",
    "stalling", "storage", "opslag",
    "atelier", "workshop", "werkplaats",
    "onderhoud", "maintenance", "entretien",
    "grasveld", "grass field",
    "clubhouse", "club house",
    "party room", "partyroom",
    "vergaderzaal", "meeting room", "salle de reunion",
    "parking",
]

RESOURCE_PRIVATE_KWS = ["eigen kart", "prive", "privé", "private", "competition", "compétition"]
RESOURCE_RENTAL_KWS  = ["location", "rental", "fun", "loisir", "verhuur"]

def classify_calendar_resource(name: str):
    """
    'private' / 'rental' / None (not a real bookable track, or no clear signal —
    skipped rather than guessed, same precision-over-recall bias as build_catalog
    uses elsewhere).
    """
    low = name.lower()
    if is_blocklisted(low) or any(kw in low for kw in NON_TRACK_RESOURCE_KWS):
        return None
    if any(kw in low for kw in RESOURCE_PRIVATE_KWS):
        return "private"
    if any(kw in low for kw in RESOURCE_RENTAL_KWS):
        return "rental"
    return None

def fetch_calendar_tracks(cid: int) -> list:
    """At most one entry per booking type — first (source order) wins if a
    center happens to expose more than one track classified the same way."""
    try:
        r = requests.get(
            f"https://www.apex-timing.com/gokarts/calendar.php?center={cid}",
            headers=HEADERS, timeout=8,
        )
        if r.status_code != 200:
            return []
        m = re.search(r'<ul id="all_tracks".*?</ul>', r.text, re.DOTALL)
        if not m:
            return []
        items = re.findall(r'data-id="(\d+)"[^>]*>([^<]+)<', m.group())
    except Exception:
        return []

    by_booking = {}
    for track_id, raw_name in items:
        name = raw_name.strip()
        booking = classify_calendar_resource(name)
        if booking is not None and booking not in by_booking:
            by_booking[booking] = {"track_id": int(track_id), "name": name, "booking": booking}
    return list(by_booking.values())

def load_overrides():
    if not OVERRIDES_FILE.exists():
        return {"force_include": set(), "force_exclude": set()}
    data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    return {
        "force_include": set(data.get("force_include", [])),
        "force_exclude": set(data.get("force_exclude", [])),
    }

OVERRIDES = load_overrides()

# ── Classification rules ───────────────────────────────────────────────────────
# Order matters: most-specific first

SESSION_RULES = [
    # Competitive/licensed classes first — these are specific, unambiguous
    # racing categories and should win over any looser age/format wording.
    ("shifter", ["shifter", "kz2", " kz ", "/kz", "dd2", "boite", "gearbox"]),
    ("master",  ["master"]),
    ("senior",  ["senior"]),
    ("junior",  ["junior"]),
    ("4stroke", ["ka100", "ka 100", "honda", "briggs", "4takt", "4-takt",
                 "4 takt", "4stroke", "4-stroke"]),
    ("mini",    ["mini", "rookie", "micromax", "baby kart"]),
    # Kart *format*, not age/skill — genuinely different equipment/experience,
    # independent of who's driving.
    ("drift",     ["drift"]),
    ("endurance", ["endurance"]),
    ("biplace",   ["biplace", "biposto", "tandem", "2 places", "2-seater",
                    "two seater", "duo kart"]),
    # Rental venues overwhelmingly describe sessions by age tier rather than
    # a racing class — "Adulte"/"Adult"/"Erwachsene" and "Enfant"/"Kids"/
    # "Kinder" are the same distinction in different languages. Checked after
    # the classes above so e.g. "Senior" still wins over an incidental
    # "adulte" mention; checked before the generic fallback below because on
    # their own (84% of all products, empirically) they're the single
    # biggest source of real signal that fallback was throwing away.
    ("kids",  ["enfant", "enfants", "kids", " kid ", " kid,", "family",
               "famille", "kind ", "kinder", "bambin", "ragazzi", "niño",
               "niños"]),
    ("adult", ["adulte", "adultes", "adult", "adulti", "erwachsene",
               "volwassene"]),
    # No specific age/skill class stated — "general" describes the SESSION
    # class (nobody asked for a category), which is a different axis from the
    # BOOKING type below (private vs rental). Reusing the word "rental" for
    # both used to make a private-booking row show a "Rental" session badge,
    # which read as self-contradictory (see e.g. RACB Spa/Racing Kart JPR).
    ("general", ["location", "rental", "fun kart", "fun-kart", "loisir",
                 "locat", "ticket", "bachelor",
                 "grand prix", "pro kart"]),
]

# Checked *before* RENTAL_KWS below — an explicit private/own-kart mention
# should win even when the same title also contains a rental-sounding word,
# e.g. "Kart privé - Loisirs / Amateurs" is a private day for a hobbyist
# skill class, not a walk-up rental; "Adult Private Grand Prix" is a private
# group buyout even though "grand prix" is normally a rental-package term.
STRONG_PRIVATE_KWS = [
    "privé", "prive", "private", "kart priv", "private kart",
    "training private", "eigen kart",
]

# Checked *after* RENTAL_KWS — phrases that merely suggest private-ness by
# context (no literal "priv"/"private"/"eigen" root) and also show up in
# genuine full-day rental packages, so an explicit rental keyword still wins.
PRIVATE_KWS = [
    "track fee", "entrainement", "entraînement", "training kart",
    "journée kart", "journee kart", "demi-journée", "demi journée",
    "demi-journ",
]

RENTAL_KWS = [
    "location ", "rental ", "fun kart", "fun-kart", "loisir",
    "locat", "ticket karting", "ticket kart", "biplace", "duo kart",
    "bachelor", "grand prix", "pro kart session",
]

def parse_hours(s):
    if not s:
        return None
    h    = int(m.group(1)) if (m := re.search(r"(\d+)h",   s)) else 0
    mins = int(m.group(1)) if (m := re.search(r"(\d+)min", s)) else 0
    return (h + mins / 60) or None

# A product title with an embedded calendar date (e.g. "BELGIAN CUP-JUNIOR /
# 05-09-26") is a one-off competition entry for that specific weekend, not a
# regular recurring booking — checked empirically against the whole catalog,
# this pattern had zero false positives (durations like "15 min" or "5h"
# don't match a day-month-year triple). These don't fit this tool's "which of
# the next 28 days is open" model at all, and worse: when one of these got
# picked as the "representative" product for a whole (center, booking) row
# (see app/browse.py select_rows), the entire row inherited its one-off
# pricing/duration and near-permanently-closed availability — e.g. Karting
# des Fagnes's real, bookable-almost-daily rental tickets were being hidden
# behind a single Belgian Cup weekend entry that showed no availability.
ONE_OFF_EVENT_DATE = re.compile(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}")

def classify(product, cat_title):
    p_title = product.get("title", "")
    combined = (p_title + " " + cat_title).lower()

    # Not a karting product at all (laser tag, bowling, mini golf, ...) — see
    # NON_KART_BLOCKLIST above.
    if is_blocklisted(combined):
        return None

    # One-off dated competition entry — see ONE_OFF_EVENT_DATE comment above.
    if ONE_OFF_EVENT_DATE.search(p_title + " " + cat_title):
        return None

    # Booking type — an explicit private/own-kart mention (STRONG_PRIVATE_KWS)
    # wins even over a co-occurring rental-sounding word; otherwise rental
    # keywords win over the weaker/contextual private phrases.
    if any(k in combined for k in STRONG_PRIVATE_KWS):
        booking = "private"
    elif any(k in combined for k in RENTAL_KWS):
        booking = "rental"
    elif any(k in combined for k in PRIVATE_KWS):
        booking = "private"
    else:
        booking = "rental"  # default fallback

    # Session type
    session = "general"
    for stype, kws in SESSION_RULES:
        if any(k in combined for k in kws):
            session = stype
            break

    # "shifter"/"4stroke" reference specific competition-only equipment (KZ/DD2
    # gearbox karts, KA100/Honda/Briggs engines) that rental venues essentially
    # never use for casual branding — checked empirically against the whole
    # catalog, matching these two implied "private" with zero false positives,
    # so it's kept as a safety net for the rare product with no other signal.
    #
    # "mini"/"junior"/"senior"/"master" used to be in this set too, on the
    # theory that a named racing class implies exclusivity. Wrong in practice:
    # every real venue reuses these words as plain rental age-tier branding
    # ("Juniorkart" at Kartbaan Oldenzaal, "SESSION MASTER (KARTING ADULTE)",
    # "Quick Race 6 min. SENIOR", "1 Junior Race") far more often than as an
    # actual licensed class — 262 products got wrongly flipped to "private"
    # this way, e.g. showing Oldenzaal's plain rental "Juniorkart" as if it
    # were their (real, but phone-only) private track access. Every genuine
    # competitive product checked (Fagnes, JPR, RACB) already had explicit
    # "Privé"/"Licencié"/a category literally containing "PRIVATE" — i.e. it
    # was already correctly classified via STRONG_PRIVATE_KWS/PRIVATE_KWS
    # above without needing this bump at all, so dropping these four here
    # only removes false positives, not real coverage.
    if session in ("shifter", "4stroke") and booking == "rental":
        booking = "private"

    # Day type from duration
    dur_h = parse_hours(product.get("duration", ""))
    if dur_h is None:
        day_type = "session"
    elif dur_h >= 4:
        day_type = "full"
    elif dur_h >= 2:
        day_type = "half"
    else:
        day_type = "session"

    return {
        "id":       int(product["id"]),
        "title":    p_title,
        "category": cat_title,
        "price":    float(product.get("price", 0) or 0),
        "dur_h":    round(dur_h, 2) if dur_h else None,
        "booking":  booking,
        "session":  session,
        "day_type": day_type,
    }

# Country codes mapped to ccTLDs (including two-part ones like .co.uk)
_TLD_MAP = {
    "be": "BE", "fr": "FR", "lu": "LU", "nl": "NL", "de": "DE",
    "es": "ES", "it": "IT", "ch": "CH", "at": "AT", "pt": "PT",
    "uk": "UK", "co.uk": "UK", "ie": "IE", "cz": "CZ", "sk": "SK",
    "pl": "PL", "dk": "DK", "se": "SE", "no": "NO", "fi": "FI",
    "ro": "RO", "hu": "HU", "hr": "HR", "si": "SI", "gr": "GR",
}

# French product-title words that strongly suggest a French-language country
_FR_WORDS = ["location", "séance", "seance", "entrainement", "entraînement",
             "pilote", "journée", "journee", "billet", "adulte", "session",
             "circuit", "tarif", "kart privé", "kart prive", "demi"]
_NL_WORDS = ["eigen", "rijden", "vrij", "beschikbaar", "dag ", "uur ",
             "training", "sessie", "eigen kart"]
_DE_WORDS = ["stunde", "runde", "fahrer", "training", "fahrt", "miete"]

def detect_country(website: str, html: str) -> str:
    # 1) Two-part ccTLD (.co.uk, .co.it, …)
    m2 = re.search(r'\.(co|com|org|net)\.(uk|ie|au|nz|za|in|nz)\b', website)
    if m2:
        ext = m2.group(2)
        return {"uk": "UK", "ie": "IE", "au": "AU", "nz": "NZ", "za": "ZA", "in": "IN"}.get(ext, "??")

    # 2) Single ccTLD
    m1 = re.search(r'\.([a-z]{2,3})(?:[/?#"]|$)', website)
    if m1 and m1.group(1) in _TLD_MAP:
        return _TLD_MAP[m1.group(1)]

    # 3) Language fallback from product titles already in html
    low = html.lower()
    if any(w in low for w in _FR_WORDS):
        return "FR"   # could be BE too, but BE centres use .be
    if any(w in low for w in _NL_WORDS):
        return "NL"
    if any(w in low for w in _DE_WORDS):
        return "DE"

    return "??"


def fetch_center(cid):
    try:
        if cid in OVERRIDES["force_exclude"]:
            return None

        r = requests.get(
            f"https://www.apex-timing.com/gokarts/sessions_booking.php?center={cid}&language=fr",
            headers=HEADERS, timeout=8,
        )
        if r.status_code != 200 or f"center{cid}" not in r.text:
            return None
        html = r.text

        # Name + website
        nm = re.search(
            r'class="(?:ax-top_bar-center_name|center_name)".*?href="([^"]*)"[^>]*><span>([^<]+)</span>',
            html, re.DOTALL,
        )
        if not nm:
            return None
        website = nm.group(1).strip()
        name    = nm.group(2).strip()

        country = detect_country(website, html)

        # Products — raw_kart_signal is checked on the *unfiltered* title/category
        # (pre-blocklist), so a stripped combo product like "Kart & Bowling" still
        # counts as evidence this center does karting.
        pm = re.search(r'var products = ({.*?});', html, re.DOTALL)
        products = []
        raw_kart_signal = False
        if pm:
            raw = json.loads(pm.group(1))
            for cat in raw.values():
                cat_title = cat.get("title", "")
                for p in cat.get("products", []):
                    if has_kart_word(p.get("title", "") + " " + cat_title):
                        raw_kart_signal = True
                    classified = classify(p, cat_title)
                    if classified is not None:
                        products.append(classified)

        forced = cid in OVERRIDES["force_include"]
        has_signal = has_kart_word(name) or has_kart_word(website) or raw_kart_signal
        if not forced and not has_signal:
            return None   # no evidence this center does karting at all
        if not forced and not products:
            return None   # karting signal existed but nothing survived the blocklist

        return {
            "id":             cid,
            "name":           name,
            "website":        website,
            "country":        country,
            "products":       products,
            "calendar_tracks": fetch_calendar_tracks(cid),
        }
    except Exception:
        return None

def merge_duplicate_venues(centers: list) -> list:
    """
    Some physical venues are split across two Apex Timing center_ids for
    internal reasons — Karting Genk's real "own-kart" tickets (Track Fee -
    Mini/Junior/Senior/Shifter, real prices) live under a *separate* center_id
    named "KARTING GENK - S3 SALES SUPPORT SERVICES", not under the main
    "Karting Genk" record at all. Left unmerged, the tool showed two different
    "Own kart" rows for the exact same track: a generic calendar-discovered
    one and this properly-detailed one.
    Detected as: same website, and one name is a substring of the other. This
    is deliberately narrow — multi-location chains sharing one corporate
    website (SPEEDPARK Conflans/Bretigny/Servon, RPM Raceway Stamford/Jersey
    City/..., Indy Kart @ Eastgate/Clearwater/...) do NOT match, because each
    location has its own distinct name rather than one being a prefix of
    another — checked against the whole catalog, this rule only ever fired
    for the genuine Genk case.
    """
    by_website = defaultdict(list)
    for c in centers:
        by_website[c["website"].rstrip("/").lower()].append(c)

    absorbed_ids = set()
    for website, group in by_website.items():
        if len(group) < 2:
            continue
        for a in group:
            for b in group:
                if a["id"] == b["id"] or a["id"] in absorbed_ids or b["id"] in absorbed_ids:
                    continue
                name_a, name_b = a["name"].lower().strip(), b["name"].lower().strip()
                if len(name_a) < 6 or len(name_b) < 6:
                    continue  # avoid trivial short-name accidental matches
                if name_a in name_b or name_b in name_a:
                    canonical, other = (a, b) if len(a["name"]) <= len(b["name"]) else (b, a)
                    canonical["products"] = canonical["products"] + other["products"]
                    canonical["calendar_tracks"] = (
                        canonical.get("calendar_tracks", []) + other.get("calendar_tracks", [])
                    )
                    absorbed_ids.add(other["id"])
                    print(f"  Merged '{other['name']}' (id={other['id']}) into "
                          f"'{canonical['name']}' (id={canonical['id']}) — same website, same venue")

    return [c for c in centers if c["id"] not in absorbed_ids]

def build(max_id=MAX_CENTER_ID):
    print(f"Probing center IDs 1–{max_id} …")
    results = []
    with ThreadPoolExecutor(max_workers=40) as ex:
        futures = {ex.submit(fetch_center, i): i for i in range(1, max_id + 1)}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{max_id} checked, {len(results)} found so far")
            r = fut.result()
            if r:
                results.append(r)

    results = merge_duplicate_venues(results)
    results.sort(key=lambda x: x["id"])
    print(f"\nFound {len(results)} active centers")

    CATALOG_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved -> {CATALOG_FILE.resolve()}")
    return results

if __name__ == "__main__":
    build()
