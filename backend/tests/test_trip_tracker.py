import _paths
import math
import unittest

from delay_risk_detector import (AlertConfig, STATUS_DELIVERED, STATUS_LATE, STATUS_ON_TIME,
                                 ReoptConfig)
from multistop_optimizer import CostConfig, Stop
from trip_tracker import (GpsConfig, GpsFix, TrackerError, TripTracker, distance_to_segment_m,
                          validate_fix)

M = [[0, 10, 10, 10], [10, 0, 10, 10], [10, 10, 0, 10], [10, 10, 10, 0]]
COORDS = [(10.0, 106.0), (10.0, 106.01), (10.01, 106.01), (10.01, 106.0)]
COST = CostConfig(late_weight=1, time_weight=1, risk_margin=0, min_improvement=0)
GPS = GpsConfig(max_age_s=30, max_accuracy_m=50)


def make(deadlines=(1000, 1000, 1000), lock=False, matrix=M, reopt=None, **kw):
    stops = [Stop("A", 1, 0, deadlines[0]), Stop("B", 2, 0, deadlines[1]),
             Stop("C", 3, 0, deadlines[2])]
    rc = reopt or ReoptConfig(False, 200, 0, lock)
    return TripTracker(matrix, stops, COST, AlertConfig(5), rc, GPS, node_coords=COORDS, **kw)


class TestProgress(unittest.TestCase):
    def test_eta_ban_dau(self):
        tr = make()
        etas = {s.order_id: s.complete_s for s in tr.plan().stops}
        self.assertEqual(etas, {"A": 10, "B": 20, "C": 30})

    def test_giao_xong_tinh_lai_eta_con_lai(self):
        tr = make()
        tr.complete_stop("A", 50)
        etas = {s.order_id: s.complete_s for s in tr.plan().stops}
        self.assertEqual(etas, {"B": 60, "C": 70})
        self.assertEqual(tr.current_node, 1)
        status = {a.order_id: a.status for a in tr.assess()}
        self.assertEqual(status["A"], STATUS_DELIVERED)

    def test_da_giao_xong_khong_giao_lai(self):
        tr = make()
        tr.complete_stop("A", 10)
        with self.assertRaises(TrackerError):
            tr.complete_stop("A", 20)
        with self.assertRaises(TrackerError):
            tr.complete_stop("Z", 20)

    def test_thoi_diem_giao_khong_hop_le(self):
        tr = make()
        tr.complete_stop("A", 100)
        for bad in (50, math.nan, -1):
            with self.assertRaises(TrackerError):
                tr.complete_stop("B", bad)

    def test_giao_het_khong_con_ke_hoach(self):
        tr = make()
        for oid, t in (("A", 10), ("B", 20), ("C", 30)):
            tr.complete_stop(oid, t)
        self.assertIsNone(tr.plan())
        res = tr.check(30)
        self.assertFalse(res.decision.allowed)
        self.assertTrue(all(a.status == STATUS_DELIVERED for a in res.assessments))

    def test_tre_ghi_nhan_lam_eta_doi_va_canh_bao(self):
        tr = make(deadlines=(1000, 1000, 100))
        self.assertEqual({a.order_id: a.status for a in tr.assess()}["C"], STATUS_ON_TIME)
        tr.apply_delay(200)
        self.assertEqual({a.order_id: a.status for a in tr.assess()}["C"], STATUS_LATE)
        with self.assertRaises(TrackerError):
            tr.apply_delay(-1)

    def test_eta_moi_cho_diem_dang_toi(self):
        tr = make(deadlines=(1000, 1000, 100))
        tr.report_new_eta("A", 90)
        etas = {s.order_id: s.complete_s for s in tr.plan().stops}
        self.assertEqual(etas, {"A": 90, "B": 100, "C": 110})
        tr.report_new_eta("A", 20)
        self.assertEqual(tr.plan().stops[0].complete_s, 20)
        with self.assertRaises(TrackerError):
            tr.report_new_eta("B", 50)
        with self.assertRaises(TrackerError):
            tr.report_new_eta("A", math.nan)

    def test_cap_nhat_ma_tran(self):
        tr = make()
        slow = [[0 if i == j else 100 for j in range(4)] for i in range(4)]
        tr.update_time_matrix(slow)
        self.assertEqual(tr.plan().stops[-1].complete_s, 300)
        with self.assertRaises(TrackerError):
            tr.update_time_matrix([[0]])

    def test_khoi_tao_sai(self):
        with self.assertRaises(TrackerError):
            make(initial_order=["A", "B"])
        with self.assertRaises(TrackerError):
            TripTracker(M, [Stop("A", 1), Stop("A", 2)], COST, AlertConfig(5),
                        ReoptConfig(False, 1, 0, False), GPS)
        with self.assertRaises(TrackerError):
            TripTracker(M, [Stop("A", 9)], COST, AlertConfig(5),
                        ReoptConfig(False, 1, 0, False), GPS)


