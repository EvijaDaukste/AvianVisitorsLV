#!/usr/bin/env python3
"""Render the Līču Putni 4K collage and display it on Samsung The Frame."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


TV_HOST = "192.168.88.15"
TV_PORT = 8002
TV_NAME = "AvianVisitors"

FRAME_DIR = Path("/home/birdnet/BirdNET-Pi/frame")
TOKEN_FILE = FRAME_DIR / "samsung-data/token.txt"
CONTENT_ID_FILE = FRAME_DIR / "samsung-data/latest-content-id.txt"
LOG_DIR = FRAME_DIR / "logs"

IMAGE_FILE = Path("/home/birdnet/bird-frame-tv/licu-putni-4k.png")
SHOOT_SCRIPT = FRAME_DIR / "shoot.py"
RENDER_PYTHON = Path("/home/birdnet/BirdNET-Pi/birdnet/bin/python")

SCRIPT_FILE = Path(__file__).resolve()
SAMSUNG_PYTHON = Path(sys.executable)

RENDER_TIMEOUT = 240
UPLOAD_TIMEOUT = 180
VERIFY_TIMEOUT = 60
SELECT_TIMEOUT = 60


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    line = f"[{timestamp()}] {message}"
    print(line, flush=True)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "samsung-frame-update.log"

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def samsung_connection():
    import samsungtvws.connection as connection

    connection.IGNORE_EVENTS_AT_STARTUP = (
        connection.IGNORE_EVENTS_AT_STARTUP
        + ("ms.remote.touchEnable", "ms.remote.touchDisable")
    )

    from samsungtvws import SamsungTVWS

    return SamsungTVWS(
        host=TV_HOST,
        port=TV_PORT,
        token_file=str(TOKEN_FILE),
        name=TV_NAME,
        timeout=30,
    )


def stage_upload() -> int:
    if not IMAGE_FILE.is_file():
        print(f"ERROR=Image not found: {IMAGE_FILE}")
        return 1

    tv = samsung_connection()
    art = tv.art()

    try:
        content_id = art.upload(
            IMAGE_FILE.read_bytes(),
            file_type="png",
        )
        print(f"CONTENT_ID={content_id}")
        return 0
    finally:
        art.close()


def stage_verify(content_id: str) -> int:
    tv = samsung_connection()
    art = tv.art()

    try:
        matches = [
            item
            for item in art.available()
            if str(item.get("content_id")) == content_id
        ]

        if not matches:
            print(f"ERROR=Artwork not found: {content_id}")
            return 1

        item = matches[0]

        print(f"CONTENT_ID={content_id}")
        print(f"CATEGORY={item.get('category_id', '')}")
        print(f"WIDTH={item.get('width', '')}")
        print(f"HEIGHT={item.get('height', '')}")
        print(f"CONTENT_TYPE={item.get('content_type', '')}")
        print("METADATA=" + json.dumps(item, ensure_ascii=False))

        if int(item.get("width", 0)) != 3840:
            print("ERROR=Uploaded artwork width is not 3840")
            return 1

        if int(item.get("height", 0)) != 2160:
            print("ERROR=Uploaded artwork height is not 2160")
            return 1

        return 0
    finally:
        art.close()


def stage_select(content_id: str, category: str) -> int:
    tv = samsung_connection()
    art = tv.art()

    try:
        art.select_image(
            content_id,
            category=category,
            show=True,
        )
        print(f"SELECTED={content_id}")
        return 0
    finally:
        art.close()


def run_stage(
    stage: str,
    timeout_seconds: int,
    *extra_args: str,
) -> str:
    command = [
        str(SAMSUNG_PYTHON),
        str(SCRIPT_FILE),
        "--stage",
        stage,
        *extra_args,
    ]

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )

    if result.stdout:
        print(result.stdout, end="", flush=True)

    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Stage {stage!r} failed with exit code {result.returncode}"
        )

    return result.stdout


def value_from_output(output: str, key: str) -> str:
    prefix = key + "="

    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()

    raise RuntimeError(f"{key} was not returned")


def render_image() -> None:
    command = [
        str(RENDER_PYTHON),
        str(SHOOT_SCRIPT),
        "http://localhost",
        "--out",
        "Līču Putni",
        "--subtitle",
        "--width",
        "--height",
        "--dsf",
        "--mat",
        "--collage-vh",
        "--cluster-xbias",
        "--cluster-ybias",
        "1.0",
    ]
    log("Rendering approved 4K washi collage")

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="", flush=True)

    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Rendering failed with exit code {result.returncode}"
        )

    if not IMAGE_FILE.is_file():
        raise RuntimeError(f"Rendered image was not created: {IMAGE_FILE}")

    log(
        f"Rendered image ready: {IMAGE_FILE} "
        f"({IMAGE_FILE.stat().st_size} bytes)"
    )


def run_full_update() -> int:
    if not TOKEN_FILE.is_file() or TOKEN_FILE.stat().st_size == 0:
        raise RuntimeError(f"Samsung token is missing: {TOKEN_FILE}")

    render_image()

    log("Uploading image to Samsung artwork library")
    upload_output = run_stage("upload", UPLOAD_TIMEOUT)
    content_id = value_from_output(upload_output, "CONTENT_ID")
    log(f"Samsung returned content ID: {content_id}")

    log(f"Verifying uploaded artwork: {content_id}")
    verify_output = run_stage(
        "verify",
        VERIFY_TIMEOUT,
        "--content-id",
        content_id,
    )

    category = value_from_output(verify_output, "CATEGORY")
    width = value_from_output(verify_output, "WIDTH")
    height = value_from_output(verify_output, "HEIGHT")

    if not category:
        raise RuntimeError("Samsung artwork category was empty")

    log(
        f"Artwork verified: {content_id}, "
        f"category {category}, {width}x{height}"
    )

    log(f"Selecting artwork on TV: {content_id}")
    run_stage(
        "select",
        SELECT_TIMEOUT,
        "--content-id",
        content_id,
        "--category",
        category,
    )

    CONTENT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_ID_FILE.write_text(content_id + "\n", encoding="utf-8")

    log(f"Samsung Frame update completed successfully: {content_id}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render and display the AvianVisitors collage on Samsung The Frame"
    )

    parser.add_argument(
        "--stage",
        choices=("upload", "verify", "select"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--content-id", help=argparse.SUPPRESS)
    parser.add_argument("--category", help=argparse.SUPPRESS)

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.stage == "upload":
        return stage_upload()

    if args.stage == "verify":
        if not args.content_id:
            print("ERROR=Missing --content-id")
            return 2
        return stage_verify(args.content_id)

    if args.stage == "select":
        if not args.content_id or not args.category:
            print("ERROR=Missing --content-id or --category")
            return 2
        return stage_select(args.content_id, args.category)

    try:
        return run_full_update()
    except subprocess.TimeoutExpired as exc:
        log(f"ERROR: Stage timed out after {exc.timeout} seconds")
        return 1
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
