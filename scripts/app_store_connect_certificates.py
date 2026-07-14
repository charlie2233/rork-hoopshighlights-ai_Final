#!/usr/bin/env python3
"""Track the short-lived signing certificate created by Xcode in CI."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.appstoreconnect.apple.com"
CI_CERTIFICATE_NAME = "Apple Development: Created via API"
CI_CERTIFICATE_TYPE = "DEVELOPMENT"
MAX_API_ATTEMPTS = 3
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
PEM_CERTIFICATE_PATTERN = re.compile(
    br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def read_der_length(value: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(value):
        raise ValueError("DER length is missing")

    first = value[offset]
    offset += 1
    if first < 0x80:
        return first, offset

    byte_count = first & 0x7F
    if byte_count == 0 or byte_count > 4 or offset + byte_count > len(value):
        raise ValueError("DER length is invalid")

    length = int.from_bytes(value[offset : offset + byte_count], "big")
    if length < 0x80:
        raise ValueError("DER length is not minimally encoded")
    return length, offset + byte_count


def read_der_integer(value: bytes, offset: int, width: int) -> tuple[bytes, int]:
    if offset >= len(value) or value[offset] != 0x02:
        raise ValueError("DER integer is missing")

    length, content_offset = read_der_length(value, offset + 1)
    end = content_offset + length
    if length == 0 or end > len(value):
        raise ValueError("DER integer length is invalid")

    integer = value[content_offset:end]
    if integer[0] & 0x80:
        raise ValueError("DER integer must be positive")
    if len(integer) > 1 and integer[0] == 0:
        integer = integer[1:]
    if len(integer) > width:
        raise ValueError("DER integer exceeds the expected width")
    return integer.rjust(width, b"\0"), end


def ecdsa_der_to_raw(signature: bytes, width: int = 32) -> bytes:
    if not signature or signature[0] != 0x30:
        raise ValueError("ECDSA signature is not a DER sequence")

    sequence_length, offset = read_der_length(signature, 1)
    sequence_end = offset + sequence_length
    if sequence_end != len(signature):
        raise ValueError("ECDSA signature sequence length is invalid")

    r_value, offset = read_der_integer(signature, offset, width)
    s_value, offset = read_der_integer(signature, offset, width)
    if offset != sequence_end:
        raise ValueError("ECDSA signature contains trailing values")
    return r_value + s_value


def create_token(
    key_path: Path,
    key_id: str,
    issuer_id: str,
    *,
    issued_at: int | None = None,
) -> str:
    timestamp = int(time.time()) if issued_at is None else issued_at
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    payload = {
        "iss": issuer_id,
        "iat": timestamp,
        "exp": timestamp + 900,
        "aud": "appstoreconnect-v1",
    }
    encoded_header = base64url(json.dumps(header, separators=(",", ":")).encode("ascii"))
    encoded_payload = base64url(json.dumps(payload, separators=(",", ":")).encode("ascii"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(key_path)],
        input=signing_input,
        capture_output=True,
        check=True,
    )
    return f"{encoded_header}.{encoded_payload}.{base64url(ecdsa_der_to_raw(result.stdout))}"


def normalized_serial(value: str) -> str:
    serial = re.sub(r"[^0-9A-F]", "", value.upper()).lstrip("0")
    return serial or "0"


def local_ci_certificate_serials() -> set[str]:
    result = subprocess.run(
        ["security", "find-certificate", "-a", "-c", CI_CERTIFICATE_NAME, "-p"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 and not result.stdout:
        return set()

    serials: set[str] = set()
    for certificate in PEM_CERTIFICATE_PATTERN.findall(result.stdout):
        serial_result = subprocess.run(
            ["openssl", "x509", "-noout", "-serial"],
            input=certificate,
            capture_output=True,
            check=True,
            text=False,
        )
        serial_line = serial_result.stdout.decode("ascii").strip()
        if "=" not in serial_line:
            raise RuntimeError("OpenSSL did not return a certificate serial number")
        serials.add(normalized_serial(serial_line.split("=", 1)[1]))
    return serials


def api_request(method: str, path: str, token: str) -> dict[str, Any] | None:
    for attempt in range(MAX_API_ATTEMPTS):
        request = Request(
            f"{API_BASE_URL}{path}",
            method=method,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
            return json.loads(body) if body else None
        except HTTPError as error:
            detail = error.read(1000).decode("utf-8", errors="replace")
            if error.code not in RETRYABLE_HTTP_STATUSES or attempt == MAX_API_ATTEMPTS - 1:
                raise RuntimeError(f"App Store Connect API returned HTTP {error.code}: {detail}") from error
        except URLError as error:
            if attempt == MAX_API_ATTEMPTS - 1:
                raise RuntimeError(f"App Store Connect API request failed: {error.reason}") from error
        time.sleep(2**attempt)

    raise AssertionError("App Store Connect retry loop exited unexpectedly")


def list_certificates(token: str) -> list[dict[str, Any]]:
    payload = api_request("GET", "/v1/certificates?limit=200", token)
    data = payload.get("data") if payload else None
    if not isinstance(data, list):
        raise RuntimeError("App Store Connect certificate response is missing data")
    return data


def ci_certificates(certificates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        certificate
        for certificate in certificates
        if certificate.get("attributes", {}).get("name") == CI_CERTIFICATE_NAME
        and certificate.get("attributes", {}).get("certificateType") == CI_CERTIFICATE_TYPE
        and isinstance(certificate.get("id"), str)
    ]


def ci_certificate_ids(certificates: list[dict[str, Any]]) -> set[str]:
    return {certificate["id"] for certificate in ci_certificates(certificates)}


def auth_token(args: argparse.Namespace) -> str:
    return create_token(Path(args.key_path), args.key_id, args.issuer_id)


def snapshot(args: argparse.Namespace) -> int:
    existing = ci_certificates(list_certificates(auth_token(args)))
    if existing:
        raise RuntimeError(
            f"Found {len(existing)} preexisting CI development certificate(s); reconcile them before starting another signed job"
        )

    local_serials = sorted(local_ci_certificate_serials())
    Path(args.output).write_text(
        json.dumps({"version": 2, "localCertificateSerials": local_serials}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Confirmed zero preexisting CI development certificates; captured {len(local_serials)} local serial(s)")
    return 0


def cleanup(args: argparse.Namespace) -> int:
    snapshot_payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    before = snapshot_payload.get("localCertificateSerials")
    if snapshot_payload.get("version") != 2 or not isinstance(before, list) or not all(
        isinstance(value, str) for value in before
    ):
        raise RuntimeError("Certificate snapshot has an unsupported format")

    token = auth_token(args)
    owned_serials = local_ci_certificate_serials() - {normalized_serial(value) for value in before}
    owned_serials.update(normalized_serial(value) for value in args.certificate_serial)
    candidates = [
        certificate
        for certificate in ci_certificates(list_certificates(token))
        if normalized_serial(str(certificate.get("attributes", {}).get("serialNumber") or "")) in owned_serials
    ]
    if len(candidates) > 1:
        raise RuntimeError(
            f"Refusing to revoke {len(candidates)} certificates; expected at most one identity owned by this runner"
        )

    for certificate in candidates:
        api_request("DELETE", f"/v1/certificates/{certificate['id']}", token)
    print(f"Revoked {len(candidates)} development certificate(s) owned by this CI runner")
    return 0


def add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--key-path", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--issuer-id", required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = commands.add_parser("snapshot")
    add_auth_arguments(snapshot_parser)
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.set_defaults(handler=snapshot)

    cleanup_parser = commands.add_parser("cleanup")
    add_auth_arguments(cleanup_parser)
    cleanup_parser.add_argument("--snapshot", required=True)
    cleanup_parser.add_argument("--certificate-serial", action="append", default=[])
    cleanup_parser.set_defaults(handler=cleanup)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
