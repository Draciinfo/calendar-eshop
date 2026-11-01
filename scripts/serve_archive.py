#!/usr/bin/env python3
"""Preview both static language sites locally: Czech at /, English at /en/."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent / "archive"
LANGUAGE_PREFIXES = {"kalendar.draci.info": "", "calendar.draci.info": "/en"}
LINK = re.compile(r"(\b(?:href|src)\s*=\s*)([\"'])(.*?)(\2)", re.I)


def localize_links(html, english):
    def replace(match):
        value = match[3]
        url = urlsplit(value)
        if url.hostname in LANGUAGE_PREFIXES:
            value = urlunsplit(("", "", LANGUAGE_PREFIXES[url.hostname] + (url.path or "/"),
                                url.query, url.fragment))
        elif english and value.startswith("/") and not value.startswith("//"):
            value = "/en" + value
        return match[1] + match[2] + value + match[4]
    return LINK.sub(replace, html)


class PreviewHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = unquote(urlsplit(path).path)
        english = path == "/en" or path.startswith("/en/")
        if english:
            path = path[3:]
        root = (ROOT / ("en" if english else "cs")).resolve()
        target = (root / path.lstrip("/")).resolve()
        return str(target if target.is_relative_to(root) else root / "__invalid_path__")

    def send_head(self):
        url = urlsplit(self.path)
        target = Path(self.translate_path(self.path))
        if target.is_dir():
            if not url.path.endswith("/"):
                self.send_response(301)
                self.send_header("Location", urlunsplit(("", "", url.path + "/", url.query, "")))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            target /= "index.html"
        if target.is_file() and target.suffix == ".html":
            html = localize_links(target.read_text(encoding="utf-8"), url.path.startswith("/en/"))
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return io.BytesIO(body)
        if target.is_dir() or not target.is_file():
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):
        # A preview should show edits immediately, including CSS changes.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(PreviewHandler, directory=str(ROOT)))
    print(f"Czech:   http://127.0.0.1:{server.server_port}/", flush=True)
    print(f"English: http://127.0.0.1:{server.server_port}/en/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
