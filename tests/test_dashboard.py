"""Selenium tests for the MetaReproducer dashboard."""
import pytest
import json
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import (
        WebDriverException,
        NoSuchElementException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not SELENIUM_AVAILABLE, reason="selenium not installed"
)


def _make_driver():
    """Return a headless Chrome driver, or None if Chrome is not available."""
    if not SELENIUM_AVAILABLE:
        return None
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    try:
        d = webdriver.Chrome(options=opts)
        d.set_window_size(1400, 900)
        return d
    except WebDriverException:
        return None


def _inject_payload(driver, payload):
    """Load payload into the dashboard via the test hook."""
    driver.execute_script(
        """
        window.__loadDashboardData(arguments[0]);
        """,
        payload,
    )
    time.sleep(1.0)


def _scoped_sample_payload():
    """Synthetic payload with explicit primary and secondary outcomes."""
    def record(review_id, outcome_label, is_primary, tier, matched, total, coverage):
        return {
            "review_id": review_id,
            "outcome_label": outcome_label,
            "is_primary": is_primary,
            "inferred_effect_type": "RR",
            "study_level": {
                "total_studies": total,
                "n_with_pdf": total,
                "n_extracted": total,
                "matched_strict": matched,
                "matched_moderate": matched,
                "match_rate_strict": matched / total,
                "match_rate_moderate": matched / total,
            },
            "review_level": {
                "tier": tier,
                "pct_difference": 0.02,
                "same_direction": True,
                "same_significance": True,
                "reference_k": total,
                "reproduced_k": matched,
                "k_coverage": coverage,
            },
            "reference_pooled": {
                "pooled": 0.25,
                "se": 0.05,
                "tau2": 0.01,
                "i2": 20.0,
            },
            "reproduced_pooled": {
                "pooled": 0.24,
                "se": 0.05,
                "tau2": 0.01,
                "i2": 18.0,
            },
            "errors": {
                "missing_pdf": 0,
                "extraction_failure": 0,
                "no_match": total - matched,
                "success": matched,
                "primary_error_source": "success" if matched == total else "no_match",
            },
            "cert": {
                "review_id": review_id,
                "classification": tier,
            },
        }

    return [
        record("CD100001", "Mortality", True, "reproduced", 4, 4, 1.0),
        record("CD100001", "Hospital stay", False, "major_discrepancy", 2, 4, 0.5),
        record("CD100002", "Readmission", True, "minor_discrepancy", 3, 4, 0.75),
    ]


@pytest.fixture(scope="module")
def driver():
    d = _make_driver()
    if d is None:
        pytest.skip("ChromeDriver not available")
    yield d
    d.quit()


@pytest.fixture(scope="module")
def loaded_dashboard(driver):
    """Open the dashboard and inject sample data, then call renderAll()."""
    html_path = Path(__file__).parent.parent / "dashboard" / "index.html"
    assert html_path.exists(), f"Dashboard not found at {html_path}"
    driver.get(f"file:///{html_path.resolve()}")

    # Load sample data
    sample_path = (
        Path(__file__).parent.parent / "data" / "results" / "sample_summary.json"
    )
    assert sample_path.exists(), f"Sample data not found at {sample_path}"
    with open(sample_path) as f:
        sample = json.load(f)

    _inject_payload(driver, sample)
    return driver


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_overview_panel_exists(loaded_dashboard):
    """overviewPanel section is present in the DOM."""
    el = loaded_dashboard.find_element(By.ID, "overviewPanel")
    assert el is not None


def test_overview_renders(loaded_dashboard):
    """Overview content div becomes visible after data load."""
    content = loaded_dashboard.find_element(By.ID, "overviewContent")
    assert content.is_displayed(), "overviewContent should be visible after data load"


def test_overview_contains_percentage(loaded_dashboard):
    """Overview panel text contains at least one percentage value."""
    panel = loaded_dashboard.find_element(By.ID, "overviewPanel")
    text = panel.text
    assert "%" in text, f"Expected '%' in overview panel text, got: {text[:200]}"


def test_overview_stats_grid_populated(loaded_dashboard):
    """Stats grid has at least 4 stat cards."""
    cards = loaded_dashboard.find_elements(
        By.CSS_SELECTOR, "#overviewStats .stat-card"
    )
    assert len(cards) >= 4, f"Expected >= 4 stat cards, got {len(cards)}"


def test_theme_toggle(loaded_dashboard):
    """Dark mode toggle changes the data-theme attribute on <html>."""
    btn = loaded_dashboard.find_element(By.ID, "themeToggle")
    initial = loaded_dashboard.execute_script(
        "return document.documentElement.getAttribute('data-theme')"
    )
    btn.click()
    time.sleep(0.3)
    after = loaded_dashboard.execute_script(
        "return document.documentElement.getAttribute('data-theme')"
    )
    assert initial != after, (
        f"Theme did not change after toggle: before={initial!r}, after={after!r}"
    )
    assert after in ("dark", "light"), f"Unexpected theme value: {after!r}"
    # Restore original theme
    btn.click()
    time.sleep(0.2)


def test_tab_navigation_to_explorer(loaded_dashboard):
    """Clicking the Review Explorer tab activates the explorer panel."""
    tab = loaded_dashboard.find_element(By.ID, "tab-explorer")
    tab.click()
    time.sleep(0.4)
    panel = loaded_dashboard.find_element(By.ID, "explorerPanel")
    assert "active" in panel.get_attribute("class"), (
        "explorerPanel should have class 'active' after tab click"
    )


