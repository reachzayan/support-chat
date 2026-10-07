import subprocess
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from app.services.web_push import decode_key


def test_key_setup_writes_secret_to_env_without_printing_or_replacing_it(tmp_path):
    env = tmp_path / "local.env"
    env.write_text("OTHER_SETTING=keep-me\nPUSH_VAPID_PRIVATE_KEY=\n")
    result = subprocess.run(
        [str(Path(".venv/bin/python")), "scripts/generate_push_keys.py", "--env-file", str(env)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    entries = dict(line.split("=", 1) for line in env.read_text().splitlines() if "=" in line)
    secret = entries["PUSH_VAPID_PRIVATE_KEY"]
    assert entries["OTHER_SETTING"] == "keep-me"
    assert len(decode_key(secret)) == 32
    ec.derive_private_key(int.from_bytes(decode_key(secret)), ec.SECP256R1())
    assert secret not in result.stdout and secret not in result.stderr
    again = subprocess.run(
        [str(Path(".venv/bin/python")), "scripts/generate_push_keys.py", "--env-file", str(env)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert again.returncode == 0, again.stderr
    assert env.read_text().count(secret) == 1
