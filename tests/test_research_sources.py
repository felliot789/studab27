import subprocess
import unittest
from unittest.mock import patch

from schola.research_sources import MAX_SOURCE_LINKS, read_source_excerpt, source_link
from schola.watcher import fetch, normalize, normalize_source


class ResearchSourceChecks(unittest.TestCase):
    def test_labeled_links_are_relative_bounded_and_not_fetched(self):
        html = ("<p>Public scholarship requirements and instructions. " * 4 + "</p>"
                '<a href="../eligibility#rules">Read <strong>eligibility</strong></a>'
                '<a href="../eligibility#again">Duplicate</a>'
                '<a href="call.pdf">2027 call</a><a href="call.pdf" download>Download</a>'
                '<a href="mailto:office@example.edu">Email</a><a href="javascript:alert(1)">Script</a>'
                '<a href="#top">Top</a><a href="package.zip">Archive</a>'
                '<form><a href="/account">Account</a></form>'
                '<svg><a href="/drawing">Drawing</a></svg>'
                '<a href="/hidden" hidden>Hidden</a>'
                + ''.join(f'<a href="/page/{i}">Page {i}</a>' for i in range(80))).encode()
        with patch("schola.watcher.socket.getaddrinfo", side_effect=AssertionError("No DNS during parsing")):
            result = normalize_source(html, "text/html", "https://example.edu/2027/apply")
        self.assertEqual(result["links"][:2], [
            {"url": "https://example.edu/eligibility", "text": "Read eligibility"},
            {"url": "https://example.edu/2027/call.pdf", "text": "2027 call"},
        ])
        self.assertEqual(len(result["links"]), MAX_SOURCE_LINKS)
        self.assertEqual(result["pdfLinks"], ["https://example.edu/2027/call.pdf"])
        self.assertFalse(any(link["url"].endswith(("account", "drawing", "hidden", ".zip")) for link in result["links"]))
        self.assertEqual(normalize(html, "text/html", result["finalUrl"]), (result["text"], result["pdfLinks"]))

    def test_candidate_links_exclude_unsafe_targets_and_bound_labels(self):
        for href in ("http://127.0.0.1/", "http://[::1]/", "http://localhost/", "http://server.local/",
                     "https://user:password@example.edu/", "https://example.edu:8080/", "file:///etc/passwd", "https://example.edu/\npath"):
            self.assertIsNone(source_link(href, "label", "https://example.edu/"), href)
        self.assertEqual(len(source_link("/rules", "x" * 500, "https://example.edu/")["text"]), 240)
        self.assertEqual(len(source_link("/" + "x" * 500, "", "https://example.edu/")["text"]), 240)

    def test_late_scholarship_sources_survive_a_large_navigation_menu(self):
        html = ('<nav>' + ''.join(f'<a href="/section/{i}">Section {i}</a>' for i in range(80)) + '</nav>'
                '<p>The official scholarship requirements explain eligibility and application deadlines. ' * 3 + '</p>'
                '<a href="/awards/requirements">Scholarship eligibility</a>'
                '<a href="/documents/2027.pdf">Funding application PDF</a>').encode()
        result = normalize_source(html, "text/html", "https://example.edu/")
        selected = {link["url"] for link in result["links"]}
        self.assertIn("https://example.edu/awards/requirements", selected)
        self.assertIn("https://example.edu/documents/2027.pdf", selected)
        self.assertEqual(result["pdfLinks"], ["https://example.edu/documents/2027.pdf"])
        self.assertIn("official scholarship requirements", result["text"])

    def test_fetch_resolves_links_against_validated_final_url(self):
        body = ("<p>Public scholarship source content and eligibility. " * 5 + '</p><a href="rules">Eligibility</a>').encode()
        with patch("schola.watcher.validate_public_url") as validate, patch("schola.watcher.PinnedHTTP") as pinned, patch("schola.watcher.time.sleep"):
            from urllib.parse import urlsplit
            validate.side_effect = lambda url: (urlsplit(url), "93.184.215.14")
            first, final = unittest.mock.MagicMock(), unittest.mock.MagicMock()
            first.status, final.status = 302, 200
            first.getheader.return_value = "/2027/"
            final.getheader.side_effect = lambda key, default=None: {"Content-Length": str(len(body)), "Content-Type": "text/html"}.get(key, default)
            final.read1.side_effect = [body, b""]
            pinned.return_value.getresponse.side_effect = [first, final]
            result = fetch("https://example.edu/old")
        self.assertEqual(result["links"], [{"url": "https://example.edu/2027/rules", "text": "Eligibility"}])
        self.assertEqual(pinned.call_count, 2)

    def test_pdf_text_and_excerpt_pagination_preserve_later_evidence(self):
        text = "Opening information. " * 1000 + "Eligibility deadline is 31 January 2027. " + "More details. " * 100
        with patch("schola.watcher.shutil.which", return_value="/usr/bin/pdftotext"), patch("schola.watcher.subprocess.run", return_value=subprocess.CompletedProcess([], 0, text.encode())):
            result = normalize_source(b"%PDF-fixture", "application/pdf", "https://example.edu/call.pdf")
        self.assertEqual(result["links"], [])
        self.assertEqual(result["pdfLinks"], [])
        first = read_source_excerpt(result["text"], limit=1000)
        later = read_source_excerpt(result["text"], offset=first["nextOffset"], limit=1000)
        self.assertEqual(first["text"] + later["text"], result["text"][:2000])
        focused = read_source_excerpt(result["text"], query="eligibility deadline", limit=1000)
        self.assertIn("31 January 2027", focused["text"])
        self.assertTrue(focused["matchedQuery"])
        self.assertGreater(focused["offset"], 16000)
        self.assertEqual(focused["totalChars"], len(result["text"]))
        self.assertLessEqual(len(read_source_excerpt(text, limit=999999)["text"]), 16000)
        self.assertIsNone(read_source_excerpt(text, offset=len(text))["nextOffset"])
        self.assertFalse(read_source_excerpt(text, query="missing phrase")["matchedQuery"])


if __name__ == "__main__":
    unittest.main()