def test_explorer_table_has_rows(loaded_dashboard):
    """Explorer table tbody contains rows matching the sample data."""
    # Ensure explorer tab is active (may already be from previous test)
    tab = loaded_dashboard.find_element(By.ID, "tab-explorer")
    tab.click()
    time.sleep(0.4)
    rows = loaded_dashboard.find_elements(
        By.CSS_SELECTOR, "#explorerBody tr"
    )
    assert len(rows) >= 1, f"Expected rows in explorer table, got {len(rows)}"


def test_explorer_table_row_count_matches_sample(loaded_dashboard):
    """Explorer table has the same number of rows as the sample data (8)."""
    tab = loaded_dashboard.find_element(By.ID, "tab-explorer")
    tab.click()
    time.sleep(0.4)
    rows = loaded_dashboard.find_elements(
        By.CSS_SELECTOR, "#explorerBody tr"
    )
    # Sample data has 8 reviews
    assert len(rows) == 8, f"Expected 8 rows, got {len(rows)}"


def test_explorer_search_filters_rows(loaded_dashboard):
    """Typing in the search box filters the explorer table rows."""
    tab = loaded_dashboard.find_element(By.ID, "tab-explorer")
    tab.click()
    time.sleep(0.3)
    search = loaded_dashboard.find_element(By.ID, "explorerSearch")
    search.clear()
    search.send_keys("CD001234")
    time.sleep(0.4)
    rows = loaded_dashboard.find_elements(
        By.CSS_SELECTOR, "#explorerBody tr"
    )
    assert len(rows) == 1, f"Expected 1 filtered row for 'CD001234', got {len(rows)}"
    # Clear search
    search.clear()
    time.sleep(0.3)


def test_csv_export_button_enabled(loaded_dashboard):
    """CSV export button is enabled after data load."""
    btn = loaded_dashboard.find_element(By.ID, "csvExport")
    assert not btn.get_attribute("disabled"), "csvExport button should be enabled"


def test_scope_summary_reports_primary_fallback_for_legacy_data(loaded_dashboard):
    """Legacy summaries without is_primary markers should explain the fallback."""
    summary = loaded_dashboard.find_element(By.ID, "scopeSummary")
    assert "No explicit primary markers found." in summary.text


def test_taxonomy_tab_renders(loaded_dashboard):
    """Clicking the Error Taxonomy tab shows taxonomy content."""
    tab = loaded_dashboard.find_element(By.ID, "tab-taxonomy")
    tab.click()
    time.sleep(0.6)  # Allow Plotly chart to render
    panel = loaded_dashboard.find_element(By.ID, "taxonomyPanel")
    assert "active" in panel.get_attribute("class"), (
        "taxonomyPanel should be active after tab click"
    )
    content = loaded_dashboard.find_element(By.ID, "taxonomyContent")
    assert content.is_displayed(), "taxonomyContent should be visible"


def test_fragility_tab_renders(loaded_dashboard):
    """Clicking the Fragility Landscape tab shows fragility content."""
    tab = loaded_dashboard.find_element(By.ID, "tab-fragility")
    tab.click()
    time.sleep(0.6)
    panel = loaded_dashboard.find_element(By.ID, "fragilityPanel")
    assert "active" in panel.get_attribute("class")
    content = loaded_dashboard.find_element(By.ID, "fragilityContent")
    assert content.is_displayed()


def test_coverage_tab_renders(loaded_dashboard):
    """Clicking the OA Coverage tab shows coverage content."""
    tab = loaded_dashboard.find_element(By.ID, "tab-coverage")
    tab.click()
    time.sleep(0.6)
    panel = loaded_dashboard.find_element(By.ID, "coveragePanel")
    assert "active" in panel.get_attribute("class")
    content = loaded_dashboard.find_element(By.ID, "coverageContent")
    assert content.is_displayed()


def test_no_inject_error(loaded_dashboard):
    """Data injection via JS did not raise an error."""
    err = loaded_dashboard.execute_script("return window.__injectError || null")
    assert err is None, f"Dashboard data injection raised: {err}"


def test_tab_keyboard_navigation(loaded_dashboard):
    """Tab buttons have correct aria-selected state after click."""
    # Navigate back to overview
    tab_overview = loaded_dashboard.find_element(By.ID, "tab-overview")
    tab_overview.click()
    time.sleep(0.3)
    assert tab_overview.get_attribute("aria-selected") == "true", (
        "tab-overview should have aria-selected=true"
    )
    tab_explorer = loaded_dashboard.find_element(By.ID, "tab-explorer")
    assert tab_explorer.get_attribute("aria-selected") == "false", (
        "tab-explorer should have aria-selected=false when overview is active"
    )


def test_scope_toggle_filters_explicit_primary_rows(loaded_dashboard):
    """Primary-only scope should hide secondary outcomes until All outcomes is selected."""
    _inject_payload(loaded_dashboard, _scoped_sample_payload())

    scope_primary = loaded_dashboard.find_element(By.ID, "scopePrimary")
    scope_all = loaded_dashboard.find_element(By.ID, "scopeAll")
    summary = loaded_dashboard.find_element(By.ID, "scopeSummary")

    assert scope_primary.get_attribute("aria-pressed") == "true"
    assert "Showing 2 primary outcomes from 2 reviews." in summary.text

    tab = loaded_dashboard.find_element(By.ID, "tab-explorer")
    tab.click()
    time.sleep(0.4)
    rows = loaded_dashboard.find_elements(By.CSS_SELECTOR, "#explorerBody tr")
    assert len(rows) == 2, f"Expected 2 primary rows, got {len(rows)}"

    scope_all.click()
    time.sleep(0.5)

    assert scope_all.get_attribute("aria-pressed") == "true"
    assert "Showing 3 outcomes from 2 reviews." in summary.text
    rows = loaded_dashboard.find_elements(By.CSS_SELECTOR, "#explorerBody tr")
    assert len(rows) == 3, f"Expected 3 rows after switching to all outcomes, got {len(rows)}"
