import numpy as np
import pandas as pd

from feature_engine.src.event_parser import load_run
from feature_engine.src.stream import CsvTail, StreamFeatureBuilder
from feature_engine.src.windowing import build_features, load_config
from .conftest import S, T0, win


def test_csv_tail_handles_partial_lines(tmp_path):
    p = tmp_path / "x.csv"; t = CsvTail(p)
    assert t.read().empty
    p.write_text("a,b,comm\n1,2,x\n3,4,y")
    d = t.read(); assert list(d.a) == [1]                    # partial last line withheld
    with open(p, "a") as f: f.write("\n5,6,z\n")
    d = t.read(); assert list(d.a) == [3, 5]


def test_stream_matches_batch(make_run):
    n = 12
    rows = [(*win(k), 1, "w", nr, c + 3 * ((k * 7 + nr) % 5)) for k in range(n) for nr, c in ((0, 40), (1, 10), (9, 25))]
    rows += [(*win(k), 2, "v", 0, 5 + k) for k in range(n)]
    res = [(*win(k), 1, "w", 200_000_000 + 10_000_000 * k, 3, 1, k) for k in range(n)]
    d = make_run(rows, res, n_windows=n)
    cfg = load_config()
    batch = build_features(load_run(d), cfg)
    run = load_run(d)
    b = StreamFeatureBuilder(run.meta, cfg)
    outs = []
    for k in range(n):                                       # feed one collector window at a time
        b.add(run.sys[run.sys.window_end_ns == win(k)[1]], run.res[run.res.window_end_ns == win(k)[1]], None, watermark_ns=win(k)[1])
        outs.append(b.poll())
    b.add(watermark_ns=T0 + (n + 2) * S)
    outs.append(b.poll())
    live = pd.concat([o for o in outs if len(o)], ignore_index=True)
    key = ["pid", "widx"]
    m = batch.merge(live, on=key, suffixes=("_b", "_l"))
    assert len(m) == len(batch) == len(live)
    for c in ["sys_total", "sys_entropy", "cpu_util", "frac_file", "sys_total_rmean", "sys_total_rstd", "sys_total_delta"]:
        assert np.allclose(m[c + "_b"], m[c + "_l"], atol=1e-9), c
