"""Needs root + built collector; skipped otherwise. Runs the real eBPF pipeline for 3 s."""
import os, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
COLL = ROOT / "build" / "ebpf-collector"
pytestmark = pytest.mark.skipif(os.geteuid() != 0 or not COLL.exists(), reason="needs root and build/ebpf-collector")


def test_collector_and_features(tmp_path):
    out = tmp_path / "run"
    p = subprocess.Popen([str(COLL), "-o", str(out), "-w", "500", "-d", "3"], stderr=subprocess.PIPE)
    import time; time.sleep(1)
    subprocess.run([sys.executable, "-c", "import os\nfor _ in range(20000): os.getppid()"], check=True)
    subprocess.run(["/bin/true"], check=True)
    assert p.wait(timeout=20) == 0, p.stderr.read().decode()
    from feature_engine.src.event_parser import load_run
    from feature_engine.src.windowing import build_features, load_config
    cfg = load_config(); cfg["window_ms"] = 500
    f = build_features(load_run(out), cfg)
    assert len(f) > 0 and f["sys_total"].max() >= 20000
    assert (out / "bpf_prog_stats.csv").exists()
