from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_all_internal_pages_render(monkeypatch, tmp_path):
    monkeypatch.setenv("FUNDING_RADAR_DB_PATH", str(tmp_path / "ui.db"))
    entry = Path(__file__).resolve().parents[1] / "app" / "Home.py"
    at = AppTest.from_file(str(entry), default_timeout=10).run()
    assert not at.exception
    assert at.title[0].value == "融资事件账本 V1"
    for page in [
        "app_pages/00_url_import.py",
        "app_pages/00_source_management.py",
        "app_pages/01_candidate_documents.py",
        "app_pages/02_entity_review.py",
        "app_pages/03_dedup_review.py",
        "app_pages/04_event_review.py",
        "app_pages/05_release_review.py",
        "app_pages/06_november_samples.py",
        "app_pages/07_technology_keywords.py",
        "app_pages/08_candidate_themes.py",
        "app_pages/09_theme_review.py",
        "app_pages/10_source_coverage.py",
        "app_pages/11_multiplatform_audit.py",
        "app_pages/12_quality_audit.py",
        "app_pages/13_event_review_queue.py",
        "app_pages/14_formal_funding_review.py",
        "app_pages/15_acquisition_review.py",
        "app_pages/16_confirmed_statistics.py",
        "app_pages/17_project_progress.py",
        "app_pages/18_v2_theme_workbench.py",
        "app_pages/19_v2_database_preview.py",
    ]:
        at.switch_page(page).run()
        assert not at.exception
