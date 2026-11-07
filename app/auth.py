"""Đăng nhập đơn giản bằng mật khẩu (băm PBKDF2).

Lưu ý: PRD yêu cầu xác thực 2 lớp cho chủ tài khoản và quản trị – chưa làm ở bản prototype này.
"""
import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex() + "$" + h.hex()


def check_password(password: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
    return hmac.compare_digest(h.hex(), h_hex)
