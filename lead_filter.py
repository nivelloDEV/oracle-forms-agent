"""
lead_filter.py – filtrerar bort brus ur SerpAPI-träffar för oracle-forms-agent.

Användning i agenten (efter att SerpAPI-resultaten hämtats):

    from lead_filter import filter_results
    keep, dropped = filter_results(results)   # results = lista av dicts från SerpAPI
    # keep    -> används i rapporten
    # dropped -> (result, orsak), bra att logga för felsökning

Varje result förväntas ha nycklarna "link", "title", "snippet" och ev. "date"
(standardfälten i SerpAPI:s organic_results).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# --------------------------------------------------------------------------
# 1. Domäner som aldrig ger leads
# --------------------------------------------------------------------------
BLOCKED_DOMAINS = {
    # egna sajter
    "nivello.se",
    # företagsregister / katalogsidor
    "hitta.se", "merinfo.se", "ratsit.se", "bolagsfakta.se", "allabolag.se",
    "eniro.se", "infobel.com", "kompass.com", "topograph.co",
    "largestcompanies.com", "fintel.io",
    # aggregerade jobbsökningar (inte enskilda annonser)
    "careerjet.dk", "careerjet.se", "glassdoor.com", "glassdoor.co.in",
    "jooble.org", "shine.com", "sulekha.com", "jobsinnetwork.com",
    # uppslagsverk, video, bloggplattformar
    "wikipedia.org", "youtube.com", "medium.com", "reddit.com",
    "wordpress.com", "facebook.com", "x.com", "twitter.com",
    # jämförelse- och säljsajter
    "sourceforge.net", "slashdot.org", "zoominfo.com", "europeanstack.io",
    "nobleprog.dk", "datavail.com", "talan.com",
    # Oracles egna marknadssidor och övrigt brus
    "oracle.com", "pluralsight.com", "cision.com", "timesofnews.com",
    "orpheus-portal.com", "tvimenning.no", "ponty-system.se",
}

# Toppdomäner/suffix som (i det här sammanhanget) i praktiken bara är spam
BLOCKED_SUFFIXES = (
    ".edu.br", ".gov.br", ".edu.in", ".ac.in", ".edu.pk", ".edu.ng",
    ".xyz", ".top", ".click", ".icu",
)

# URL-mönster för genererade spamsidor, t.ex.
# https://itt.fatecourinhos.edu.br/report/uGRJ9XHJJJX8/oracle_forms_12c_features
SPAM_PATH_PATTERNS = [
    re.compile(r"/report/[A-Za-z0-9]{8,}/"),
    re.compile(r"/(download|pdf|ebook)s?/[A-Za-z0-9]{8,}"),
    re.compile(r"[_-](updated[_-]version|free[_-]download|pdf[_-]download)", re.I),
    # LinkedIn-artiklar (content marketing från konsultbolag), inte annonser
    re.compile(r"linkedin\.com/pulse/", re.I),
]
SPAM_TITLE_PATTERNS = [
    re.compile(r"\bupdated version\b", re.I),
    re.compile(r"\bfree (pdf|download)\b", re.I),
    re.compile(r"\bcomparison\b", re.I),
    re.compile(r"\bvs\.?\s", re.I),
]

# --------------------------------------------------------------------------
# 2. Relevans: Oracle-teknik + Norden + jobb/uppdrag/företag
# --------------------------------------------------------------------------
TECH = re.compile(r"\boracle\s*(forms|reports|apex)\b|\bpl/?sql\b|\bforms\s*/\s*reports\b", re.I)
NORDIC = re.compile(
    r"\b(sverige|sweden|svensk|stockholm|göteborg|goteborg|malmö|malmo|lund|helsingborg|"
    r"uppsala|linköping|jönköping|danmark|denmark|dansk|københavn|kobenhavn|copenhagen|"
    r"aarhus|odense|hillerød|lyngby|swedish|danish|svenska|danske?)\b"
    r"|\.se/|\.dk/|//se\.|//dk\.|\.se$|\.dk$"
    # svensk/dansk text räcker som signal även utan landsnamn
    r"|\b(du arbetar|vi söker|oracleutvecklare|utvecklare|verket|kommun|region|"
    r"vi søger|udvikler|konsulent)\b",
    re.I,
)
INTENT = re.compile(
    r"\b(söker|vi söker|rekryter|anställ|uppdrag|konsultuppdrag|tjänst|ansök|"
    r"søger|stilling|job|jobs|hiring|developer|utvecklare|udvikler|consultant|konsult|"
    r"konsulent|architect|arkitekt|migrat|moderniser|moderniz)\w*",
    re.I,
)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "refid", "trackingid", "trk", "tl", "gclid", "fbclid", "scroll_to_id",
}

MAX_AGE_DAYS = 365


def _host(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.lower().removeprefix("www.")


def _domain_blocked(host: str) -> bool:
    if host.endswith(BLOCKED_SUFFIXES):
        return True
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


def normalize_url(url: str) -> str:
    """Tar bort spårningsparametrar, språkprefix och avslutande snedstreck,
    så att samma sida med olika parametrar inte räknas som 'ny'."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    # se.linkedin.com / dk.linkedin.com -> linkedin.com
    host = re.sub(r"^[a-z]{2}\.(linkedin\.com)$", r"\1", host)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def _parse_date(raw: str | None) -> date | None:
    """Tolkar SerpAPI-datum som '6 juli 2026', '15 dec. 2021',
    'för 3 dagar sedan', '3 days ago'."""
    if not raw:
        return None
    s = raw.lower().strip()
    today = date.today()

    m = re.search(r"(\d+)\s*(dag|dagar|day|days|vecka|veckor|week|weeks|månad|månader|month|months|år|year|years)", s)
    if m and ("sedan" in s or "ago" in s or s.startswith("för")):
        n, unit = int(m.group(1)), m.group(2)
        days = (
            n if unit.startswith(("dag", "day"))
            else n * 7 if unit.startswith(("veck", "week"))
            else n * 30 if unit.startswith(("mån", "month"))
            else n * 365
        )
        return today - timedelta(days=days)

    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(r"(\d{1,2})\s+([a-zåäö]+)\.?\s+(\d{4})", s)
    if m:
        mon = months.get(m.group(2)[:3])
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(1)))
            except ValueError:
                return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    return None


