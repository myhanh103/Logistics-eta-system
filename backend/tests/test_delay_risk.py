import _paths
import math
import unittest

from delay_risk_detector import (ALERT_CRITICAL, ALERT_INFO, ALERT_NONE, ALERT_WARNING,
                                 AlertConfig, DelayRiskInputError, OrderProgress, ReoptConfig,
                                 STATUS_AT_RISK, STATUS_DELIVERED, STATUS_ETA_UNKNOWN,
                                 STATUS_LATE, STATUS_NO_DEADLINE, STATUS_ON_TIME, assess,
                                 classify, count_by_status, decide_reoptimization, worst_alert)

CFG = AlertConfig(at_risk_buffer_s=60)
RCFG = ReoptConfig(trigger_on_at_risk=False, off_route_m=200, min_interval_s=120, lock_next=False)


def st(deadline, eta, **kw):
    return classify(OrderProgress("X", deadline, eta, **kw), CFG)


class TestClassify(unittest.TestCase):
    def test_on_time_at_risk_late(self):
        self.assertEqual(st(1000, 800).status, STATUS_ON_TIME)
        self.assertEqual(st(1000, 950).status, STATUS_AT_RISK)
        self.assertEqual(st(1000, 1001).status, STATUS_LATE)

    def test_canh_bien(self):
        self.assertEqual(st(1000, 1000).status, STATUS_AT_RISK)
        self.assertEqual(st(1000, 940).status, STATUS_ON_TIME)
        zero = classify(OrderProgress("X", 1000, 1000), AlertConfig(0))
        self.assertEqual(zero.status, STATUS_ON_TIME)

    def test_muc_canh_bao(self):
        self.assertEqual(st(1000, 800).alert, ALERT_NONE)
        self.assertEqual(st(1000, 950).alert, ALERT_WARNING)
        self.assertEqual(st(1000, 1100).alert, ALERT_CRITICAL)
        self.assertAlmostEqual(st(1000, 1100).lateness_s, 100)

    def test_khong_co_deadline(self):
        a = st(None, 500)
        self.assertEqual((a.status, a.alert, a.lateness_s), (STATUS_NO_DEADLINE, ALERT_INFO, 0.0))
        self.assertEqual(st(None, None).status, STATUS_NO_DEADLINE)

    def test_deadline_khong_hop_le(self):
        for bad in (-1, math.nan, math.inf, "x", True):
            with self.assertRaises(DelayRiskInputError, msg=str(bad)):
                st(bad, 100)

    def test_eta_thieu_hoac_hong(self):
        for bad in (None, math.nan, -5, math.inf, "abc", True):
            self.assertEqual(st(1000, bad).status, STATUS_ETA_UNKNOWN, msg=str(bad))
        self.assertEqual(st(1000, None).alert, ALERT_WARNING)

    def test_da_giao_xong(self):
        a = st(1000, None, delivered=True, delivered_s=900)
        self.assertEqual((a.status, a.alert, a.lateness_s), (STATUS_DELIVERED, ALERT_NONE, 0.0))
        late = st(1000, 5000, delivered=True, delivered_s=1200)
        self.assertEqual(late.status, STATUS_DELIVERED)
        self.assertAlmostEqual(late.lateness_s, 200)
        self.assertEqual(st(None, None, delivered=True).status, STATUS_DELIVERED)

    def test_da_giao_khong_nhan_eta_cu(self):
        self.assertEqual(st(100, 9999, delivered=True, delivered_s=50).alert, ALERT_NONE)

    def test_cau_hinh_khong_hop_le(self):
        for bad in (-1, math.nan, None, True):
            with self.assertRaises(DelayRiskInputError):
                AlertConfig(bad)


class TestAssess(unittest.TestCase):
    def test_deadline_bang_nhau_xep_on_dinh_theo_do_khan_va_id(self):
        orders = [OrderProgress("C", 1000, 900), OrderProgress("A", 1000, 900),
                  OrderProgress("B", 1000, 1300)]
        out = assess(orders, CFG)
        self.assertEqual([a.order_id for a in out], ["B", "A", "C"])
        again = assess(list(reversed(orders)), CFG)
        self.assertEqual([a.order_id for a in again], ["B", "A", "C"])

    def test_deadline_bang_nhau_cung_trang_thai_theo_slack(self):
        out = assess([OrderProgress("A", 1000, 990), OrderProgress("B", 1000, 960)], CFG)
        self.assertEqual([a.order_id for a in out], ["A", "B"])
        self.assertTrue(all(a.status == STATUS_AT_RISK for a in out))

    def test_deadline_bang_nhau_chi_dua_tre_phan_biet(self):
        out = assess([OrderProgress("A", 1000, 1100), OrderProgress("B", 1000, 1500)], CFG)
        self.assertEqual([a.order_id for a in out], ["B", "A"])

    def test_order_id_trung_lap(self):
        with self.assertRaises(DelayRiskInputError):
            assess([OrderProgress("A", 1, 1), OrderProgress("A", 2, 2)], CFG)

    def test_tong_hop(self):
        out = assess([OrderProgress("A", 1000, 1100), OrderProgress("B", None, 5),
                      OrderProgress("C", 1000, 100), OrderProgress("D", 1, None, True, 1)], CFG)
        self.assertEqual(count_by_status(out), {STATUS_LATE: 1, STATUS_NO_DEADLINE: 1,
                                                STATUS_ON_TIME: 1, STATUS_DELIVERED: 1})
        self.assertEqual(worst_alert(out), ALERT_CRITICAL)
        self.assertEqual(worst_alert([]), ALERT_NONE)

    def test_eta_thay_doi_doi_trang_thai(self):
        before = classify(OrderProgress("A", 1000, 800), CFG)
        after = classify(OrderProgress("A", 1000, 1200), CFG)
        self.assertEqual((before.status, after.status), (STATUS_ON_TIME, STATUS_LATE))


