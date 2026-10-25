#!/usr/bin/env python3
"""Collect contact details for the top-N overall reviewers.

For each reviewer: fetch the OpenReview profile (homepage, masked email
domains, scholarly links), crawl the homepage (plus its JS bundles and a few
contact-like pages), and fall back to the first page of their recent papers
on their ACL Anthology author page. Candidate addresses are ranked against
the OpenReview email domains and the reviewer's name. Every row is meant to be
checked by a human before anything is sent; output lands in data/contacts/
(gitignored).
"""

import csv
import html
import json
import re
import subprocess
import threading
import time
import tomllib
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import unquote, urljoin, urlparse

import requests
import typer
from requests.adapters import HTTPAdapter
from rich.console import Console
from urllib3.util.retry import Retry

from src.map_openreview_profiles import (
    get_access_token_from_env,
    load_auth_cookies_from_env,
)

app = typer.Typer(help=__doc__)
console = Console()

API = "https://api2.openreview.net"
SITE = "https://arrgreatreviewers.org"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
MAX_EXTRA_PAGES = 4
MAX_SCRIPTS = 3
MAX_PAPERS = 25
MAX_ARXIV_PAPERS = 15
ARXIV_DELAY_SECONDS = 3  # arXiv asks API clients for one request every 3 seconds
MAX_PAGE_BYTES = 2_000_000
MAX_PDF_BYTES = 30_000_000
EXTRA_PAGE_HINT = re.compile(r"contact|about|cv|bio|me\b|people|home", re.I)

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
# "name [at] host [dot] edu", "name(at)host.edu", "name {at} host . edu"
BRACKETED_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*[\[\(\{<]\s*(?:at|AT|@)\s*[\]\)\}>]\s*"
    r"([A-Za-z0-9-]+(?:\s*(?:[\[\(\{<]\s*(?:dot|DOT|\.)\s*[\]\)\}>]|\.|\s+dot\s+)\s*[A-Za-z0-9-]+)+)"
)
# "name at host dot edu" (bare words; requires a "dot" word to avoid prose)
BARE_RE = re.compile(
    r"\b([A-Za-z0-9._%+-]+)\s+(?:at|AT)\s+([A-Za-z0-9-]+(?:\s+(?:dot|DOT)\s+[A-Za-z0-9-]+)+)\b"
)
DOT_RE = re.compile(
    r"\s*(?:[\[\(\{<]\s*(?:dot|DOT|\.)\s*[\]\)\}>]|\s+(?:dot|DOT)\s+|\.)\s*"
)
# Paper headers: "{alice, bob}@uni.edu" or "{alice|bob}@uni.edu"
GROUPED_RE = re.compile(
    r"\{([^{}@]{1,300})\}\s*@\s*([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)"
)
CFEMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
HREF_ATTR_RE = re.compile(r'href=(["\'])([^"\']+)\1', re.I)
HREF_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
SCRIPT_SRC_RE = re.compile(r'<script\b[^>]*src=["\']([^"\']+)["\']', re.I)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)

JUNK_DOMAINS = {
    "example.com",
    "domain.com",
    "email.com",
    "sentry.io",
    "wixpress.com",
    "sentry-next.wixpress.com",
    "github.com",
    "users.noreply.github.com",
    "arxiv.org",
    "aclweb.org",
}
JUNK_LOCAL = re.compile(
    r"^(noreply|no-reply|webmaster|admin|info|support|example|name|your|email|user"
    r"|firstname\.lastname|first\.last|permissions|help)$",
    re.I,
)
# Filenames and asset paths that look like addresses (logo@2x.png, talk@acl24.pdf).
JUNK_SUFFIX = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|css|js|pdf|html?|php|jsp|aspx?|txt|zip|mp4)$", re.I
)
BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


# ---------------------------------------------------------------- OpenReview


