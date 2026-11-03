import gzip

import pytest
import requests
import responses

from webscope.crawler import (
    CrawlOptions,
    count_pages,
    extract_links,
    normalize_link,
    parse_sitemap,
)
from webscope.fetcher import FetchedPage

BASE = "https://shop.example"
HTML = {"Content-Type": "text/html; charset=utf-8"}


def urlset(*paths: str) -> str:
    locs = "".join(f"<url><loc>{BASE}{path}</loc></url>" for path in paths)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'


def sitemap_index(*urls: str) -> str:
    items = "".join(f"<sitemap><loc>{url}</loc></sitemap>" for url in urls)
    return f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</sitemapindex>'


def home(html: str = "<html><body></body></html>") -> FetchedPage:
    return FetchedPage(url=f"{BASE}/", final_url=f"{BASE}/", status_code=200, html=html)


def run(options: CrawlOptions | None = None, page: FetchedPage | None = None, events=None):
    sleeps: list[float] = []

    def on_event(code: str, **params: object) -> None:
        if events is not None:
            events.append(code)

    result = count_pages(
        page or home(),
        requests.Session(),
        options or CrawlOptions(),
        sleep=sleeps.append,
        on_event=on_event,
    )
    return result, sleeps


def test_sitemap_declared_in_robots(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", body=f"User-agent: *\nSitemap: {BASE}/custom-map.xml\n")
    mocked.get(f"{BASE}/custom-map.xml", body=urlset("/", "/a", "/b", "/b/", "/c#top"))
    result, sleeps = run()
    assert (result.count, result.source, result.at_least) == (4, "sitemap", False)
    assert sleeps == []


def test_falls_back_to_default_sitemap_location(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", status=404)
    mocked.get(f"{BASE}/sitemap.xml", body=urlset("/", "/about"))
    result, _ = run()
    assert (result.count, result.source) == (2, "sitemap")


def test_sitemap_index_is_followed(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", status=404)
    mocked.get(
        f"{BASE}/sitemap.xml",
        body=sitemap_index(f"{BASE}/posts.xml", f"{BASE}/pages.xml.gz"),
    )
    mocked.get(f"{BASE}/posts.xml", body=urlset("/blog/1", "/blog/2", "/blog/3"))
    mocked.get(f"{BASE}/pages.xml.gz", body=gzip.compress(urlset("/", "/about").encode()))
    result, _ = run()
    assert (result.count, result.source, result.at_least) == (5, "sitemap", False)


def test_sitemap_index_depth_limit_reports_at_least(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", status=404)
    mocked.get(f"{BASE}/sitemap.xml", body=sitemap_index(f"{BASE}/level1.xml", f"{BASE}/flat.xml"))
    mocked.get(f"{BASE}/level1.xml", body=sitemap_index(f"{BASE}/level2.xml"))
    mocked.get(f"{BASE}/level2.xml", body=sitemap_index(f"{BASE}/level3.xml"))
    mocked.get(f"{BASE}/flat.xml", body=urlset("/x", "/y"))
    result, _ = run(CrawlOptions(max_sitemap_depth=2))
    assert (result.count, result.at_least) == (2, True)


def test_sitemap_read_limit_reports_at_least(mocked: responses.RequestsMock) -> None:
    children = [f"{BASE}/s{i}.xml" for i in range(5)]
    mocked.get(f"{BASE}/robots.txt", status=404)
    mocked.get(f"{BASE}/sitemap.xml", body=sitemap_index(*children))
    for i, child in enumerate(children):
        mocked.get(child, body=urlset(f"/page-{i}"))
    result, _ = run(CrawlOptions(max_sitemaps=3))
    assert (result.count, result.at_least) == (2, True)


def test_sitemap_urls_from_other_domains_are_ignored(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", status=404)
    body = urlset("/a") + "<url><loc>https://other.example/b</loc></url>"
    mocked.get(f"{BASE}/sitemap.xml", body=body)
    result, _ = run()
    assert result.count == 1


def site_page(*links: str) -> str:
    anchors = "".join(f'<a href="{link}">x</a>' for link in links)
    return f"<html><body>{anchors}</body></html>"


def test_crawl_without_sitemap(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", body="User-agent: *\nDisallow: /private\n")
    mocked.get(f"{BASE}/sitemap.xml", status=404)
    mocked.get(f"{BASE}/a", body=site_page("/b", "/a/", "/#top"), headers=HTML)
    mocked.get(f"{BASE}/b", body=site_page("/c", "https://external.example/"), headers=HTML)
    mocked.get(f"{BASE}/c", body="not found", status=404)
    start = home(site_page("/a", "/a#section", "/private/x", "mailto:hi@shop.example", "/file.pdf"))
    events: list[str] = []
    result, sleeps = run(CrawlOptions(delay=0.3), start, events)
    assert (result.count, result.source, result.at_least) == (3, "crawl", False)
    assert sleeps == [0.3, 0.3, 0.3]
    assert "crawl_blocked" in events
    assert "crawl_error" in events
    assert not [c for c in mocked.calls if "/private" in c.request.url]


def test_crawl_stops_at_max_pages(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", status=404)
    mocked.get(f"{BASE}/sitemap.xml", status=404)
    for i in range(1, 10):
        mocked.get(f"{BASE}/p{i}", body=site_page(f"/p{i + 1}"), headers=HTML)
    result, _ = run(CrawlOptions(max_pages=4), home(site_page("/p1")))
    assert (result.count, result.source, result.at_least) == (4, "crawl", True)


def test_crawl_single_page_site(mocked: responses.RequestsMock) -> None:
    mocked.get(f"{BASE}/robots.txt", status=404)
    mocked.get(f"{BASE}/sitemap.xml", status=404)
    result, _ = run()
    assert (result.count, result.at_least) == (1, False)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://Shop.Example/a/", "https://shop.example/a"),
        ("https://shop.example/a#frag", "https://shop.example/a"),
        ("https://shop.example", "https://shop.example/"),
        ("https://shop.example/?q=1", "https://shop.example/?q=1"),
        ("https://shop.example/doc.PDF", None),
        ("mailto:hi@shop.example", None),
        ("javascript:void(0)", None),
    ],
)
def test_normalize_link(url: str, expected: str | None) -> None:
    assert normalize_link(url) == expected


def test_extract_links_keeps_same_domain_including_www() -> None:
    html = site_page("/a", "https://www.shop.example/b", "https://evil.example/c", "/a/")
    assert extract_links(html, f"{BASE}/") == [f"{BASE}/a", "https://www.shop.example/b"]


def test_parse_sitemap_handles_cdata_and_entities() -> None:
    body = b"<urlset><url><loc><![CDATA[https://a.example/x?a=1&amp;b=2]]></loc></url></urlset>"
    assert parse_sitemap(body) == (False, ["https://a.example/x?a=1&b=2"])
