import unittest

from ai_usage_tray.icon_renderer import _badge_level, _display_percent
from ai_usage_tray.providers.base import ProviderUsage, UsageWindow
from ai_usage_tray.tray_app import _build_usage_tooltip


class UiUsageSummaryTests(unittest.TestCase):
    def test_display_percent_uses_shortest_window(self):
        windows = [
            UsageWindow("5-hour rolling", used_percent=18, remaining_percent=82),
            UsageWindow("Weekly", used_percent=59, remaining_percent=41),
            UsageWindow("Monthly", used_percent=26, remaining_percent=74),
        ]

        self.assertEqual(_display_percent(windows), 82)


    def test_badge_level_ignores_shortest_window_and_warns_for_longer_windows(self):
        windows = [
            UsageWindow("5-hour rolling", used_percent=92, remaining_percent=8),
            UsageWindow("Weekly", used_percent=59, remaining_percent=41),
            UsageWindow("Monthly", used_percent=26, remaining_percent=74),
        ]

        self.assertEqual(_badge_level(windows), "medium")


    def test_badge_level_is_urgent_when_longer_window_is_low_or_reached(self):
        windows = [
            UsageWindow("5-hour rolling", used_percent=18, remaining_percent=82),
            UsageWindow("Weekly", used_percent=78, remaining_percent=22),
            UsageWindow("Monthly", used_percent=26, remaining_percent=74),
        ]

        self.assertEqual(_badge_level(windows), "low")


    def test_usage_tooltip_lists_windows_on_separate_lines(self):
        usage = ProviderUsage(
            provider_id="opencode-go",
            provider_name="OpenCode Go",
            windows=[
                UsageWindow("5-hour rolling", used_percent=18, remaining_percent=82, reset_at=0),
                UsageWindow("Weekly", used_percent=59, remaining_percent=41, reset_at=0),
                UsageWindow("Monthly", used_percent=26, remaining_percent=74, reset_at=0),
            ],
            last_refreshed="14:32:10",
        )

        self.assertEqual(
            _build_usage_tooltip("OpenCode Go", usage),
            "OpenCode Go\n"
            "5-hour rolling: 82% left\n"
            "Weekly: 41% left\n"
            "Monthly: 74% left\n"
            "Updated: 14:32:10",
        )


if __name__ == "__main__":
    unittest.main()