class TestReoptDecision(unittest.TestCase):
    def a(self, *specs):
        return assess([OrderProgress(f"O{i}", d, e) for i, (d, e) in enumerate(specs)], CFG)

    def test_khong_kich_hoat_khi_on_time(self):
        d = decide_reoptimization(self.a((1000, 100), (1000, 200)), 3, RCFG, 0)
        self.assertFalse(d.allowed)
        self.assertEqual(d.triggers, [])

    def test_kich_hoat_khi_tre(self):
        d = decide_reoptimization(self.a((100, 500), (1000, 200)), 3, RCFG, 0)
        self.assertTrue(d.allowed)
        self.assertEqual(d.triggers, ["late"])

    def test_at_risk_phu_thuoc_cau_hinh(self):
        a = self.a((1000, 970), (1000, 100))
        self.assertFalse(decide_reoptimization(a, 3, RCFG, 0).allowed)
        on = ReoptConfig(True, 200, 120, False)
        self.assertEqual(decide_reoptimization(a, 3, on, 0).triggers, ["at_risk"])

    def test_lech_tuyen(self):
        a = self.a((1000, 100), (1000, 200))
        self.assertTrue(decide_reoptimization(a, 3, RCFG, 0, off_route_m=500).allowed)
        self.assertFalse(decide_reoptimization(a, 3, RCFG, 0, off_route_m=200).allowed)
        self.assertFalse(decide_reoptimization(a, 3, RCFG, 0, off_route_m=50).allowed)

    def test_gps_loi_bo_qua_lech_tuyen_nhung_van_xet_tre(self):
        a = self.a((1000, 100), (1000, 200))
        d = decide_reoptimization(a, 3, RCFG, 0, off_route_m=9999, position_ok=False)
        self.assertFalse(d.allowed)
        self.assertTrue(d.notes)
        late = self.a((100, 500), (1000, 200))
        d2 = decide_reoptimization(late, 3, RCFG, 0, off_route_m=None, position_ok=False)
        self.assertTrue(d2.allowed)

    def test_chan_khi_khong_du_diem(self):
        late = self.a((100, 500))
        self.assertFalse(decide_reoptimization(late, 1, RCFG, 0).allowed)
        self.assertFalse(decide_reoptimization(late, 0, RCFG, 0).allowed)
        lock = ReoptConfig(False, 200, 120, True)
        late2 = self.a((100, 500), (1000, 5))
        self.assertFalse(decide_reoptimization(late2, 2, lock, 0).allowed)
        self.assertTrue(decide_reoptimization(late2, 3, lock, 0).allowed)

    def test_chan_khi_vuot_gioi_han_don(self):
        late = self.a((100, 500))
        self.assertFalse(decide_reoptimization(late, 6, RCFG, 0).allowed)

    def test_cooldown(self):
        late = self.a((100, 500), (1000, 5))
        self.assertFalse(decide_reoptimization(late, 3, RCFG, 150, last_reopt_s=100).allowed)
        self.assertTrue(decide_reoptimization(late, 3, RCFG, 220, last_reopt_s=100).allowed)
        self.assertTrue(decide_reoptimization(late, 3, RCFG, 5, last_reopt_s=None).allowed)

    def test_duong_bi_chan_bo_qua_cooldown(self):
        ok = self.a((1000, 100), (1000, 200))
        d = decide_reoptimization(ok, 3, RCFG, 110, last_reopt_s=100, plan_feasible=False)
        self.assertTrue(d.allowed)
        self.assertEqual(d.triggers, ["blocked"])

    def test_don_da_giao_khong_kich_hoat(self):
        a = assess([OrderProgress("A", 10, None, True, 500), OrderProgress("B", 1000, 100),
                    OrderProgress("C", 1000, 100)], CFG)
        self.assertFalse(decide_reoptimization(a, 2, RCFG, 0).allowed)

    def test_dau_vao_sai(self):
        a = self.a((100, 500))
        for kwargs in (dict(now_s=-1), dict(now_s=0, last_reopt_s=math.nan)):
            with self.assertRaises(DelayRiskInputError):
                decide_reoptimization(a, 3, RCFG, **kwargs)
        with self.assertRaises(DelayRiskInputError):
            decide_reoptimization(a, True, RCFG, 0)

    def test_cau_hinh_reopt_khong_hop_le(self):
        for args in ((1, 200, 1, False), (True, -1, 1, False), (True, 1, math.nan, False),
                     (True, 1, 1, "x")):
            with self.assertRaises(DelayRiskInputError):
                ReoptConfig(*args)
        with self.assertRaises(DelayRiskInputError):
            ReoptConfig(True, 1, 1, False, max_stops=0)


if __name__ == "__main__":
    unittest.main()
