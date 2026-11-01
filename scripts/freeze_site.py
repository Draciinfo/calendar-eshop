#!/usr/bin/env python3
"""Export the public calendar into two standalone static sites, without Django."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
HOSTS = {"cs": "kalendar.draci.info", "en": "calendar.draci.info"}
INTERNAL = set(HOSTS.values())
PAGES = {"/", "/kontakt/", "/contact/", "/obchodni-podminky/",
         "/terms-conditions/", "/souhlas-s-poskytnutim-osobnich-udaju/",
         "/personal-information-protection/"}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
              ".css", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".docx"}
NOTICE = {
    "cs": ("Archiv kalendářů Draci.info", "Nové kalendáře už nevydáváme. "
           "Tento web slouží pouze k prohlížení minulých ročníků. "
           "Objednávky ani přihlášení k newsletteru již nepřijímáme."),
    "en": ("Draci.info calendar archive", "We no longer publish new calendars. "
           "This website is a read-only archive of past editions. "
           "Orders and newsletter subscriptions are closed."),
}


def is_page(path):
    path = path or "/"
    return path in PAGES or re.fullmatch(r"/20\d{2}/", path) is not None


def normalized(url):
    parts = urlsplit(url)
    host = parts.hostname
    # The two language hosts share the same public media and static files.
    if host in INTERNAL and parts.path.startswith(("/media/", "/static/", "/resize/", "/crop/")):
        host = HOSTS["cs"]
    if parts.scheme not in ("http", "https") or not host:
        raise ValueError(f"Unsupported asset URL: {url}")
    return urlunsplit(("https", host, parts.path, parts.query, ""))


class Exporter:
    def __init__(self, output, cache, offline=False):
        self.output = output
        self.cache = cache
        self.offline = offline
        self.assets = {}
        self.pages = {}
        self.cache.mkdir(parents=True, exist_ok=True)

    def fetch(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        cached = self.cache / key
        if cached.exists():
            return cached.read_bytes()
        if self.offline:
            raise RuntimeError(f"Not cached (offline mode): {url}")
        error = None
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "Draci.info-static-archive/1.0"})
                with urlopen(request, timeout=40) as response:
                    if urlsplit(response.url).hostname not in {urlsplit(url).hostname}:
                        raise ValueError(f"Unexpected cross-host redirect: {url} -> {response.url}")
                    body = response.read()
                cached.write_bytes(body)
                return body
            except Exception as exc:
                error = exc
                time.sleep(attempt + 1)
        raise RuntimeError(f"Cannot download {url}: {error}") from error

    def asset(self, url, base):
        if url.startswith(("data:", "#")):
            return url
        absolute, fragment = urldefrag(urljoin(base, url))
        absolute = normalized(absolute)
        if absolute not in self.assets:
            suffix = Path(urlsplit(absolute).path).suffix.lower()
            if urlsplit(absolute).hostname == "fonts.googleapis.com":
                suffix = ".css"
            if suffix not in EXTENSIONS:
                raise ValueError(f"Unsupported asset type: {absolute}")
            digest = hashlib.sha256(absolute.encode()).hexdigest()[:24]
            self.assets[absolute] = f"/assets/{digest}{suffix}"
        return self.assets[absolute] + (f"#{fragment}" if fragment else "")

    def css(self, text, base):
        # Source maps are build-time data, not archive dependencies.
        text = re.sub(r"/\*[#@]\s*sourceMappingURL=.*?\*/", "", text, flags=re.S)
        # The live Font Awesome bundle references a missing WOFF2 file (404).
        # Keep its existing WOFF/TTF fallbacks instead of preserving that broken request.
        text = re.sub(r"url\([^)]*fontawesome-webfont\.woff2[^)]*\)"
                      r"\s*format\(['\"]woff2['\"]\)\s*,?", "", text)
        return CSS_URL.sub(lambda match: 'url("' + self.asset(match[2], base) + '")', text)

    def prepare_page(self, raw, url, language):
        soup = BeautifulSoup(raw, "html.parser")
        if not soup.html or not soup.body or not soup.select_one("nav"):
            raise ValueError(f"Not a calendar page: {url}")
        soup.html["lang"] = language
        for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
            comment.extract()
        # Replace all legacy scripts, including newsletter AJAX, analytics and jQuery.
        for element in soup.select("script, iframe, object, embed, form, input, textarea, select, "
                                   ".newsletter, #buy, a.cart"):
            element.decompose()
        for element in soup.find_all(True):
            for attr in list(element.attrs):
                if attr.lower().startswith("on"):
                    del element[attr]
        for dropdown in list(soup.select(".dropdown")):
            if dropdown.select_one('a[href*="currency="]'):
                dropdown.decompose()
        for link in list(soup.select("#about a[href]")):
            if re.search(r"objedn|orders?|pre.?order|buy", link.get_text(" "), re.I) or \
                    "forms.gle/" in link["href"]:
                paragraph = link.find_parent("p")
                (paragraph or link).decompose()
            elif urlsplit(link["href"]).fragment == "preview":
                link["href"] = "#preview"
        for link in list(soup.select('a[href]')):
            href = link["href"].strip()
            absolute = urlsplit(urljoin(url, href))
            if href == "#buy":
                link["href"] = "#preview"
                link.string = "Prohlédnout kalendář" if language == "cs" else "Look inside"
            elif absolute.hostname in INTERNAL and not is_page(absolute.path) and \
                    not absolute.path.startswith(("/media/", "/static/", "/resize/", "/crop/")):
                link.unwrap()
            elif absolute.scheme.lower() in ("javascript", "vbscript", "data"):
                link.unwrap()
        for item in soup.select(".timeline > li"):
            if not item.select_one(".timeline-panel"):
                heading = item.select_one("h4")
                if heading:
                    heading.string = "Archiv" if language == "cs" else "Archive"
        for item in soup.select(".navbar-nav > li"):
            if not item.get_text(strip=True) and not item.select_one("a"):
                item.decompose()
        toggle = soup.select_one(".navbar-toggle")
        if toggle:
            toggle["aria-expanded"] = "false"
            toggle["aria-controls"] = "bs-example-navbar-collapse-1"

        notice = soup.new_tag("aside", attrs={"class": "archive-notice", "aria-label": NOTICE[language][0]})
        title = soup.new_tag("p")
        strong = soup.new_tag("strong")
        strong.string = NOTICE[language][0]
        title.append(strong)
        notice.append(title)
        paragraph = soup.new_tag("p")
        paragraph.string = NOTICE[language][1]
        notice.append(paragraph)
        if "podminky" in url or "terms-" in url or "udaju" in url or "protection" in url:
            paragraph = soup.new_tag("p")
            paragraph.string = ("Níže je historické znění dokumentu z doby provozu e-shopu."
                                if language == "cs" else
                                "The document below is a historical copy from when the shop was operating.")
            notice.append(paragraph)
        section = soup.select_one("body > section")
        if section:
            container = section.select_one(".container")
            (container if container is not None else section).insert(0, notice)
        else:
            soup.select_one("nav").insert_after(notice)

        for element in soup.select("[style]"):
            element["style"] = self.css(element["style"], url)
        for element in soup.select("style"):
            element.string = self.css(element.get_text(), url)
        for element in soup.select("img[src], source[src]"):
            element["src"] = self.asset(element["src"], url)
        for element in soup.select("[srcset]"):
            raise ValueError(f"srcset needs explicit processing: {url}")
        for element in soup.select('meta[property="og:image"]'):
            element["content"] = self.asset(element["content"], url)
        for element in soup.select('link[href]'):
            if set(element.get("rel", [])) & {"stylesheet", "icon", "shortcut"}:
                element["href"] = self.asset(element["href"], url)
            else:
                element.decompose()

        discovered = set()
        for link in soup.select("a[href]"):
            href = link["href"].strip()
            absolute = urlsplit(urljoin(url, href))
            if href.startswith("#") or absolute.scheme in ("mailto", "tel"):
                continue
            if absolute.hostname in INTERNAL:
                if is_page(absolute.path):
                    if absolute.hostname == urlsplit(url).hostname:
                        discovered.add(absolute.path or "/")
                        link["href"] = (absolute.path or "/") + (f"#{absolute.fragment}" if absolute.fragment else "")
                    else:
                        link["href"] = "https://" + absolute.hostname + (absolute.path or "/")
                else:
                    link["href"] = self.asset(href, url)
            if link.get("target") == "_blank":
                # Preserve gallery grouping in rel; add opener protection to external links.
                link["rel"] = list(dict.fromkeys(link.get("rel", []) + ["noopener", "noreferrer"]))

        canonical = soup.new_tag("link", rel="canonical", href=url)
        soup.head.append(canonical)
        style_version = hashlib.sha256((SCRIPTS / "archive.css").read_bytes()).hexdigest()[:12]
        style = soup.new_tag("link", rel="stylesheet", href=f"/assets/archive.css?v={style_version}")
        soup.head.append(style)
        script = soup.new_tag("script", src="/assets/archive.js", defer="")
        soup.body.append(script)
        # Collapse indentation left by removed template blocks.
        return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", str(soup)), discovered

    def build(self):
        for language, host in HOSTS.items():
            pending = {"/"}
            visited = set()
            while pending:
                batch = sorted(pending - visited)
                if not batch:
                    break
                urls = [f"https://{host}{path}" for path in batch]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    documents = list(pool.map(self.fetch, urls))
                for path, url, raw in zip(batch, urls, documents):
                    html, links = self.prepare_page(raw, url, language)
                    target = self.output / language / path.strip("/") / "index.html"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(html, encoding="utf-8")
                    self.pages[url] = {"file": str(target.relative_to(self.output)),
                                       "source_sha256": hashlib.sha256(raw).hexdigest()}
                    visited.add(path)
                    pending.update(links)
                    print(f"Page {language}: {path}", flush=True)

        completed = set()
        while set(self.assets) - completed:
            batch = sorted(set(self.assets) - completed)
            with ThreadPoolExecutor(max_workers=8) as pool:
                bodies = list(pool.map(self.fetch, batch))
            for url, body in zip(batch, bodies):
                path = self.assets[url]
                if path.endswith(".css"):
                    body = self.css(body.decode("utf-8-sig"), url).encode("utf-8")
                for language in HOSTS:
                    target = self.output / language / path.lstrip("/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(body)
                completed.add(url)
            print(f"Downloaded {len(completed)} assets ({len(self.assets)} discovered)", flush=True)

        for language in HOSTS:
            root = self.output / language
            for name in ("archive.css", "archive.js"):
                shutil.copyfile(SCRIPTS / name, root / "assets" / name)
            (root / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
            title = "Stránka nenalezena" if language == "cs" else "Page not found"
            home = "Zpět do archivu" if language == "cs" else "Back to the archive"
            (root / "404.html").write_text(
                f'<!doctype html><html lang="{language}"><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{title}</title><h1>{title}</h1><p><a href="/">{home}</a></p></html>',
                encoding="utf-8")
        manifest = {"exported_at": datetime.now(timezone.utc).isoformat(),
                    "pages": self.pages, "assets": self.assets}
        (self.output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest


def verify(output):
    """Fail if a local dependency is missing or active legacy features survive."""
    problems = []
    for language in HOSTS:
        root = output / language
        pages = sorted(root.rglob("*.html"))
        if not (root / "index.html").exists():
            problems.append(f"Missing homepage: {root}")
        for page in pages:
            soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
            if soup.select("form, input, iframe, object, embed, .newsletter, #buy"):
                problems.append(f"Active shop/subscription element: {page}")
            for script in soup.select("script"):
                if script.get("src") != "/assets/archive.js" or script.get_text(strip=True):
                    problems.append(f"Unexpected script: {page}")
            refs = [tag[attr] for tag in soup.find_all(True)
                    for attr in ("href", "src") if tag.has_attr(attr)]
            refs += [match[2] for tag in soup.select("[style]")
                     for match in CSS_URL.finditer(tag["style"])]
            refs += [match[2] for tag in soup.select("style")
                     for match in CSS_URL.finditer(tag.get_text())]
            refs += [tag["content"] for tag in soup.select('meta[property="og:image"]')]
            for ref in refs:
                parts = urlsplit(ref)
                if parts.scheme or parts.netloc or not parts.path:
                    continue
                target = root / unquote(parts.path).lstrip("/")
                if parts.path.endswith("/"):
                    target /= "index.html"
                if not target.is_file():
                    problems.append(f"Missing link in {page}: {ref}")
            for tag in soup.select("img[src], link[rel=stylesheet]"):
                if not tag.get("src", tag.get("href", "")).startswith("/assets/"):
                    problems.append(f"External image/style dependency: {page}")
        for css in (root / "assets").glob("*.css"):
            for match in CSS_URL.finditer(css.read_text(encoding="utf-8")):
                ref = match[2]
                if ref.startswith(("data:", "#")):
                    continue
                path = urlsplit(ref).path
                if not ref.startswith("/assets/") or not (root / path.lstrip("/")).is_file():
                    problems.append(f"Missing/external CSS dependency in {css}: {ref}")
    if problems:
        raise RuntimeError("Archive verification failed:\n" + "\n".join(problems))
    print("Verified: all pages, images, styles and fonts are local; no forms or legacy scripts.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Only use previously downloaded cache")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output = ROOT / "archive"
    if args.verify_only:
        verify(output)
        return
    # A failed download or validation never replaces the previous archive.
    with tempfile.TemporaryDirectory(prefix=".archive-build-", dir=ROOT) as temporary:
        staging = Path(temporary) / "archive"
        staging.mkdir()
        manifest = Exporter(staging, ROOT / ".archive-cache", args.offline).build()
        verify(staging)
        output.mkdir(exist_ok=True)
        for name in ("cs", "en"):
            destination = output / name
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(staging / name), destination)
        shutil.copyfile(staging / "manifest.json", output / "manifest.json")
        print(f"Archive ready: {len(manifest['pages'])} pages, {len(manifest['assets'])} assets.")


if __name__ == "__main__":
    main()