def classify(result: dict) -> str | None:
    """Returnerar None om träffen ska behållas, annars orsaken till att den sållas."""
    url = result.get("link", "")
    title = result.get("title", "") or ""
    snippet = result.get("snippet", "") or ""
    text = f"{title} {snippet} {url}"
    host = _host(url)

    if not host:
        return "saknar URL"
    if _domain_blocked(host):
        return f"blockerad domän ({host})"
    if any(p.search(url) for p in SPAM_PATH_PATTERNS):
        return "spam-URL"
    if any(p.search(title) for p in SPAM_TITLE_PATTERNS):
        return "spam-titel"
    if "ingen information att visa" in snippet.lower():
        return "tom sida"

    d = _parse_date(result.get("date"))
    if d and (date.today() - d).days > MAX_AGE_DAYS:
        return f"för gammal ({d.isoformat()})"

    if not TECH.search(text):
        return "ingen Forms/APEX/PL-SQL-koppling"
    if not NORDIC.search(text):
        return "inte Sverige/Danmark"
    if not INTENT.search(text):
        return "inget jobb/uppdrag/migrering"
    return None


def filter_results(results: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    keep: list[dict] = []
    dropped: list[tuple[dict, str]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for r in results:
        reason = classify(r)
        if reason is None:
            nurl = normalize_url(r.get("link", ""))
            ntitle = re.sub(r"\W+", " ", (r.get("title") or "").lower()).strip()
            if nurl in seen_urls or (ntitle and ntitle in seen_titles):
                reason = "dubblett"
            else:
                seen_urls.add(nurl)
                if ntitle:
                    seen_titles.add(ntitle)
                r["normalized_link"] = nurl  # använd denna för ny/återkommande-jämförelsen
                keep.append(r)
                continue
        dropped.append((r, reason))
    return keep, dropped
