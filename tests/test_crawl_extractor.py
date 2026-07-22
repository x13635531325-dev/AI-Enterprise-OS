from scrapling.engines.toolbelt.custom import Response

from app.crawling.extractor import extract_page
from app.schemas.crawls import CreateCrawlRequest


def test_extract_page_uses_scrapling_selectors_for_multiple_records(tmp_path):
    response = Response(
        url="https://example.com/products",
        content="""
            <html><head><title>Catalog</title></head><body>
              <article><h2>One</h2><span class="price">10</span></article>
              <article><h2>Two</h2><span class="price">20</span></article>
            </body></html>
        """,
        status=200,
        reason="OK",
        cookies={},
        headers={"content-type": "text/html"},
        request_headers={},
        adaptive=True,
        storage_args={"storage_file": str(tmp_path / "adaptive.sqlite3")},
    )
    request = CreateCrawlRequest(
        name="catalog",
        start_urls=["https://example.com/products"],
        item_selector="article",
        fields=[
            {"name": "name", "selector": "h2::text"},
            {"name": "price", "selector": ".price::text"},
        ],
        destinations={
            "oss": {"enabled": False},
            "mysql": {"enabled": True},
        },
    )

    page = extract_page(response, request)

    assert page.title == "Catalog"
    assert page.records == [
        {"name": "One", "price": "10"},
        {"name": "Two", "price": "20"},
    ]
