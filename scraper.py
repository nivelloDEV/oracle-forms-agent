import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
DATA_FILE = "found_companies.json"

QUERIES = [
    'site:linkedin.com/jobs "oracle forms" sweden',
    'site:linkedin.com/jobs "oracle forms" danmark',
    'site:linkedin.com/jobs "oracle forms" denmark',
    '"oracle forms" företag sverige',
    '"oracle forms" virksomhed danmark',
    '"oracle forms" consultant sweden',
    '"oracle forms" developer denmark',
]

CLOSED_PHRASES = [
    "no longer accepting applications",
    "no longer accepting",
    "job no longer available",
]

ALLOWED_LOCATIONS = [
    "sweden", "sverige", "stockholm", "göteborg", "malmö", "gothenburg",
    "denmark", "danmark", "copenhagen", "köpenhamn", "københavn", "aarhus", "odense",
]


def load_seen() -> set:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(DATA_FILE, "w") as f:
        json.dump(list(seen), f)


def parse_date(date_str: str) -> datetime | None:
    """Försöker tolka datumsträngar från SerpAPI, t.ex. '3 months ago', '2024-01-15'."""
    if not date_str:
        return None
    date_str = date_str.lower().strip()
    now = datetime.now()
    try:
        if "day" in date_str:
            days = int(date_str.split()[0])
            return now - timedelta(days=days)
        elif "week" in date_str:
            weeks = int(date_str.split()[0])
            return now - timedelta(weeks=weeks)
        elif "month" in date_str:
            months = int(date_str.split()[0])
            return now - timedelta(days=months * 30)
        elif "year" in date_str:
            years = int(date_str.split()[0])
            return now - timedelta(days=years * 365)
        else:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def is_recent(date_str: str, max_days: int = 365) -> bool:
    """Returnerar True om datumet är inom max_days, eller om datumet är okänt."""
    parsed = parse_date(date_str)
    if parsed is None:
        return True  # Okänt datum – ta med för säkerhets skull
    return (datetime.now() - parsed).days <= max_days


def search_google(query: str) -> list[dict]:
    url = "https://serpapi.com/search"
    params = {
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 10,
        "hl": "sv",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("organic_results", [])

        filtered = []
        for res in results:
            snippet = res.get("snippet", "").lower()
            title = res.get("title", "").lower()
            link = res.get("link", "")
            is_linkedin = "linkedin.com/jobs" in link

            # Hämta datum från SerpAPI (finns i "date" eller inne i "rich_snippet")
            date_str = (
                res.get("date")
                or res.get("rich_snippet", {}).get("top", {}).get("detected_extensions", {}).get("posted_at")
                or ""
            )

            is_closed = any(phrase in snippet or phrase in title for phrase in CLOSED_PHRASES)

            if is_closed:
                if is_recent(date_str):
                    print(f"  Stängd men under 1 år gammal, tar med: {res.get('title', '')}")
                else:
                    print(f"  Hoppar över stängd annons (>1 år): {res.get('title', '')}")
                    continue

            if is_linkedin and not any(loc in snippet or loc in title for loc in ALLOWED_LOCATIONS):
                print(f"  Hoppar över annons utanför SE/DK: {res.get('title', '')}")
                continue

            filtered.append({
                "title": res.get("title", ""),
                "link": link,
                "snippet": res.get("snippet", ""),
                "query": query,
                "date": date_str,
            })
        return filtered
    except Exception as e:
        print(f"Fel vid sökning '{query}': {e}")
        return []


def run_scraper() -> list[dict]:
    seen = load_seen()
    new_results = []

    for query in QUERIES:
        print(f"Söker: {query}")
        results = search_google(query)
        for r in results:
            if r["link"] not in seen:
                seen.add(r["link"])
                new_results.append(r)

    save_seen(seen)
    print(f"\nHittade {len(new_results)} nya träffar.")
    return new_results


if __name__ == "__main__":
    results = run_scraper()
    for r in results:
        print(f"\n{r['title']}\n{r['link']}\n{r['snippet']}")
