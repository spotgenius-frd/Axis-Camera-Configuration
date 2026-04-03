"""
Entry point for python -m axis_bulk_config.
Use:
  python -m axis_bulk_config.discover <camera_ip> [options]
  python -m axis_bulk_config.read_config <camera_ip> [options]
  python -m axis_bulk_config.config_explorer <camera_ip> [options]
  python -m axis_bulk_config.apply cameras.csv [options]
"""

import sys


def main() -> int:
    print(
        "Axis bulk config: use one of:\n"
        "  python -m axis_bulk_config.discover <camera_ip> [--user USER] [--password PASS] [-o file.json]\n"
        "  python -m axis_bulk_config.read_config <camera_ip> [--user USER] [--password PASS] [-o file.json]\n"
        "  python -m axis_bulk_config.config_explorer <camera_ip> [--user USER] [--password PASS] [-i] [-o file.json] [--apply] [--firmware-info] [--capabilities]\n"
        "  python -m axis_bulk_config.apply cameras.csv [--report report.csv] [--dry-run]",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
