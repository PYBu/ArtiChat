from __future__ import annotations

import asyncio

import bcrypt
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    ENABLE_PASSWORD_VALIDATION,
    PASSWORD_HASH_ALGORITHM,
    PASSWORD_VALIDATION_HINT,
    PASSWORD_VALIDATION_REGEX_PATTERN,
)


PASSWORD_BCRYPT_MAX_BYTES = 72


async def get_password_hash(password: str) -> str:
    if PASSWORD_HASH_ALGORITHM == 'argon2':
        from argon2 import PasswordHasher

        return await asyncio.to_thread(PasswordHasher().hash, password)
    if PASSWORD_HASH_ALGORITHM == 'bcrypt':
        return (await asyncio.to_thread(bcrypt.hashpw, password.encode('utf-8'), bcrypt.gensalt())).decode('utf-8')
    raise ValueError(f'Unsupported PASSWORD_HASH_ALGORITHM: {PASSWORD_HASH_ALGORITHM}')


def validate_password(password: str) -> bool:
    if PASSWORD_HASH_ALGORITHM == 'bcrypt' and len(password.encode('utf-8')) > PASSWORD_BCRYPT_MAX_BYTES:
        raise ValueError(ERROR_MESSAGES.PASSWORD_TOO_LONG)
    if ENABLE_PASSWORD_VALIDATION and not PASSWORD_VALIDATION_REGEX_PATTERN.match(password):
        raise ValueError(ERROR_MESSAGES.INVALID_PASSWORD(PASSWORD_VALIDATION_HINT))
    return True


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False

    if hashed_password.startswith('$argon2'):
        from argon2 import PasswordHasher
        from argon2.exceptions import InvalidHashError, VerificationError

        try:
            return await asyncio.to_thread(PasswordHasher().verify, hashed_password, plain_password)
        except (InvalidHashError, VerificationError):
            return False

    password_bytes = plain_password.encode('utf-8')[:PASSWORD_BCRYPT_MAX_BYTES]
    try:
        return await asyncio.to_thread(
            bcrypt.checkpw,
            password_bytes,
            hashed_password.encode('utf-8'),
        )
    except ValueError:
        return False
