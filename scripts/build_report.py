#!/usr/bin/env python3
"""Inject Amazon purchase analysis JSON into the HTML report template."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime


HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "report_template.html")


def render_report(analysis: dict, output_path: str | None = None) -> str:
    if output_path is None:
        output_path = os.path.expanduser("~/Desktop/amazon-purchase-report.html")
    analysis = dict(analysis)
    analysis.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
    with open(TEMPLATE, "r", encoding="utf-8") as handle:
        template = handle.read()
    blob = json.dumps(analysis, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("__REPORT_DATA__", blob)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return output_path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("Usage: build_report.py <analysis.json> [output.html]")
        return 0
    analysis_path = argv[0]
    output_path = argv[1] if len(argv) > 1 else None
    with open(analysis_path, "r", encoding="utf-8") as handle:
        analysis = json.load(handle)
    path = render_report(analysis, output_path)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