class OpenReviewClient:
    """Authenticated OpenReview API client that refreshes an expired access token once."""

    def __init__(self) -> None:
        # Plain session (no Retry-After sleeping): a rate limit should surface, not stall for an hour.
        self.session = requests.Session()
        for cookie in load_auth_cookies_from_env():
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie["domain"],
                path=cookie["path"],
            )
        self.token = get_access_token_from_env()

    def _refresh(self) -> None:
        resp = self.session.post(f"{API}/refreshToken", timeout=30)
        if resp.status_code != 200:
            console.print(
                "[red]OpenReview token expired and refresh failed; log in again and re-export cookies.[/red]"
            )
            raise typer.Exit(1)
        self.token = resp.json()["token"]

    def profiles(self, profile_ids: List[str]) -> Dict[str, Dict]:
        """Fetch profiles in batches (one request per 100 ids; the API allows ~100 requests/hour)."""
        found: Dict[str, Dict] = {}
        for start in range(0, len(profile_ids), 100):
            batch = profile_ids[start : start + 100]
            for attempt in range(2):
                resp = self.session.post(
                    f"{API}/profiles/search",
                    json={"ids": batch},
                    headers={"Authorization": f"Bearer {self.token}"}
                    if self.token
                    else {},
                    timeout=60,
                )
                if resp.status_code == 401 and attempt == 0:
                    self._refresh()
                    continue
                if resp.status_code == 429:
                    console.print(
                        f"[red]OpenReview rate limit hit; retry in {resp.headers.get('Retry-After', '?')}s.[/red]"
                    )
                    raise typer.Exit(1)
                resp.raise_for_status()
                for profile in resp.json().get("profiles", []):
                    found[profile["id"]] = profile
                    # Profiles answer to any of their names' ids (e.g. ~Old_Name1).
                    for name in profile.get("content", {}).get("names", []):
                        if name.get("username"):
                            found.setdefault(name["username"], profile)
                break
        return found


# ------------------------------------------------------------------ Ranking


def load_top_reviewers(db_file: Path, top_n: int) -> List[Dict]:
    """Return reviewers holding an overall rank <= top_n, ordered by rank."""
    db = json.loads(db_file.read_text(encoding="utf-8"))
    top = []
    for openreview_id, reviewer in db.items():
        rank = next(
            (
                a["rank"]
                for a in reviewer.get("achievements", [])
                if a["type"].startswith("overall_top_")
            ),
            None,
        )
        if rank is not None and rank <= top_n:
            top.append({**reviewer, "openreview_id": openreview_id, "rank": rank})
    return sorted(top, key=lambda r: r["rank"])


# --------------------------------------------------------- Email extraction


def _decode_cfemail(hexstr: str) -> str:
    key = int(hexstr[:2], 16)
    return "".join(
        chr(int(hexstr[i : i + 2], 16) ^ key) for i in range(2, len(hexstr), 2)
    )


def _rot36(text: str, shift: int) -> str:
    return "".join(
        BASE36[(BASE36.index(c) + shift) % 36] if c in BASE36 else c
        for c in text.lower()
    )


def decode_shifted_mailto(href: str) -> Optional[str]:
    """Undo a base-36 Caesar shift of a mailto: href (used e.g. by uni-stuttgart.de)."""
    scheme, sep, _ = href.partition(":")
    if not sep or len(scheme) != 6 or scheme.lower() == "mailto" or "@" not in href:
        return None
    for shift in range(1, 36):
        if _rot36(scheme, shift) == "mailto":
            return _rot36(href, shift)
    return None


def _valid(email: str) -> bool:
    local, _, domain = email.rpartition("@")
    return (
        bool(local)
        and domain not in JUNK_DOMAINS
        and not JUNK_LOCAL.match(local)
        and not JUNK_SUFFIX.search(email)
    )


def _dedupe_valid(found: List[str]) -> List[str]:
    seen, out = set(), []
    for email in found:
        email = email.strip(".").lower()
        if email not in seen and EMAIL_RE.fullmatch(email) and _valid(email):
            seen.add(email)
            out.append(email)
    return out


