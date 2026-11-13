import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import build_site  # noqa: E402


def test_site_builds_offline_from_snapshots(tmp_path):
    built = build_site.build(tmp_path, offline=True, tickers=["SPY", "NVDA"])
    assert built == ["SPY", "NVDA"]
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "spy.html" in index and "nvda.html" in index
    spy = (tmp_path / "spy.html").read_text(encoding="utf-8")
    assert "cdn.plot.ly" in spy and "All tickers" in spy
    assert len(spy) < 1_000_000          # Plotly comes from the CDN, not embedded
