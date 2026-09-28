from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
import csv
import re

root = Path.home() / "BirdNET-Pi" / "model" / "taxonomy-lv"

source = root / "latvijasdaba-aves-source.html"
preview = root / "LV_family_reference_preview.tsv"

base_url = "https://www.latvijasdaba.lv"


def direct_text_after_link(link):
    parts = []

    for item in link.next_siblings:
        if isinstance(item, Tag) and item.name == "ul":
            break

        if isinstance(item, NavigableString):
            parts.append(str(item))

    return " ".join(parts).strip()


def latin_name(text):
    match = re.search(r"\(([A-Z][A-Za-z]+)\)", text)

    if match:
        return match.group(1)

    return ""


html = source.read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")

records = {}

for order_item in soup.find_all("li"):
    order_link = order_item.find("a", recursive=False)
    family_list = order_item.find("ul", recursive=False)

    if order_link is None or family_list is None:
        continue

    order_lv = order_link.get_text(" ", strip=True)
    order_latin = latin_name(direct_text_after_link(order_link))

    if not order_latin:
        continue

    for family_item in family_list.find_all("li", recursive=False):
        family_link = family_item.find("a", recursive=False)

        if family_link is None:
            continue

        family_lv = family_link.get_text(" ", strip=True)
        family_latin = latin_name(direct_text_after_link(family_link))

        if not family_latin:
            continue

        href = family_link.get("href", "").strip()

        if href.startswith("/"):
            source_url = base_url + href
        else:
            source_url = href

        records[family_latin] = {
            "family_latin": family_latin,
            "family_lv": family_lv,
            "order_latin": order_latin,
            "order_lv": order_lv,
            "source_url": source_url,
            "reviewed": "no",
        }

columns = [
    "family_latin",
    "family_lv",
    "order_latin",
    "order_lv",
    "source_url",
    "reviewed",
]

with preview.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=columns,
        delimiter="\t",
        lineterminator="\n",
    )

    writer.writeheader()

    for family_latin in sorted(records):
        writer.writerow(records[family_latin])

orders = {
    record["order_latin"]
    for record in records.values()
}

print("Preview written to:", preview)
print("Families parsed:", len(records))
print("Orders parsed:", len(orders))
