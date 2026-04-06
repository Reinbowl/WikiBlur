"""
WikiBlur Category Validator
============================
Crawls Wikipedia's API to find categories confirmed to have enough
image-rich articles for a full 8-round WikiBlur game.

How it works:
  1. For each parent in PARENT_CATEGORIES, fetch its subcategories
  2. Test each subcategory (and the parent itself) by fetching article
     metadata from the Wikipedia API and checking for thumbnail URLs
  3. Any category with >= MIN_VALID_ARTICLES confirmed image-articles passes
  4. Writes valid_categories.json and prints a JS const you can paste
     straight into wikiblur.html

No HTTP image probing is done — Wikipedia only populates thumbnail.source
in the API response when the file genuinely exists and is served, so the
API check alone is highly reliable. SVG/OGG/PDF URLs are filtered by
extension as an extra guard.

Usage:
    python3 validate_categories.py
    python3 validate_categories.py --max-children 20 --output my_cats.json
    python3 validate_categories.py --delay 1.5   # slower, safer

Requirements: Python 3.8+, no third-party packages needed.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import argparse
from typing import Optional

# ── Match these to your wikiblur.html constants ────────────────────
TOTAL_ROUNDS       = 8
MIN_VALID_ARTICLES = TOTAL_ROUNDS + 3  # = 11

# Stop scanning a category once we confirm this many — small buffer
# above MIN_VALID_ARTICLES so a few CDN failures at play-time are fine
SCAN_TARGET = MIN_VALID_ARTICLES + 8  # = 19

# Delay between every API call. 1.0 s keeps us well under Wikipedia's
# rate limits; lower values risk 429s on long runs.
API_DELAY = 1.0   # seconds between calls — overridable via --delay
TIMEOUT   = 20    # seconds per request

# Retry behaviour when a 429 (or transient error) is returned.
MAX_RETRIES    = 5
BACKOFF_BASE   = 2   # exponential base; wait = BACKOFF_BASE ** attempt seconds

API = "https://en.wikipedia.org/w/api.php"

# Identify ourselves properly — Wikipedia's policy requires a meaningful
# User-Agent that includes a contact address or repo URL.
USER_AGENT = (
    "WikiBlur/1.0 "
    "(https://github.com/username; "
    "example@email.com)"
)

BAD_EXT = re.compile(r'\.(svg|ogg|ogv|webm|pdf|tiff?)(\?|$)', re.IGNORECASE)

# version 1
PARENT_CATEGORIES = [
    "Mammals", "Birds", "Reptiles", "Amphibians", "Fish",
    "Insects", "Arachnids", "Molluscs", "Crustaceans",
    "Flowering plants", "Trees", "Fungi", "Marine biology",
    "Dinosaurs", "Primates", "Big cats", "Bears", "Sharks",
    "National parks", "Islands", "Volcanoes", "Waterfalls",
    "Mountains", "Deserts", "Rivers", "Lakes", "Beaches",
    "Lighthouses", "Castles", "Cathedrals", "Bridges",
    "Cities", "Archaeological sites",
    "Paintings", "Sculptures", "Photographers",
    "Ancient Egyptian art", "Ancient Greek art",
    "Renaissance art", "Impressionism", "Modern art",
    "Pottery", "Masks", "Textiles",
    "Spacecraft", "Rockets", "Satellites", "Telescopes",
    "Aircraft", "Locomotives", "Automobiles", "Ships",
    "Minerals", "Gemstones", "Fossils", "Meteorites",
    "Olympic sports", "Martial arts", "Gymnasts",
    "Musical instruments", "Guitars", "Drums",
    "Coins", "Stamps", "Flags",
]

# version 2
PARENT_CATEGORIES = [
    # Nature / Biology
    "Wildflowers", "Grasses", "Coral reefs", "Seaweed",
    "Butterflies and moths", "Beetles",
    "Birds of prey", "Songbirds",
    "Rodents", "Marsupials", "Whales", "Seals and sea lions",

    # Geography / Natural Features
    "Canyons", "Glaciers", "Cliffs", "Hot springs", "Geysers",
    "Rainforests", "Savannas", "Tundra", "Wetlands",
    "Peninsulas", "Deltas", "Oases",

    # Architecture / Man-made
    "Skyscrapers", "Temples", "Mosques", "Pagodas",
    "Fortresses", "Palaces", "Museums", "Libraries",
    "Universities", "Stadiums", "Airports", "Harbors",

    # Arts / Culture
    "Murals", "Street art", "Illustrations", "Calligraphy",
    "Ceramics", "Jewelry", "Fashion", "Costumes",
    "Dance", "Theatre",

    # Technology / Engineering
    "Computers", "Supercomputers", "Robots", "Drones",
    "Submarines", "Space stations", "Microscopes",
    "Scientific instruments", "Engines",

    # Earth Science / Weather
    "Rock formations", "Caves", "Soil types",
    "Earthquakes", "Clouds", "Storms", "Rainbows",

    # Sports / Activities
    "Ball games", "Winter sports", "Water sports",
    "Extreme sports", "Track and field", "Cycling", "Team sports",

    # Music
    "Pianos", "Violins", "Wind instruments",
    "Orchestras", "Bands", "Music festivals",

    # Objects / Collectibles
    "Posters", "Maps", "Books", "Magazines",
    "Toys", "Board games", "Clocks", "Watches",
]


def api_get(params: dict, delay: float = API_DELAY) -> dict:
    """
    GET the Wikipedia API and return parsed JSON.

    Handles 429 Too Many Requests by honouring the Retry-After header
    (or falling back to exponential backoff) and retrying up to
    MAX_RETRIES times. Also retries on transient network errors.
    """
    full_params = {"format": "json", "origin": "*", **params}
    # Use quote (not quote_plus) so | is NOT percent-encoded
    qs  = urllib.parse.urlencode(full_params, quote_via=urllib.parse.quote)
    url = f"{API}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                # Respect the server's Retry-After value when present.
                retry_after = exc.headers.get("Retry-After")
                if retry_after is not None:
                    wait = float(retry_after)
                    print(f"\n  [429 rate-limited — Retry-After: {wait:.0f}s]", flush=True)
                else:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    print(f"\n  [429 rate-limited — backing off {wait:.0f}s]", flush=True)

                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    # Also bump the inter-call delay for the remainder of the run
                    # so we don't immediately hit the limit again.
                    delay = max(delay, wait / 4)
                    continue
                # Exhausted retries — propagate so safe_api_get can log it
                raise

            # Non-429 HTTP error — retry on 5xx, give up on 4xx
            if 500 <= exc.code < 600 and attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"\n  [HTTP {exc.code} — retrying in {wait:.0f}s]", flush=True)
                time.sleep(wait)
                continue
            raise

        except OSError as exc:
            # Covers timeouts, connection resets, DNS failures, etc.
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"\n  [Network error: {exc} — retrying in {wait:.0f}s]", flush=True)
                time.sleep(wait)
                continue
            raise

    # Should be unreachable, but keeps the type-checker happy
    raise RuntimeError("api_get: exceeded MAX_RETRIES without returning")


def safe_api_get(params: dict) -> Optional[dict]:
    try:
        return api_get(params)
    except Exception as exc:
        print(f"\n  [API error after {MAX_RETRIES} retries: {exc}]", flush=True)
        return None


def fetch_subcategories(parent: str) -> list:
    data = safe_api_get({
        "action": "query", "list": "categorymembers",
        "cmtitle": f"Category:{parent}", "cmtype": "subcat", "cmlimit": "80",
    })
    if not data:
        return []
    return [
        m["title"].replace("Category:", "", 1)
        for m in data.get("query", {}).get("categorymembers", [])
    ]


def fetch_members(category: str) -> list:
    data = safe_api_get({
        "action": "query", "list": "categorymembers",
        "cmtitle": f"Category:{category}", "cmtype": "page", "cmlimit": "500",
    })
    if not data:
        return []
    return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]


def fetch_details_batch(titles: list) -> list:
    """Return pages that have a valid thumbnail URL and non-stub extract."""
    if not titles:
        return []
    data = safe_api_get({
        "action": "query",
        "prop": "pageimages|extracts",
        "piprop": "thumbnail",
        "pithumbsize": "600",
        "exsentences": "2",
        "exintro": "1",
        "explaintext": "1",
        "titles": "|".join(titles[:50]),
    })
    if not data:
        return []

    good = []
    for page in data.get("query", {}).get("pages", {}).values():
        pageid  = page.get("pageid", -1)
        thumb   = page.get("thumbnail", {}).get("source", "")
        extract = (page.get("extract") or "").strip()
        if pageid > 0 and thumb and len(extract) > 20 and not BAD_EXT.search(thumb):
            good.append(page)
    return good


def count_valid(category: str, delay: float = API_DELAY) -> int:
    """Count image-confirmed articles in a category. Stops at SCAN_TARGET."""
    members = fetch_members(category)
    time.sleep(delay)

    if len(members) < MIN_VALID_ARTICLES:
        return len(members)  # return actual count so caller can show it

    confirmed = 0
    for i in range(0, len(members), 50):
        if confirmed >= SCAN_TARGET:
            break
        confirmed += len(fetch_details_batch(members[i:i+50]))
        time.sleep(delay)

    return confirmed


def main():
    global API_DELAY

    parser = argparse.ArgumentParser()
    parser.add_argument("--max-children", type=int, default=10,
                        help="Max subcategories to test per parent (default: 10)")
    parser.add_argument("--output", default="valid_categories.json")
    parser.add_argument(
        "--delay", type=float, default=API_DELAY,
        help=f"Seconds between API calls (default: {API_DELAY}). "
             "Increase if you keep hitting 429s.",
    )
    args = parser.parse_args()
    API_DELAY = args.delay  # propagate to module-level default

    print("WikiBlur Category Validator")
    print(f"  MIN_VALID_ARTICLES = {MIN_VALID_ARTICLES}")
    print(f"  SCAN_TARGET        = {SCAN_TARGET}")
    print(f"  Max children       = {args.max_children}")
    print(f"  API delay          = {API_DELAY}s")
    print(f"  Max retries        = {MAX_RETRIES} (exponential backoff)")
    print()

    valid   = []
    seen    = set()
    tested  = 0

    def test(name: str, indent: str) -> bool:
        nonlocal tested
        if name in seen:
            return False
        seen.add(name)
        tested += 1
        sys.stdout.write(f"{indent}'{name}'... ")
        sys.stdout.flush()
        n = count_valid(name, delay=API_DELAY)
        if n >= MIN_VALID_ARTICLES:
            print(f"✓  ({n} image articles)")
            valid.append(name)
            return True
        else:
            print(f"✗  ({n} image articles, need {MIN_VALID_ARTICLES})")
            return False

    for i, parent in enumerate(PARENT_CATEGORIES):
        print(f"[{i+1}/{len(PARENT_CATEGORIES)}] {parent}")
        test(parent, "  ")

        subs = fetch_subcategories(parent)
        time.sleep(API_DELAY)
        print(f"  └─ {len(subs)} subcategories, testing first {args.max_children}")

        for sub in subs[:args.max_children]:
            test(sub, "     ")

        print()

    unique = list(dict.fromkeys(valid))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print("─" * 60)
    print(f"Tested : {tested}  |  Valid : {len(unique)}  |  Saved : {args.output}")
    print()
    print("Paste into wikiblur.html:")
    print()
    print("const VALIDATED_CATEGORIES = [")
    for j in range(0, len(unique), 4):
        chunk = unique[j:j+4]
        comma = "," if j + 4 < len(unique) else ""
        print("  " + ", ".join(f'"{c}"' for c in chunk) + comma)
    print("];")


if __name__ == "__main__":
    main()