def extract_emails(page: str) -> List[str]:
    """Extract plain, mailto, Cloudflare-protected, shifted, and spelled-out addresses."""
    found: List[str] = [_decode_cfemail(h) for h in CFEMAIL_RE.findall(page)]

    def _decode_href(m: re.Match) -> str:
        decoded = decode_shifted_mailto(html.unescape(m.group(2)))
        if decoded:
            found.append(decoded.removeprefix("mailto:").split("?")[0])
            return 'href=""'  # drop the ciphertext so it is not read as an address
        return m.group(0)

    page = HREF_ATTR_RE.sub(_decode_href, page)
    found += EMAIL_RE.findall(html.unescape(unquote(page)))
    text = html.unescape(TAG_RE.sub(" ", SCRIPT_STYLE_RE.sub(" ", page)))
    for regex in (BRACKETED_RE, BARE_RE):
        for local, domain in regex.findall(text):
            found.append(f"{local}@{DOT_RE.sub('.', domain)}")
    return _dedupe_valid(found)


def extract_paper_emails(text: str) -> List[str]:
    """Extract addresses from paper text, expanding "{a, b}@host" groups."""
    found: List[str] = []
    for group, domain in GROUPED_RE.findall(text):
        found += [
            f"{local.strip()}@{domain}"
            for local in re.split(r"[,|;\s]+", group)
            if local.strip()
        ]
    found += EMAIL_RE.findall(GROUPED_RE.sub(" ", text))
    return _dedupe_valid(found)


def _fold(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s.lower()) if c.isalnum() or c == " "
    )


UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _name_parts(names: List[str]) -> List[List[str]]:
    variants = {_fold(n) for n in names} | {
        _fold(n.lower().translate(UMLAUTS)) for n in names
    }
    out = []
    for variant in variants:
        parts = [p for p in variant.replace("-", " ").split() if len(p) >= 2]
        if parts:
            out.append(parts)
    return out


def name_matches(email: str, names: List[str]) -> bool:
    """Whether the local part clearly belongs to any of `names` (all OpenReview names).

    Accepts: the surname anywhere (short surnames like "wang" also need the given
    name or its initial), the given name as a prefix, or the initials.
    """
    local = _fold(email.partition("@")[0]).replace(" ", "")
    if not local:
        return False
    for parts in _name_parts(names):
        given, surname = parts[0], parts[-1]
        if local == "".join(p[0] for p in parts):
            return True
        if len(given) >= 3 and local.startswith(given):
            return True
        if len(surname) >= 3 and surname in local:
            if len(surname) >= 5 or given in local or given[0] in (local[0], local[-1]):
                return True
    return False


def initials_match(email: str, names: List[str]) -> bool:
    """Institutional usernames built from initials: th656, nv2006, nvit, cli, wolf.

    Too weak on its own (any co-author could match); only trusted together with a
    confirmed domain.
    """
    local = re.sub(r"[^a-z]", "", _fold(email.partition("@")[0]))
    if not local:
        return False
    for parts in _name_parts(names):
        given, surname = parts[0], parts[-1]
        initials = "".join(p[0] for p in parts)
        if local in (initials, surname, given[0] + surname):
            return True
        if (
            local.startswith(given[0])
            and len(local) >= 3
            and surname.startswith(local[1:])
        ):
            return True
    return False


FREEMAIL = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "icloud.com", "me.com", "proton.me", "protonmail.com",
    "163.com", "126.com", "qq.com", "foxmail.com", "mail.ru", "yandex.ru",
    "naver.com",
}  # fmt: skip


def domain_matches(email: str, or_domains: List[str]) -> bool:
    domain = email.partition("@")[2]
    return any(
        domain == d or domain.endswith("." + d) or d.endswith("." + domain)
        for d in or_domains
    )


