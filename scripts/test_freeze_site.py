"""Regression checks for preserving galleries while retiring data collection."""
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from freeze_site import Exporter, verify


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exporter = Exporter(self.root / "output", self.root / "cache", offline=True)

    def page(self, content):
        html, links = self.exporter.prepare_page(
            '<html lang="en"><head><title>Calendar</title></head><body>'
            '<nav><a href="https://calendar.draci.info">EN</a></nav>' + content + '</body></html>',
            "https://kalendar.draci.info/2023/", "cs")
        return BeautifulSoup(html, "html.parser"), links

    def test_removes_all_collection_and_order_calls_to_action(self):
        soup, _ = self.page('''
            <div class="newsletter"><form action="/newsletter/">
            <input name="email"></form></div><section id="buy">Order now</section>
            <div id="about"><p><a href="https://forms.gle/example">Order calendar</a></p></div>
            <script src="/static/shop.js"></script><script>track()</script>
            <img src="/media/dragon.jpg" onerror="track()">
            <a href="/checkout/">Checkout</a>
            <li class="dropdown"><a href="/?currency=EUR">EUR</a></li>
        ''')
        self.assertFalse(soup.select("form, input, .newsletter, #buy, .dropdown"))
        self.assertEqual([tag["src"] for tag in soup.select("script")], ["/assets/archive.js"])
        self.assertFalse(soup.select("[onerror]"))
        self.assertNotIn("forms.gle", str(soup))
        self.assertFalse(soup.select('a[href="/checkout/"]'))
        self.assertTrue(soup.select_one(".archive-notice"))

    def test_preserves_language_switch_and_discovers_only_archive_pages(self):
        soup, links = self.page('<a href="/2012/">2012</a><a href="/admin/">Admin</a>')
        self.assertEqual(soup.select_one("nav a")["href"], "https://calendar.draci.info/")
        self.assertEqual(links, {"/2012/"})
        self.assertEqual(soup.html["lang"], "cs")

    def test_gallery_retains_full_image_and_thumbnail_as_local_assets(self):
        soup, _ = self.page('''<a class="fancybox" rel="previews" href="/media/large.jpg">
            <img src="/resize/200/100/media/small.jpg"></a>
            <div id="about"><a href="https://kalendar.draci.info/2021/#preview">Preview</a></div>
            <section id="preview"></section>''')
        self.assertTrue(soup.select_one("a.fancybox")["href"].startswith("/assets/"))
        self.assertTrue(soup.img["src"].startswith("/assets/"))
        self.assertEqual(soup.select_one("#about a")["href"], "#preview")

    def test_css_keeps_font_fallback_and_rewrites_nested_dependencies(self):
        css = self.exporter.css("""@font-face { src:
            url('/static/font-awesome/fonts/fontawesome-webfont.woff2?v=4') format('woff2'),
            url('../fonts/font.woff?#iefix') format('woff'); }
            a { background: url('data:image/png;base64,abc'); }
            b { background: url('../img/dragon.png'); }""", "https://kalendar.draci.info/static/css/a.css")
        self.assertNotIn("woff2", css)
        self.assertIn("#iefix", css)
        self.assertIn("data:image/png;base64,abc", css)
        self.assertEqual(len(self.exporter.assets), 2)

    def test_verification_rejects_missing_files_and_unexpected_scripts(self):
        for language in ("cs", "en"):
            root = self.root / "output" / language
            root.mkdir(parents=True)
            (root / "index.html").write_text('<img src="/assets/missing.png"><script>track()</script>')
        with self.assertRaisesRegex(RuntimeError, "Unexpected script"):
            verify(self.root / "output")


if __name__ == "__main__":
    unittest.main()
