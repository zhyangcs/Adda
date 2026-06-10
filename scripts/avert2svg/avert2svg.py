#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import base64
import re
from pathlib import Path


DATA_URI_RE = re.compile(
    r"data:image/svg\+xml;base64,([A-Za-z0-9+/=\s\r\n]+)",
    re.IGNORECASE
)

def extract_base64(payload: str) -> str:
    """
    从文本中提取 base64 内容。
    优先提取 data:image/svg+xml;base64, 后面的部分；
    如果找不到，就把整个文本当作 base64（并去掉空白）。
    """
    m = DATA_URI_RE.search(payload)
    if m:
        b64 = m.group(1)
    else:
        b64 = payload

    # 去掉所有空白（换行/空格/tab），避免解码报错
    b64 = re.sub(r"\s+", "", b64)

    # 一些文本末尾可能有引号/分号等非 base64 字符，简单裁剪一下
    b64 = re.sub(r"[^A-Za-z0-9+/=].*$", "", b64)

    if not b64:
        raise ValueError("没有提取到 base64 内容。请检查输入 txt 格式。")

    return b64


def decode_svg_bytes(b64: str) -> bytes:
    try:
        return base64.b64decode(b64, validate=True)
    except Exception:
        # 有些 base64 可能不严格（缺 padding），尝试补齐
        pad = (-len(b64)) % 4
        b64_padded = b64 + ("=" * pad)
        return base64.b64decode(b64_padded)


def main():
    ap = argparse.ArgumentParser(
        description="Convert data:image/svg+xml;base64,... in a txt file to an .svg file."
    )
    ap.add_argument("input_txt", help="输入 txt 路径（包含 data:image/svg+xml;base64,... 或纯 base64）")
    ap.add_argument("-o", "--output", help="输出 svg 路径（默认：与输入同名.svg）")
    args = ap.parse_args()

    in_path = Path(args.input_txt)
    if not in_path.exists():
        raise FileNotFoundError(f"找不到输入文件：{in_path}")

    text = in_path.read_text(encoding="utf-8", errors="ignore")

    b64 = extract_base64(text)
    svg_bytes = decode_svg_bytes(b64)

    out_path = Path(args.output) if args.output else in_path.with_suffix(".svg")

    # 尝试按 UTF-8 写出（svg 通常是文本）；若失败就按二进制写
    try:
        svg_text = svg_bytes.decode("utf-8")
        out_path.write_text(svg_text, encoding="utf-8")
    except UnicodeDecodeError:
        out_path.write_bytes(svg_bytes)

    print(f"✅ 已生成：{out_path.resolve()}")


if __name__ == "__main__":
    main()
