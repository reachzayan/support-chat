from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# Valid Argon2id hash used for constant-time login checks on unknown/inactive accounts.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$YXNkZmFzZGZhc2RmYXNkZg"
    "$YXNkZmFzZGZhc2RmYXNkZmFzZGZhc2RmYXNkZmFzZGZhc2Rm"
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash, VerificationError):
        return False


def verify_password_or_dummy(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        verify_password(_DUMMY_PASSWORD_HASH, password)
        return False
    return verify_password(password_hash, password)
