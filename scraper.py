import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
DATA_FILE = "found_companies.json"
RESULTS_FILE = "results.json"
BLOCKLIST_FILE = "blocklist.json"

QUERIES = [
    'site:linkedin.com/jobs "oracle forms" sweden',
    'site:linkedin.com/jobs "oracle forms" danmark',
    'site:linkedin.com/jobs "oracle forms" denmark',
    '"oracle forms" företag sverige',
    '"oracle forms" virksomhed danmark',
    '"oracle forms" consultant sweden',
    '"oracle forms" developer denmark',
    'site:linkedin.com/jobs "oracle apex" sweden',
    'site:linkedin.com/jobs "oracle apex" danmark',
    'site:linkedin.com/jobs "oracle apex" denmark',
    'site:linkedin.com/jobs "pl/sql" sweden',
    'site:linkedin.com/jobs "pl/sql" danmark',
    'site:linkedin.com/jobs "pl/sql" denmark',
    '"oracle apex" företag sverige',
    '"oracle apex" virksomhed danmark',
    '"pl/sql" konsult sverige',
    '"pl/sql" konsulent danmark',
]

CLOSED_PHRASES = [
    "no longer accepting applications",
    "no longer accepting",
    "job no longer available",
]


def load_seen() -> set:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(DATA_FILE, "w") as f:
        json.dump(list(seen), f)


def load_blocklist() -> set:
    """Hämtar blocklistan direkt från GitHub så att webbgränssnittets ändringar alltid används."""
    github_token = os.environ.get("GITHUB_TOKEN")
    repo = "nivelloDEV/oracle-forms-agent"
    url = f"https://api.github.com/repos/{repo}/contents/{BLOCKLIST_FILE}"
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            print("Ingen blocklista hittad, fortsätter utan.")
            return set()
        r.raise_for_status()
        import base64
        data = json.loads(base64.b64decode(r.json()["content"].replace("\n", "")).decode())
        print(f"Laddade blocklista med {len(data)} poster.")
        return set(data)
    except Exception as e:
        print(f"Kunde inte hämta blocklista: {e}")
        return set()


def save_results(results: list):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    date_str = date_str.lower().strip()
    now = datetime.now()
    try:
        if "day" in date_str:
            return now - timedelta(days=int(date_str.split()[0]))
        elif "week" in date_str:
            return now - timedelta(weeks=int(date_str.split()[0]))
        elif "month" in date_str:
            return now - timedelta(days=int(date_str.split()[0]) * 30)
        elif "year" in date_str:
            return now - timedelta(days=int(date_str.split()[0]) * 365)
        else:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def is_recent(date_str: str, max_days: int = 365) -> bool:
    parsed = parse_date(date_str)
    if parsed is None:
        return True
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

            # Bygg fylligare beskrivning från rich_snippet
            rich = res.get("rich_snippet", {})
            extra_parts = []
            for d in [rich.get("top", {}), rich.get("bottom", {})]:
                for v in d.values():
                    if isinstance(v, str) and len(v) > 20 and v.lower() not in snippet:
                        extra_parts.append(v)
            full_snippet = res.get("snippet", "")
            if extra_parts:
                full_snippet += " | " + " | ".join(extra_parts[:2])

            filtered.append({
                "title": res.get("title", ""),
                "link": link,
                "snippet": full_snippet,
                "query": query,
                "date": date_str,
            })
        return filtered
    except Exception as e:
        print(f"Fel vid sökning '{query}': {e}")
        return []


def run_scraper() -> list[dict]:
    seen = load_seen()
    blocklist = load_blocklist()
    all_results = []
    seen_links_this_run = set()

    for query in QUERIES:
        print(f"Söker: {query}")
        results = search_google(query)
        for r in results:
            if r["link"] in seen_links_this_run:
                continue
            if r["link"] in blocklist:
                print(f"  Blockerad, hoppar över: {r['title']}")
                continue
            seen_links_this_run.add(r["link"])
            r["is_new"] = r["link"] not in seen
            all_results.append(r)

    # Nya först
    all_results.sort(key=lambda r: not r["is_new"])

    # Uppdatera minne
    seen.update(seen_links_this_run)
    save_seen(seen)

    # Spara resultat för GitHub Pages
    save_results(all_results)

    new_count = sum(1 for r in all_results if r["is_new"])
    print(f"\nHittade {len(all_results)} träffar ({new_count} nya, {len(all_results) - new_count} återkommande).")
    return all_results


if __name__ == "__main__":
    results = run_scraper()
    for r in results:
        status = "NY" if r["is_new"] else "ÅTERKOMMANDE"
        print(f"\n[{status}] {r['title']}\n{r['link']}\n{r['snippet']}")
