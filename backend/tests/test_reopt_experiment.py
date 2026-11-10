import _paths
import contextlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import asdict

from reopt_experiment import ILLUSTRATIVE, POLICIES, ExperimentConfig, main, run_experiment


def small(**kw):
    return ExperimentConfig(**{**asdict(ILLUSTRATIVE), "trials": 20, **kw})


class TestExperiment(unittest.TestCase):
    def test_xac_dinh_theo_seed(self):
        a = run_experiment(small())
        b = run_experiment(small())
        self.assertEqual(a["summary"], b["summary"])
        c = run_experiment(small(seed=1))
        self.assertNotEqual(a["summary"], c["summary"])

    def test_static_khong_tinh_lai_va_gated_khong_nhieu_hon_always(self):
        r = run_experiment(small(deadline_slack_low=1.6, deadline_slack_high=2.4))
        s = r["summary"]
        self.assertEqual(s["static"]["replans"], 0)
        self.assertLessEqual(s["gated"]["replans"], s["always"]["replans"])

    def test_moi_chinh_sach_giao_du_don(self):
        r = run_experiment(small(trials=5))
        self.assertEqual(set(r["summary"]), set(POLICIES))
        self.assertEqual(sum(r["gated_vs_static"].values()), 5)

    def test_nhan_du_lieu_tong_hop_va_tham_so_chua_duyet(self):
        r = run_experiment(small(trials=2))
        self.assertIn("TỔNG HỢP", r["data"])
        self.assertIn("CHƯA ĐƯỢC DUYỆT", r["parameters"])

    def test_cli_ghi_json(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["--trials", "3", "--out", out])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["config"]["trials"], 3)
            self.assertIn("static", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
