"""Optional browser QA: pip install -r requirements-browser.txt; uses installed Chrome."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        failures = []
        for width, height in [(1440, 1000), (768, 1024), (390, 844), (360, 800)]:
            page = browser.new_page(
                viewport={"width": width, "height": height}, reduced_motion="reduce"
            )
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.goto((ROOT / "docs/index.html").as_uri())
            expect(page.locator("#decision-title")).not_to_contain_text("Loading")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            for selector in [".overview", ".metric-band", ".segment-band", ".method-band"]:
                box = page.locator(selector).bounding_box()
                assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1, (width, selector)
            for metric in page.evaluate("window.EXPERIMENT_DATA.summary"):
                page.get_by_role("button", name=metric["metric_label"], exact=True).click()
                expected = f"{metric['absolute_lift'] * 100:+.1f} pp"
                expect(page.locator("#effect-value")).to_have_text(expected)
                assert page.locator(".rate-fill.control").bounding_box()["width"] > 0
                for dimension in ["Listener", "Track tenure", "Artist reach"]:
                    page.get_by_role("button", name=dimension, exact=True).click()
                    assert page.locator("#forest-plot circle").count() >= 2
                    assert page.locator("#segment-table tr").count() >= 2
            page.get_by_role("button", name="Qualified listen rate", exact=True).click()
            page.get_by_role("button", name="Listener", exact=True).click()
            page.evaluate("window.scrollTo(0, 0)")
            suffix = "desktop" if width == 1440 else f"mobile-{width}"
            page.screenshot(path=str(ROOT / f"docs/assets/dashboard-{suffix}.png"), full_page=True)
            page.goto((ROOT / "docs/memo.html").as_uri())
            expect(page.get_by_role("heading", level=1)).to_have_text(
                "Music promotion: decision memo"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                "memo overflow"
            )
            if width == 1440:
                pdf = ROOT / "target/memo-print-check.pdf"
                page.pdf(path=str(pdf), prefer_css_page_size=True)
                assert len(PdfReader(pdf).pages) == 1, "Memo exceeds one printed page"
            page.close()
        browser.close()
        assert not failures, failures
    print("PASS: 4 viewports, 15 metric/segment combinations each, visible charts, 1-page memo.")


if __name__ == "__main__":
    main()
