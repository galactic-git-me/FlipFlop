#!/usr/bin/env python3
"""Scrape BscScan address transactions across all pages and filter by date range."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: beautifulsoup4. Install with: pip install beautifulsoup4 requests"
    ) from exc

BASE_URL = "https://bscscan.com"
TXS_PATH = "/txs"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}


def fetch_page(session: requests.Session, address: str, page: int, retries: int = 3) -> str:
    params = {"a": address, "p": page}
    url = f"{BASE_URL}{TXS_PATH}"

    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            if attempt == retries:
                raise RuntimeError(f"Failed to fetch page {page}: {exc}") from exc
            time.sleep(1.5 * attempt)

    raise RuntimeError(f"Failed to fetch page {page}")


def parse_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    marker = soup.find(string=re.compile(r"Page\s+\d+\s+of\s+\d+", re.I))
    if not marker:
        return 1

    match = re.search(r"Page\s+\d+\s+of\s+(\d+)", marker, re.I)
    return int(match.group(1)) if match else 1


def first_link_href(td) -> str:
    a = td.find("a", href=True)
    return a["href"].strip() if a else ""


def first_link_text(td) -> str:
    a = td.find("a")
    if a:
        return " ".join(a.get_text(" ", strip=True).split())
    return " ".join(td.get_text(" ", strip=True).split())


def parse_row(row) -> Optional[Dict[str, str]]:
    tds = row.find_all("td")
    if len(tds) < 8:
        return None

    tx_hash_href = first_link_href(tds[1])
    tx_hash = tx_hash_href.split("/")[-1] if tx_hash_href else first_link_text(tds[1])

    block_text = " ".join(tds[2].get_text(" ", strip=True).split())

    date_td = row.find("td", class_=lambda c: c and "showDate" in c)
    if date_td:
        timestamp_text = " ".join(date_td.get_text(" ", strip=True).split())
    else:
        timestamp_text = ""

    from_addr = first_link_text(tds[5])
    from_href = first_link_href(tds[5])

    # The "to" column can include method tags and labels; pick last address-like link if present.
    to_links = tds[7].find_all("a", href=True)
    to_href = ""
    to_addr = ""
    if to_links:
        for link in reversed(to_links):
            href = link.get("href", "")
            if "/address/" in href:
                to_href = href
                to_addr = " ".join(link.get_text(" ", strip=True).split())
                break
        if not to_addr:
            to_href = to_links[-1].get("href", "")
            to_addr = " ".join(to_links[-1].get_text(" ", strip=True).split())
    else:
        to_addr = " ".join(tds[7].get_text(" ", strip=True).split())

    value_text = " ".join(tds[8].get_text(" ", strip=True).split()) if len(tds) > 8 else ""
    fee_text = " ".join(tds[9].get_text(" ", strip=True).split()) if len(tds) > 9 else ""

    return {
        "tx_hash": tx_hash,
        "tx_url": urljoin(BASE_URL, tx_hash_href) if tx_hash_href else "",
        "block": block_text,
        "datetime_utc": timestamp_text,
        "from": from_addr,
        "from_url": urljoin(BASE_URL, from_href) if from_href else "",
        "to": to_addr,
        "to_url": urljoin(BASE_URL, to_href) if to_href else "",
        "value": value_text,
        "txn_fee": fee_text,
    }


def parse_transactions(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    transactions: List[Dict[str, str]] = []
    for row in table.find_all("tr"):
        parsed = parse_row(row)
        if parsed:
            transactions.append(parsed)
    return transactions


def in_range(ts: str, start: datetime, end: datetime) -> bool:
    if not ts:
        return False
    try:
        dt = datetime.strptime(ts, DATE_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return start <= dt <= end


def write_csv(rows: List[Dict[str, str]], outfile: str) -> None:
    if not rows:
        headers = [
            "tx_hash",
            "tx_url",
            "block",
            "datetime_utc",
            "from",
            "from_url",
            "to",
            "to_url",
            "value",
            "txn_fee",
        ]
    else:
        headers = list(rows[0].keys())

    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape BscScan transactions for an address and filter by date range."
    )
    parser.add_argument(
        "--address",
        default="0x128C33C16EE6D337154D0996220A791d89Aa0442",
        help="BSC wallet/contract address",
    )
    parser.add_argument(
        "--start",
        default="2021-01-01",
        help="Start date (UTC), format YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="End date (UTC), format YYYY-MM-DD",
    )
    parser.add_argument(
        "--csv",
        default="bscscan_transactions_2021_to_today.csv",
        help="Output CSV filename",
    )
    parser.add_argument(
        "--json",
        default="bscscan_transactions_2021_to_today.json",
        help="Output JSON filename",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.4,
        help="Delay in seconds between page requests",
    )

    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )

    if end_dt < start_dt:
        print("Error: --end must be >= --start", file=sys.stderr)
        return 1

    session = requests.Session()

    first_html = fetch_page(session, args.address, 1)
    total_pages = parse_total_pages(first_html)

    all_rows: List[Dict[str, str]] = []

    for page in range(1, total_pages + 1):
        html = first_html if page == 1 else fetch_page(session, args.address, page)
        rows = parse_transactions(html)

        if not rows:
            continue

        filtered = [r for r in rows if in_range(r["datetime_utc"], start_dt, end_dt)]
        all_rows.extend(filtered)

        print(f"Page {page}/{total_pages}: parsed {len(rows)}, kept {len(filtered)}")
        if args.sleep > 0:
            time.sleep(args.sleep)

    write_csv(all_rows, args.csv)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2)

    print(f"\\nSaved {len(all_rows)} transactions")
    print(f"CSV:  {args.csv}")
    print(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
