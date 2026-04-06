import unittest

from axis_bulk_config.read_config import build_summary


class ReadSummaryTest(unittest.TestCase):
    def test_overlay_active_when_text_overlay_elements_are_enabled(self):
        out = {
            "device_info": {"data": {"propertyList": {}}},
            "params": {
                "Image": {
                    "root.Image.I0.Overlay.Enabled": "no",
                    "root.Image.I0.Text.TextEnabled": "yes",
                    "root.Image.I0.Text.ClockEnabled": "no",
                    "root.Image.I0.Text.DateEnabled": "yes",
                    "root.Image.I0.Text.String": "",
                },
                "Storage": {},
            },
            "stream_profiles_structured": [],
        }

        summary = build_summary(out)

        self.assertTrue(summary["overlay_active"])

    def test_overlay_active_when_overlay_text_is_non_empty(self):
        out = {
            "device_info": {"data": {"propertyList": {}}},
            "params": {
                "Image": {
                    "root.Image.I0.Overlay.Enabled": "no",
                    "root.Image.I0.Text.TextEnabled": "no",
                    "root.Image.I0.Text.ClockEnabled": "no",
                    "root.Image.I0.Text.DateEnabled": "no",
                    "root.Image.I0.Text.String": "AES-PlateRecognizer-Entry-Cam",
                },
                "Storage": {},
            },
            "stream_profiles_structured": [],
        }

        summary = build_summary(out)

        self.assertTrue(summary["overlay_active"])

    def test_overlay_active_ignores_non_primary_channels(self):
        out = {
            "device_info": {"data": {"propertyList": {}}},
            "params": {
                "Image": {
                    "root.Image.I1.Text.TextEnabled": "yes",
                    "root.Image.I1.Text.String": "secondary",
                },
                "Storage": {},
            },
            "stream_profiles_structured": [],
        }

        summary = build_summary(out)

        self.assertFalse(summary["overlay_active"])
        self.assertEqual(summary["overlay"], {})

    def test_overlay_active_when_dynamic_overlay_is_visible(self):
        out = {
            "device_info": {"data": {"propertyList": {}}},
            "params": {
                "Image": {
                    "root.Image.I0.Overlay.Enabled": "no",
                    "root.Image.I0.Text.TextEnabled": "no",
                },
                "Storage": {},
            },
            "dynamic_overlays": {
                "data": {
                    "textOverlays": [
                        {
                            "text": "AES-PlateRecognizer-Entry-Cam %F %T #r",
                            "visible": True,
                        }
                    ]
                }
            },
            "stream_profiles_structured": [],
        }

        summary = build_summary(out)

        self.assertTrue(summary["overlay_active"])


if __name__ == "__main__":
    unittest.main()
