import unittest
from datetime import datetime
from app.schedule_evaluator import is_schedule_active, SENSITIVITY_PRESETS

class TestScheduleEvaluator(unittest.TestCase):

    def test_presets_mapping(self):
        self.assertIn("low", SENSITIVITY_PRESETS)
        self.assertIn("medium", SENSITIVITY_PRESETS)
        self.assertIn("high", SENSITIVITY_PRESETS)

        self.assertEqual(SENSITIVITY_PRESETS["low"]["min_area"], 3000)
        self.assertEqual(SENSITIVITY_PRESETS["high"]["min_area"], 500)

    def test_24_7_schedule_always_active(self):
        self.assertTrue(is_schedule_active(schedule_type="24/7"))

    def test_standard_daytime_schedule(self):
        # Mon, Oct 20 2026, 10:00 AM (Monday = 0)
        dt_active = datetime(2026, 10, 19, 10, 0, 0)
        # Mon, Oct 20 2026, 20:00 PM (8 PM)
        dt_inactive = datetime(2026, 10, 19, 20, 0, 0)

        days = ["mon", "tue", "wed", "thu", "fri"]

        self.assertTrue(is_schedule_active(
            schedule_type="scheduled",
            schedule_days=days,
            start_time_str="08:00:00",
            end_time_str="18:00:00",
            dt_override=dt_active
        ))

        self.assertFalse(is_schedule_active(
            schedule_type="scheduled",
            schedule_days=days,
            start_time_str="08:00:00",
            end_time_str="18:00:00",
            dt_override=dt_inactive
        ))

    def test_overnight_midnight_crossover_schedule(self):
        # 22:00 to 06:00 (Overnight)
        dt_night = datetime(2026, 10, 19, 23, 30, 0)  # 11:30 PM -> Active
        dt_early = datetime(2026, 10, 19, 3, 15, 0)   # 03:15 AM -> Active
        dt_day = datetime(2026, 10, 19, 14, 0, 0)     # 02:00 PM -> Inactive

        days = ["mon", "tue", "wed", "thu", "fri"]

        self.assertTrue(is_schedule_active(
            schedule_type="scheduled",
            schedule_days=days,
            start_time_str="22:00:00",
            end_time_str="06:00:00",
            dt_override=dt_night
        ))

        self.assertTrue(is_schedule_active(
            schedule_type="scheduled",
            schedule_days=days,
            start_time_str="22:00:00",
            end_time_str="06:00:00",
            dt_override=dt_early
        ))

        self.assertFalse(is_schedule_active(
            schedule_type="scheduled",
            schedule_days=days,
            start_time_str="22:00:00",
            end_time_str="06:00:00",
            dt_override=dt_day
        ))

if __name__ == "__main__":
    unittest.main()
