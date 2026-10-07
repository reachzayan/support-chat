"""Create a persistent local VAPID key without printing the private key."""

import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    content = args.env_file.read_text() if args.env_file.exists() else ""
    lines = content.splitlines()
    previous = next(
        (
            line.split("=", 1)[1].strip()
            for line in lines
            if line.startswith("PUSH_VAPID_PRIVATE_KEY=")
        ),
        "",
    )
    if previous:
        print("Existing push key preserved.")
        return
    key = ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value.to_bytes(32)
    encoded = base64.urlsafe_b64encode(key).decode().rstrip("=")
    lines = [line for line in lines if not line.startswith("PUSH_VAPID_PRIVATE_KEY=")]
    lines.append("PUSH_VAPID_PRIVATE_KEY=" + encoded)
    if not any(line.startswith("PUSH_VAPID_SUBJECT=") for line in lines):
        lines.append("PUSH_VAPID_SUBJECT=mailto:notifications@supportchat.local")
    # The private key is a deployment secret and must remain stable across restarts.
    descriptor = os.open(args.env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as destination:
        destination.write("\n".join(lines) + "\n")
    args.env_file.chmod(0o600)
    print("Push key saved to the env file. Restart the API and worker to enable push.")


if __name__ == "__main__":
    main()
