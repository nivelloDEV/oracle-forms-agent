import os
import json
import requests
from datetime import datetime
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


def load_seen() -> set:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(DATA_FILE, "w") as f:
        json.dump(list(seen), f)


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
        return [
            {
                "title": res.get("title", ""),
                "link": res.get("link", ""),
                "snippet": res.get("snippet", ""),
                "query": query,
            }
            for res in results
        ]
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
