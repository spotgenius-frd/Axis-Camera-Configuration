import unittest
from unittest.mock import Mock, patch

from axis_bulk_config.firmware_lookup import get_latest_firmware


class FirmwareLookupTest(unittest.TestCase):
    @patch("axis_bulk_config.firmware_lookup.requests.get")
    def test_returns_support_page_even_when_latest_scrape_fails(self, requests_get):
        requests_get.side_effect = Exception("timeout")

        result = get_latest_firmware("AXIS Q1786-LE Network Camera")

        self.assertIsNotNone(result)
        self.assertEqual(
            result["support_page_url"],
            "https://www.axis.com/products/axis-q1786-le/support",
        )
        self.assertIsNone(result["version"])
        self.assertIsNone(result["download_url"])

    @patch("axis_bulk_config.firmware_lookup.requests.get")
    def test_extracts_latest_version_and_direct_download(self, requests_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <div>Version 11.11.192 - AXIS OS LTS 2024</div>
        <a href="https://www.axis.com/ftp/pub/axis/software/P/Q1786-LE/11.11.192/axis.bin">Download</a>
        <div>Integrity checksum: 1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef</div>
        """
        requests_get.return_value = response

        result = get_latest_firmware("AXIS Q1786-LE Network Camera")

        self.assertEqual(result["version"], "11.11.192")
        self.assertEqual(
            result["download_url"],
            "https://www.axis.com/ftp/pub/axis/software/P/Q1786-LE/11.11.192/axis.bin",
        )
        self.assertEqual(
            result["support_page_url"],
            "https://www.axis.com/products/axis-q1786-le/support",
        )


if __name__ == "__main__":
    unittest.main()