class TestGps(unittest.TestCase):
    def test_validate(self):
        ok = GpsFix(10.0, 106.0, 95, 10)
        self.assertEqual(validate_fix(ok, 100, GPS), (True, "ok"))
        bad = [GpsFix(math.nan, 106.0, 95), GpsFix(91, 106.0, 95), GpsFix(10, 181, 95),
               GpsFix(10, 106, 200), GpsFix(10, 106, 10), GpsFix(10, 106, 95, 500),
               GpsFix(10, 106, 95, -1), GpsFix(True, 106, 95)]
        for fix in bad:
            self.assertFalse(validate_fix(fix, 100, GPS)[0], msg=str(fix))

    def test_khoang_cach_den_doan(self):
        a, b = (10.0, 106.0), (10.0, 106.01)
        self.assertAlmostEqual(distance_to_segment_m((10.0, 106.005), a, b), 0, places=3)
        self.assertAlmostEqual(distance_to_segment_m((10.001, 106.005), a, b), 111, delta=0.5)
        beyond = distance_to_segment_m((10.0, 106.02), a, b)
        self.assertAlmostEqual(beyond, 0.01 * 111000 * math.cos(math.radians(10.0)), delta=1)
        self.assertAlmostEqual(distance_to_segment_m((10.001, 106.0), a, a), 111, delta=0.5)

    def test_gps_loi_khong_cap_nhat_lech_tuyen(self):
        tr = make()
        ok, _ = tr.submit_gps(GpsFix(10.0, 106.005, 99), 100)
        self.assertTrue(ok)
        self.assertAlmostEqual(tr.off_route_m, 0, places=2)
        ok, reason = tr.submit_gps(GpsFix(math.nan, 106.0, 99), 100)
        self.assertFalse(ok)
        self.assertIsNone(tr.off_route_m)
        self.assertFalse(tr.position_ok)
        self.assertIn("hữu hạn", reason)

    def test_lech_tuyen_kich_hoat_tinh_lai_nhung_gps_loi_thi_khong(self):
        tr = make()
        tr.submit_gps(GpsFix(10.02, 106.005, 99), 100)
        self.assertGreater(tr.off_route_m, 200)
        self.assertEqual(tr.check(100).decision.triggers, ["off_route"])
        tr2 = make()
        tr2.submit_gps(GpsFix(10.02, 106.005, 99, 9999), 100)
        res = tr2.check(100)
        self.assertFalse(res.decision.allowed)
        self.assertEqual(res.decision.triggers, [])

    def test_gps_hop_le_phuc_hoi(self):
        tr = make()
        tr.submit_gps(GpsFix(10.0, 106.0, 99, 9999), 100)
        self.assertFalse(tr.position_ok)
        tr.submit_gps(GpsFix(10.0, 106.005, 99, 5), 100)
        self.assertTrue(tr.position_ok)

    def test_giao_xong_xoa_lech_tuyen(self):
        tr = make()
        tr.submit_gps(GpsFix(10.02, 106.005, 99), 100)
        tr.complete_stop("A", 10)
        self.assertIsNone(tr.off_route_m)

    def test_khong_co_toa_do_nut(self):
        tr = TripTracker(M, [Stop("A", 1, 0, 100), Stop("B", 2, 0, 100)], COST, AlertConfig(5),
                         ReoptConfig(False, 1, 0, False), GPS)
        ok, reason = tr.submit_gps(GpsFix(10.0, 106.0, 99), 100)
        self.assertTrue(ok)
        self.assertIsNone(tr.off_route_m)