def institutional_match(email: str, or_domains: List[str]) -> bool:
    """Domain is on the OpenReview profile and is not a shared provider like gmail."""
    return email.partition("@")[2] not in FREEMAIL and domain_matches(email, or_domains)


def score_email(email: str, or_domains: List[str], names: List[str]) -> int:
    """Domain on the OpenReview profile: +3 (institutional) or +2 (gmail & co., which
    many namesakes share); +1 when the local part resembles a name.

    Initials-style usernames count as a name only on a confirmed institutional domain.
    """
    if institutional_match(email, or_domains):
        return 3 + (name_matches(email, names) or initials_match(email, names))
    freemail = email.partition("@")[2] in FREEMAIL and domain_matches(email, or_domains)
    return 2 * freemail + name_matches(email, names)


def confidence(score: int) -> str:
    return "high" if score >= 3 else "medium" if score >= 1 else "low"


# ------------------------------------------------------------------ Fetching


class Fetched(NamedTuple):
    url: str
    body: bytes
    error: str  # empty on success
    encoding: str = "utf-8"

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding, errors="replace")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    # Ride out transient 429/5xx from shared hosts (ACL Anthology, GitHub Pages) with short backoff.
    retry = Retry(
        total=4,
        connect=1,
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=1,
        backoff_max=20,
        respect_retry_after_header=False,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def fetch(
    session: requests.Session,
    url: str,
    accept: Tuple[str, ...] = ("html",),
    max_bytes: int = MAX_PAGE_BYTES,
    params: Optional[Dict] = None,
) -> Fetched:
    """GET `url`; reject unexpected content types before downloading and cap the body size."""
    try:
        with session.get(
            url, params=params, timeout=(10, 30), allow_redirects=True, stream=True
        ) as resp:
            if resp.status_code != 200:
                return Fetched(url, b"", f"HTTP {resp.status_code}")
            ctype = resp.headers.get("content-type", accept[0]).lower()
            if not any(a in ctype for a in accept):
                return Fetched(url, b"", f"unexpected content-type {ctype}")
            body = bytearray()
            for chunk in resp.iter_content(65536):
                body += chunk
                if len(body) > max_bytes:
                    break
            return Fetched(resp.url, bytes(body), "", resp.encoding or "utf-8")
    except requests.RequestException as exc:
        return Fetched(url, b"", f"unreachable ({type(exc).__name__})")


def crawl_homepage(homepage: str, names: List[str]) -> Dict:
    """Homepage, then same-site JS bundles (SPA sites), then a few contact-like pages."""
    session = _session()
    result: Dict = {"emails": {}, "status": ""}
    page = fetch(session, homepage)
    if page.error:
        result["status"] = f"homepage {page.error}"
        return result

    def harvest(fetched: Fetched, require_name: bool = False) -> None:
        if not fetched.error:
            for email in extract_emails(fetched.text):
                if not require_name or name_matches(email, names):
                    result["emails"].setdefault(email, fetched.url)

    harvest(page)
    host = urlparse(page.url).netloc
    if not result["emails"]:
        scripts = [
            urljoin(page.url, src)
            for src in SCRIPT_SRC_RE.findall(page.text)
            if urlparse(urljoin(page.url, src)).netloc == host
        ]
        for url in scripts[:MAX_SCRIPTS]:
            # Bundles embed library authors' addresses, so only keep the reviewer's own.
            harvest(
                fetch(session, url, accept=("javascript", "ecmascript", "text/plain")),
                require_name=True,
            )
    if not result["emails"]:
        extra: List[str] = []
        for href, label in HREF_RE.findall(page.text):
            url = urljoin(page.url, href.strip()).split("#")[0]
            if (
                urlparse(url).netloc != host
                or url.rstrip("/") == page.url.rstrip("/")
                or url in extra
            ):
                continue
            if EXTRA_PAGE_HINT.search(href) or EXTRA_PAGE_HINT.search(
                TAG_RE.sub("", label)
            ):
                extra.append(url)
        for url in extra[:MAX_EXTRA_PAGES]:
            harvest(fetch(session, url))
    result["status"] = "" if result["emails"] else "no email on homepage"
    return result


# -------------------------------------------------------- Paper fallback


# Single-paper PDFs (2024.acl-long.12.pdf, P19-1001.pdf); skips whole-volume PDFs (*.0.pdf).
ANTHOLOGY_PDF_RE = re.compile(
    r"href=[\"']?(https://aclanthology\.org/(?:\d{4}\.[a-z0-9-]+\.(?!0\.)\d+|[A-Z]\d{2}-\d{4})\.pdf)"
)
META_REFRESH_RE = re.compile(
    r"<meta\s+http-equiv=[\"']?refresh[\"']?\s+content=[\"']?\d+;\s*url=([^\"'>\s]+)",
    re.I,
)


def recent_paper_pdfs(
    session: requests.Session, anthology_url: str
) -> Tuple[List[str], str]:
    """PDF URLs from the person's ACL Anthology author page, newest first (page order).

    Renamed authors get a meta-refresh stub pointing at their new page; follow it once.
    """
    fetched = fetch(session, anthology_url)
    if not fetched.error and (redirect := META_REFRESH_RE.search(fetched.text)):
        fetched = fetch(session, urljoin(fetched.url, redirect.group(1)))
    if fetched.error:
        return [], f"ACL Anthology page {fetched.error}"
    pdfs = list(dict.fromkeys(ANTHOLOGY_PDF_RE.findall(fetched.text)))
    return pdfs, "" if pdfs else "no papers on ACL Anthology page"


def first_page_text(session: requests.Session, pdf_url: str) -> str:
    fetched = fetch(
        session,
        pdf_url,
        accept=("pdf", "octet-stream"),
        max_bytes=MAX_PDF_BYTES,
    )
    if fetched.error:
        return ""
    proc = subprocess.run(
        ["pdftotext", "-l", "1", "-enc", "UTF-8", "-", "-"],
        input=fetched.body,
        capture_output=True,
        timeout=60,
    )
    return proc.stdout.decode("utf-8", errors="replace")


def scan_pdfs(
    session: requests.Session,
    pdfs: List[str],
    names: List[str],
    or_domains: List[str],
    domain_required: bool,
    before_each: Callable[[], None] = lambda: None,
) -> Dict[str, str]:
    """Collect the reviewer's addresses from paper first pages, newest first.

    Headers list every co-author, so a candidate needs a clear name match, or an
    initials-style username on a domain from the reviewer's OpenReview profile. Stops
    at the first domain-confirmed address; `domain_required` keeps only those.
    """
    found: Dict[str, str] = {}
    for pdf in pdfs:
        before_each()
        for email in extract_paper_emails(first_page_text(session, pdf)):
            confirmed = institutional_match(email, or_domains) and (
                name_matches(email, names) or initials_match(email, names)
            )
            if confirmed or (not domain_required and name_matches(email, names)):
                found.setdefault(email, pdf)
        if any(score_email(e, or_domains, names) == 4 for e in found):
            break
    return found


def search_anthology(
    anthology_url: str, names: List[str], or_domains: List[str]
) -> Dict:
    """Scan the first pages of recent papers on the reviewer's ACL Anthology page."""
    session = _session()
    if not anthology_url:
        return {"emails": {}, "status": "no ACL Anthology link on OpenReview"}
    pdfs, error = recent_paper_pdfs(session, anthology_url)
    if not pdfs:
        return {"emails": {}, "status": error}
    pdfs = pdfs[:MAX_PAPERS]
    emails = scan_pdfs(session, pdfs, names, or_domains, domain_required=False)
    status = "" if emails else f"no matching email in {len(pdfs)} Anthology papers"
    return {"emails": emails, "status": status}


class ArxivThrottle:
    """Serialise arXiv requests to one every ARXIV_DELAY_SECONDS."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last = 0.0

    def __call__(self) -> None:
        with self.lock:
            wait = self.last + ARXIV_DELAY_SECONDS - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()


def search_arxiv(
    name: str, names: List[str], or_domains: List[str], throttle: ArxivThrottle
) -> Dict:
    """Scan recent arXiv papers by author name.

    A name search returns every namesake, so only domain-confirmed addresses count.
    """
    session = _session()
    throttle()
    feed = fetch(
        session,
        "https://export.arxiv.org/api/query",
        accept=("xml",),
        params={
            "search_query": f'au:"{name}"',
            "sortBy": "submittedDate",
            "max_results": MAX_ARXIV_PAPERS,
        },
    )
    if feed.error:
        return {"emails": {}, "status": f"arXiv search {feed.error}"}
    ids = re.findall(r"<id>https?://arxiv\.org/abs/([^<]+?)(?:v\d+)?</id>", feed.text)
    pdfs = [f"https://arxiv.org/pdf/{i}" for i in ids]
    emails = scan_pdfs(
        session, pdfs, names, or_domains, domain_required=True, before_each=throttle
    )
    status = "" if emails else f"no domain-confirmed email in {len(pdfs)} arXiv papers"
    return {"emails": emails, "status": status}


# ---------------------------------------------------------------------- CLI


FIELDS = [
    "rank",
    "name",
    "institution",
    "total_recognized",
    "total_reviewed",
    "site_profile_url",
    "openreview_url",
    "homepage",
    "openreview_email_domains",
    "email",
    "confidence",
    "email_source",
    "other_candidates",
    "status",
    "dblp",
    "gscholar",
    "aclanthology",
    "semantic_scholar",
]


def _apply(row: Dict, emails: Dict[str, str], stage: str, note: str) -> None:
    """Merge `emails` into the row's candidates and re-pick the best-scoring one."""
    candidates = row["candidates"]
    for email, source in emails.items():
        candidates.setdefault(email, source)
    row["status"].append(f"{stage}: {len(emails)} found" if emails else note)
    if not candidates:
        return
    ranked = sorted(
        candidates,
        key=lambda e: -score_email(e, row["openreview_email_domains"], row["names"]),
    )
    row["email"] = ranked[0]
    row["email_source"] = candidates[ranked[0]]
    row["confidence"] = confidence(
        score_email(ranked[0], row["openreview_email_domains"], row["names"])
    )
    row["other_candidates"] = ranked[1:]


def load_manual_contacts(path: Path) -> Dict[str, Dict]:
    """Hand-verified addresses keyed by OpenReview id (gitignored, like the output).

    ["~Jane_Doe1"]
    email = "jane@example.org"
    source = "https://aclanthology.org/2024.acl-long.1.pdf"
    note = "listed under her name in the paper header"
    """
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


@app.command()
def main(
    top_n: int = typer.Option(100, help="Collect contacts for overall ranks 1..N."),
    db_file: Path = typer.Option(Path("data/reviewers_database.json")),
    out_dir: Path = typer.Option(Path("data/contacts")),
    workers: int = typer.Option(8, help="Parallel homepage crawls."),
    manual_file: Path = typer.Option(
        Path("data/contacts/manual_contacts.toml"),
        help="Hand-verified addresses that override automatic results.",
    ),
):
    reviewers = load_top_reviewers(db_file, top_n)
    console.print(f"Top {top_n}: {len(reviewers)} reviewers")

    profiles = OpenReviewClient().profiles(
        [r["openreview_id"] for r in reviewers if r["openreview_id"].startswith("~")]
    )
    rows = []
    for r in reviewers:
        profile = profiles.get(r["openreview_id"])
        content = (profile or {}).get("content", {})
        domains = sorted(
            {e.split("@", 1)[1].lower() for e in content.get("emails", []) if "@" in e}
        )
        rows.append(
            {
                "rank": r["rank"],
                "openreview_id": r["openreview_id"],
                "name": r["name"],
                # Every name on the profile (former names, transliterations) for email matching.
                "names": list(
                    dict.fromkeys(
                        [r["name"]]
                        + [
                            n["fullname"]
                            for n in content.get("names", [])
                            if n.get("fullname")
                        ]
                    )
                ),
                "institution": r["institution"],
                "total_recognized": r["total_recognized"],
                "total_reviewed": r["total_reviewed"],
                "site_profile_url": f"{SITE}/reviewer/{r['openreview_id'].replace('~', '').replace('/', '-')}/",
                "openreview_url": f"https://openreview.net/profile?id={r['openreview_id']}",
                "homepage": (content.get("homepage") or "").strip(),
                "openreview_email_domains": domains,
                "dblp": content.get("dblp", ""),
                "gscholar": content.get("gscholar", ""),
                "aclanthology": content.get("aclanthology", ""),
                "semantic_scholar": content.get("semanticScholar", ""),
                "status": [] if profile else ["openreview profile not found"],
                "candidates": {},
            }
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        crawls = list(
            pool.map(
                lambda row: crawl_homepage(row["homepage"], row["names"])
                if row["homepage"]
                else {"emails": {}, "status": "no homepage on OpenReview"},
                rows,
            )
        )
    for row, crawl in zip(rows, crawls):
        _apply(row, crawl["emails"], "homepage", crawl["status"])

    def unconfirmed() -> List[Dict]:
        return [row for row in rows if row.get("confidence") != "high"]

    # Paper fallbacks for everyone without a domain-confirmed address; few workers,
    # to stay polite to the ACL Anthology and arXiv.
    todo = unconfirmed()
    console.print(f"Searching ACL Anthology papers for {len(todo)} reviewers")
    with ThreadPoolExecutor(max_workers=3) as pool:
        searches = list(
            pool.map(
                lambda row: search_anthology(
                    row["aclanthology"], row["names"], row["openreview_email_domains"]
                ),
                todo,
            )
        )
    for row, search in zip(todo, searches):
        _apply(row, search["emails"], "anthology", search["status"])

    todo = unconfirmed()
    console.print(f"Searching arXiv papers for {len(todo)} reviewers")
    throttle = ArxivThrottle()
    with ThreadPoolExecutor(max_workers=2) as pool:
        searches = list(
            pool.map(
                lambda row: search_arxiv(
                    row["name"], row["names"], row["openreview_email_domains"], throttle
                ),
                todo,
            )
        )
    for row, search in zip(todo, searches):
        _apply(row, search["emails"], "arxiv", search["status"])

    manual = load_manual_contacts(manual_file)
    for row in rows:
        if entry := manual.get(row["openreview_id"]):
            if row.get("email") and row["email"] != entry["email"]:
                row["other_candidates"] = [row["email"], *row["other_candidates"]]
            row["email"] = entry["email"]
            row["email_source"] = entry.get("source", "")
            row["confidence"] = "manual"
            row["status"].append(f"manual: {entry.get('note', '')}".rstrip(": "))

    out_dir.mkdir(parents=True, exist_ok=True)
    json_file = out_dir / f"top{top_n}_contacts.json"
    csv_file = out_dir / f"top{top_n}_contacts.csv"
    json_file.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "status": "; ".join(row["status"]),
                    "openreview_email_domains": "; ".join(
                        row["openreview_email_domains"]
                    ),
                    "other_candidates": "; ".join(row.get("other_candidates", [])),
                }
            )

    counts: Dict[str, int] = {}
    for row in rows:
        key = row.get("confidence", "none")
        counts[key] = counts.get(key, 0) + 1
    console.print(f"Email confidence: {counts}")
    console.print(f"Wrote {csv_file} and {json_file}")


if __name__ == "__main__":
    app()
