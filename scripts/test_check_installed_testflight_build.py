import unittest

from scripts.check_installed_testflight_build import (
    EXPECTED_BUNDLE_ID,
    extract_app_metadata,
    find_app_record,
    parse_device_table,
    state_is_available,
)


class CheckInstalledTestflightBuildTests(unittest.TestCase):
    def test_parse_available_paired_iphone_keeps_model_clean(self) -> None:
        output = """Name             Hostname                           Identifier                             State                Model
--------------   --------------------------------   ------------------------------------   -------------------  --------------------------
charlie iPhone   charliedeiPhone.coredevice.local   E5786BB6-0095-5509-8B85-110C0B5CE6D3   available (paired)   iPhone 15 Pro (iPhone16,1)
"""

        devices = parse_device_table(output)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["state"], "available (paired)")
        self.assertEqual(devices[0]["model"], "iPhone 15 Pro (iPhone16,1)")
        self.assertTrue(state_is_available(devices[0]["state"]))

    def test_find_app_record_accepts_nested_devicectl_shape(self) -> None:
        payload = {
            "result": {
                "apps": [
                    {
                        "bundleIdentifier": EXPECTED_BUNDLE_ID,
                        "shortVersionString": "1.0.0",
                        "bundleVersion": "51",
                        "name": "HoopClips",
                    }
                ]
            }
        }

        app = find_app_record(payload, EXPECTED_BUNDLE_ID)

        self.assertIsNotNone(app)
        self.assertEqual(
            extract_app_metadata(app or {}),
            {
                "bundleId": EXPECTED_BUNDLE_ID,
                "marketingVersion": "1.0.0",
                "buildNumber": "51",
                "name": "HoopClips",
            },
        )


if __name__ == "__main__":
    unittest.main()
