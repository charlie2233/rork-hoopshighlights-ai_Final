import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from scripts.app_store_connect_certificates import (
    CI_CERTIFICATE_NAME,
    api_request,
    ci_certificate_ids,
    cleanup,
    ecdsa_der_to_raw,
    snapshot,
)


class AppStoreConnectCertificateTests(unittest.TestCase):
    def test_ecdsa_der_to_raw_pads_both_integers(self) -> None:
        signature = bytes.fromhex("3006020101020102")

        raw = ecdsa_der_to_raw(signature)

        self.assertEqual(len(raw), 64)
        self.assertEqual(raw[:32], b"\0" * 31 + b"\x01")
        self.assertEqual(raw[32:], b"\0" * 31 + b"\x02")

    def test_ecdsa_der_to_raw_removes_positive_sign_padding(self) -> None:
        signature = bytes.fromhex("300802020080020200ff")

        raw = ecdsa_der_to_raw(signature)

        self.assertEqual(raw[:32], b"\0" * 31 + b"\x80")
        self.assertEqual(raw[32:], b"\0" * 31 + b"\xff")

    def test_ecdsa_der_to_raw_rejects_trailing_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "sequence length"):
            ecdsa_der_to_raw(bytes.fromhex("300602010102010200"))

    def test_ci_certificate_ids_requires_exact_name_and_type(self) -> None:
        certificates = [
            {
                "id": "ci-development",
                "attributes": {
                    "name": CI_CERTIFICATE_NAME,
                    "certificateType": "DEVELOPMENT",
                },
            },
            {
                "id": "distribution",
                "attributes": {
                    "name": "iOS Distribution: Account Holder",
                    "certificateType": "IOS_DISTRIBUTION",
                },
            },
            {
                "id": "named-similarly",
                "attributes": {
                    "name": f"{CI_CERTIFICATE_NAME} old",
                    "certificateType": "DEVELOPMENT",
                },
            },
        ]

        self.assertEqual(ci_certificate_ids(certificates), {"ci-development"})

    def test_cleanup_revokes_only_the_new_matching_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "snapshot.json"
            snapshot_path.write_text(
                json.dumps({"version": 2, "localCertificateSerials": ["AA"]}),
                encoding="utf-8",
            )
            certificates = [
                self.ci_certificate("created-by-this-job", "BB"),
                {
                    "id": "distribution",
                    "attributes": {
                        "name": "iOS Distribution: Account Holder",
                        "certificateType": "IOS_DISTRIBUTION",
                        "serialNumber": "CC",
                    },
                },
            ]
            args = SimpleNamespace(snapshot=str(snapshot_path), certificate_serial=[])

            with patch(
                "scripts.app_store_connect_certificates.auth_token",
                return_value="token",
            ), patch(
                "scripts.app_store_connect_certificates.list_certificates",
                return_value=certificates,
            ), patch(
                "scripts.app_store_connect_certificates.local_ci_certificate_serials",
                return_value={"AA", "BB"},
            ), patch(
                "scripts.app_store_connect_certificates.api_request"
            ) as api_request:
                self.assertEqual(cleanup(args), 0)

            api_request.assert_called_once_with(
                "DELETE",
                "/v1/certificates/created-by-this-job",
                "token",
            )

    def test_cleanup_refuses_to_revoke_multiple_new_certificates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "snapshot.json"
            snapshot_path.write_text(
                json.dumps({"version": 2, "localCertificateSerials": []}),
                encoding="utf-8",
            )
            args = SimpleNamespace(snapshot=str(snapshot_path), certificate_serial=[])

            with patch(
                "scripts.app_store_connect_certificates.auth_token",
                return_value="token",
            ), patch(
                "scripts.app_store_connect_certificates.list_certificates",
                return_value=[self.ci_certificate("one", "01"), self.ci_certificate("two", "02")],
            ), patch(
                "scripts.app_store_connect_certificates.local_ci_certificate_serials",
                return_value={"1", "2"},
            ), patch(
                "scripts.app_store_connect_certificates.api_request"
            ) as api_request:
                with self.assertRaisesRegex(RuntimeError, "Refusing to revoke 2"):
                    cleanup(args)

            api_request.assert_not_called()

    def test_cleanup_does_not_revoke_unowned_api_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "snapshot.json"
            snapshot_path.write_text(
                json.dumps({"version": 2, "localCertificateSerials": []}),
                encoding="utf-8",
            )
            args = SimpleNamespace(snapshot=str(snapshot_path), certificate_serial=[])

            with patch(
                "scripts.app_store_connect_certificates.auth_token",
                return_value="token",
            ), patch(
                "scripts.app_store_connect_certificates.list_certificates",
                return_value=[self.ci_certificate("another-actor", "AA")],
            ), patch(
                "scripts.app_store_connect_certificates.local_ci_certificate_serials",
                return_value=set(),
            ), patch(
                "scripts.app_store_connect_certificates.api_request"
            ) as api_request:
                self.assertEqual(cleanup(args), 0)

            api_request.assert_not_called()

    def test_snapshot_blocks_preexisting_api_created_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(output=str(Path(temp_dir) / "snapshot.json"))
            with patch(
                "scripts.app_store_connect_certificates.auth_token",
                return_value="token",
            ), patch(
                "scripts.app_store_connect_certificates.list_certificates",
                return_value=[self.ci_certificate("stale", "AA")],
            ):
                with self.assertRaisesRegex(RuntimeError, "reconcile them"):
                    snapshot(args)

    def test_api_request_retries_transient_network_failure(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"data": []}'

        with patch(
            "scripts.app_store_connect_certificates.urlopen",
            side_effect=[URLError("temporary"), response],
        ) as urlopen, patch("scripts.app_store_connect_certificates.time.sleep") as sleep:
            self.assertEqual(api_request("GET", "/v1/certificates", "token"), {"data": []})

        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1)

    @staticmethod
    def ci_certificate(certificate_id: str, serial_number: str) -> dict:
        return {
            "id": certificate_id,
            "attributes": {
                "name": CI_CERTIFICATE_NAME,
                "certificateType": "DEVELOPMENT",
                "serialNumber": serial_number,
            },
        }


if __name__ == "__main__":
    unittest.main()
