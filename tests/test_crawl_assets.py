from app.crawling.scrapling_runner import (
    _asset_candidates,
    _asset_filename,
    _asset_matches_description,
    _asset_url_allowed,
    _description_terms,
)
from scrapling.engines.toolbelt.custom import Response


def test_asset_url_filter_requires_allowed_domain_and_extension():
    allowed_domains = {"example.com"}
    extensions = ["pdf", "docx"]

    assert _asset_url_allowed(
        "https://example.com/files/guide.PDF?download=1",
        allowed_domains,
        extensions,
    )
    assert not _asset_url_allowed(
        "https://cdn.example.net/files/guide.pdf",
        allowed_domains,
        extensions,
    )
    assert not _asset_url_allowed(
        "https://example.com/files/script.exe",
        allowed_domains,
        extensions,
    )


def test_asset_filename_prefers_content_disposition_and_sanitizes_it():
    filename = _asset_filename(
        "https://example.com/download?id=1",
        {"content-disposition": 'attachment; filename="report:2026.pdf"'},
    )

    assert filename == "report_2026.pdf"


def test_no_code_asset_selectors_work_with_scrapling():
    response = Response(
        url="https://example.com/resources",
        content="""
            <html><body>
              <a href="/guide.pdf">Guide</a>
              <img src="/cover.jpg" data-src="/cover-large.webp">
            </body></html>
        """,
        status=200,
        reason="OK",
        cookies={},
        headers={"content-type": "text/html"},
        request_headers={},
    )

    file_candidates = _asset_candidates(response, "a[href]", ["href"])
    image_candidates = _asset_candidates(
        response,
        "img[src], img[data-src]",
        ["src", "data-src"],
    )

    assert [url for url, _ in file_candidates] == ["/guide.pdf"]
    assert [url for url, _ in image_candidates] == [
        "/cover.jpg",
        "/cover-large.webp",
    ]


def test_description_terms_extract_example_intent():
    assert _description_terms("只爬安徽省的试卷") == ["安徽省", "试卷"]


def test_asset_description_matches_link_text_metadata_and_url():
    response = Response(
        url="https://example.com/resources",
        content="""
            <html><body>
              <a href="/files/anhui-exam.pdf" title="2025年安徽省试卷">下载</a>
              <a href="/files/jiangsu-exam.pdf">江苏省试卷</a>
            </body></html>
        """,
        status=200,
        reason="OK",
        cookies={},
        headers={"content-type": "text/html"},
        request_headers={},
    )

    terms = _description_terms("只爬安徽省的试卷")
    candidates = _asset_candidates(response, "a[href]", ["href"])
    matched_urls = [
        url
        for url, searchable_text in candidates
        if _asset_matches_description(searchable_text, terms)
    ]

    assert matched_urls == ["/files/anhui-exam.pdf"]
