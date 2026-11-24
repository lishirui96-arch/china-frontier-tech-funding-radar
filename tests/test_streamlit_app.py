from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_all_internal_pages_render(monkeypatch, tmp_path):
    monkeypatch.setenv("FUNDING_RADAR_DB_PATH", str(tmp_path / "ui.db"))
    entry = Path(__file__).resolve().parents[1] / "app" / "Home.py"
    at = AppTest.from_file(str(entry), default_timeout=10).run()
    assert not at.exception
    assert at.title[0].value == "融资事件账本 V1"
    for page in [
        "app_pages/01_candidate_documents.py",
        "app_pages/02_entity_review.py",
        "app_pages/03_dedup_review.py",
        "app_pages/04_event_review.py",
        "app_pages/05_release_review.py",
    ]:
        at.switch_page(page).run()
        assert not at.exception
