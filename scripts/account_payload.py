#!/usr/bin/env python3
"""Create and decrypt sealed account payloads for the account management workflow."""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import json
import os
import re
import stat
import sys
from pathlib import Path

try:
    from nacl.public import PrivateKey, PublicKey, SealedBox
except ModuleNotFoundError as exc:
    if exc.name == "nacl":
        raise SystemExit(
            "缺少 PyNaCl。请使用 `uv run --with PyNaCl python "
            "scripts/account_payload.py ...` 运行此工具，或在 .venv 中安装 PyNaCl。"
        ) from exc
    raise


ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def encode_key(raw_key: bytes) -> str:
    return base64.urlsafe_b64encode(raw_key).decode("ascii").rstrip("=")


def decode_key(raw_key: str) -> bytes:
    try:
        value = raw_key.strip()
        return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("密钥不是有效的 Base64 内容") from exc


def validate_text(name: str, value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} 必须是文本")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} 不能为空")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} 不能包含换行")
    return value if name == "password" else value.strip()


def validate_account_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("解密后的账号资料格式错误")
    if payload.get("version") != 1:
        raise ValueError("账号资料版本不受支持")

    account_id = validate_text("account_id", payload.get("account_id", ""))
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ValueError("account_id 只能包含字母、数字、下划线和短横线")
    return {
        "version": 1,
        "account_id": account_id,
        "username": validate_text("username", payload.get("username", "")),
        "password": validate_text("password", payload.get("password", "")),
        "course_id": validate_text("course_id", payload.get("course_id", "")),
        "clazz_id": validate_text(
            "clazz_id", payload.get("clazz_id", ""), allow_empty=True
        ),
    }


def decrypt_payload(raw_payload: str, raw_private_key: str) -> dict:
    try:
        encrypted = decode_key(raw_payload)
        private_key = PrivateKey(decode_key(raw_private_key))
        decrypted = SealedBox(private_key).decrypt(encrypted)
        payload = json.loads(decrypted.decode("utf-8"))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("账号密文无法解密或格式无效") from exc
    except Exception as exc:
        raise ValueError("账号密文无法使用当前私钥解密") from exc
    return validate_account_payload(payload)


def prompt_value(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def generate_key(private_path: Path, public_path: Path) -> None:
    if private_path.exists() or public_path.exists():
        raise ValueError("密钥文件已存在；如需重新生成请先手动移走旧文件")
    private_key = PrivateKey.generate()
    private_path.write_text(encode_key(bytes(private_key)), encoding="ascii")
    public_path.write_text(
        encode_key(bytes(private_key.public_key)),
        encoding="ascii",
    )
    private_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"已生成私钥文件: {private_path}")
    print(f"已生成公钥文件: {public_path}")
    print("请将私钥文件内容保存为 GitHub Secret: SUPERSTAR_ACCOUNT_PRIVATE_KEY")
    print("私钥不要提交到仓库；公钥只用于本地生成密文")


def encrypt_account(public_path: Path, args: argparse.Namespace) -> None:
    public_key = PublicKey(decode_key(public_path.read_text(encoding="ascii")))
    account_id = args.account_id or prompt_value("账号别名")
    username = args.username or prompt_value("用户名")
    password = getpass.getpass("密码: ")
    course_id = args.course_id or prompt_value("课程 ID")
    clazz_id = args.clazz_id if args.clazz_id is not None else prompt_value("班级 ID（可留空）")
    payload = validate_account_payload(
        {
            "version": 1,
            "account_id": account_id,
            "username": username,
            "password": password,
            "course_id": course_id,
            "clazz_id": clazz_id,
        }
    )
    encrypted = SealedBox(public_key).encrypt(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    print("请复制下面这一整行到 Manage Superstar account Workflow 的 encrypted_payload：")
    print(base64.urlsafe_b64encode(encrypted).decode("ascii").rstrip("="))


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate-key")
    generate.add_argument("--private-key-file", type=Path, default=Path("superstar-account-private-key.txt"))
    generate.add_argument("--public-key-file", type=Path, default=Path("superstar-account-public-key.txt"))

    encrypt = subparsers.add_parser("encrypt")
    encrypt.add_argument("--public-key-file", type=Path, default=Path("superstar-account-public-key.txt"))
    encrypt.add_argument("--account-id")
    encrypt.add_argument("--username")
    encrypt.add_argument("--course-id")
    encrypt.add_argument("--clazz-id", default=None)
    args = parser.parse_args()

    try:
        if args.command == "generate-key":
            generate_key(args.private_key_file, args.public_key_file)
        else:
            encrypt_account(args.public_key_file, args)
    except (OSError, ValueError, EOFError) as exc:
        print(f"账号密文工具失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