class TestReoptFlow(unittest.TestCase):
    def test_tre_dao_thu_tu_theo_deadline(self):
        tr = make(deadlines=(1000, 15, 1000))
        res = tr.check(0)
        self.assertTrue(res.adopted)
        self.assertEqual(tr.order[0], "B")
        self.assertEqual(tr.reopt_count, 1)

    def test_khong_tre_khong_tinh_lai(self):
        tr = make()
        res = tr.check(0)
        self.assertIsNone(res.replan)
        self.assertEqual(tr.order, ["A", "B", "C"])
        self.assertEqual(tr.reopt_count, 0)

    def test_lock_next_giu_diem_dau(self):
        tr = make(deadlines=(1000, 15, 20), lock=True)
        tr.check(0)
        self.assertEqual(tr.order[0], "A")

    def test_lock_next_khong_du_diem_de_dao(self):
        stops = [Stop("A", 1, 0, 1000), Stop("B", 2, 0, 5)]
        tr = TripTracker(M, stops, COST, AlertConfig(5), ReoptConfig(False, 200, 0, True), GPS)
        res = tr.check(0)
        self.assertFalse(res.decision.allowed)
        self.assertIsNone(res.replan)

    def test_dung_dieu_kien_sau_khi_giao_mot_diem(self):
        tr = make(deadlines=(1000, 1000, 1000))
        tr.complete_stop("A", 10)
        tr.apply_delay(2000)
        res = tr.check(2010)
        self.assertEqual(res.decision.triggers, ["late"])
        self.assertTrue(res.decision.allowed)

    def test_cooldown_giua_hai_lan_check(self):
        rc = ReoptConfig(False, 200, 100, False)
        tr = make(deadlines=(1000, 15, 1000), reopt=rc)
        self.assertTrue(tr.check(0).decision.allowed)
        tr.apply_delay(5000)
        res = tr.check(50)
        self.assertFalse(res.decision.allowed)
        self.assertIn("mới tính lại", res.decision.reason)
        self.assertTrue(tr.check(150).decision.allowed)

    def test_duong_bi_chan_bat_buoc_doi(self):
        blocked = [row[:] for row in M]
        blocked[0][1] = None
        tr = make(deadlines=(1000, 1000, 1000), matrix=blocked)
        self.assertIsNone(tr.plan())
        res = tr.check(0)
        self.assertEqual(res.decision.triggers, ["blocked"])
        self.assertTrue(res.adopted)
        self.assertNotEqual(tr.order[0], "A")
        self.assertIsNotNone(tr.plan())

    def test_force_replan(self):
        tr = make(deadlines=(1000, 15, 1000))
        self.assertTrue(tr.force_replan(0).adopted)

    def test_khong_deadline_khong_bao_tre(self):
        stops = [Stop("A", 1, 0, None), Stop("B", 2, 0, None), Stop("C", 3, 0, None)]
        tr = TripTracker(M, stops, COST, AlertConfig(5), ReoptConfig(False, 200, 0, False), GPS)
        tr.apply_delay(10 ** 6)
        res = tr.check(0)
        self.assertFalse(res.decision.allowed)
        self.assertEqual({a.status for a in res.assessments}, {"no_deadline"})


if __name__ == "__main__":
    unittest.main()
