from pathlib import Path
import csv
import json

root = Path.home() / "BirdNET-Pi" / "model" / "taxonomy-lv"

birds_path = root / "LV_bird_taxonomy.tsv"
families_path = root / "LV_family_reference.tsv"
ebird_path = root / "ebird-taxonomy.json"

preview_path = root / "LV_bird_taxonomy_preview.tsv"
unmatched_path = root / "unmatched_species.tsv"
issues_path = root / "taxonomy_issues.tsv"
overrides_path = root / "taxonomy_overrides.tsv"

def read_tsv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


birds = read_tsv(birds_path)
families = read_tsv(families_path)
overrides = read_tsv(overrides_path)

override_map = {
    row["scientific_name"].strip(): row
    for row in overrides
}



ebird_records = json.loads(
    ebird_path.read_text(encoding="utf-8")
)

family_map = {
    row["family_latin"].strip(): row
    for row in families
}

ebird_map = {}

for row in ebird_records:
    scientific_name = row.get("sciName", "").strip()

    if not scientific_name:
        continue

    current = ebird_map.get(scientific_name)

    if current is None or row.get("category") == "species":
        ebird_map[scientific_name] = row

columns = [
    "scientific_name",
    "latvian_name",
    "family_latin",
    "family_lv",
    "order_latin",
    "order_lv",
    "source_url",
    "reviewed",
]

preview_rows = []
unmatched_rows = []
issue_rows = []
exact_matches = 0
complete_matches = 0

for bird in birds:
    scientific_name = bird["scientific_name"].strip()
    latvian_name = bird["latvian_name"].strip()

    result = {
        "scientific_name": scientific_name,
        "latvian_name": latvian_name,
        "family_latin": "",
        "family_lv": "",
        "order_latin": "",
        "order_lv": "",
        "source_url": "",
        "reviewed": "no",
    }

    override = override_map.get(scientific_name)

    if override:
        ebird_name = override["ebird_scientific_name"].strip()
    else:
        ebird_name = scientific_name

    ebird = ebird_map.get(ebird_name)

    if ebird is None:
        unmatched_rows.append({
            "scientific_name": scientific_name,
            "latvian_name": latvian_name,
            "issue": "No exact eBird scientific-name match",
        })
        preview_rows.append(result)
        continue

    exact_matches += 1

    family_latin = ebird.get("familySciName", "").strip()
    if override and override["latvian_family"].strip():
        family_latin = override["latvian_family"].strip()

    ebird_order = ebird.get("order", "").strip()

    if not family_latin:
        issue_rows.append({
            "scientific_name": scientific_name,
            "issue": "eBird record has no familySciName",
            "value": "",
        })
        preview_rows.append(result)
        continue

    family = family_map.get(family_latin)

    if family is None:
        issue_rows.append({
            "scientific_name": scientific_name,
            "issue": "Family absent from Latvian reference",
            "value": family_latin,
        })
        result["family_latin"] = family_latin
        result["order_latin"] = ebird_order
        preview_rows.append(result)
        continue
    reference_order = family["order_latin"].strip()

    use_latvian_order = (
        override
        and override["resolution_note"].strip().startswith(
            "Use Latvian reference order"
        )
    )

    if (
        ebird_order
        and reference_order != ebird_order
        and not use_latvian_order
    ):
        issue_rows.append({
            "scientific_name": scientific_name,
            "issue": "Order conflict",
            "value": (
                "eBird=" + ebird_order
                + "; Latvian reference=" + reference_order
            ),
        })

    result.update({
        "family_latin": family_latin,
        "family_lv": family["family_lv"].strip(),
        "order_latin": reference_order,
        "order_lv": family["order_lv"].strip(),
        "source_url": family["source_url"].strip(),
        "reviewed": "no",
    })

    complete_matches += 1
    preview_rows.append(result)
with preview_path.open(
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
    writer.writerows(preview_rows)

unmatched_fields = [
    "scientific_name",
    "latvian_name",
    "issue",
]

with unmatched_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=unmatched_fields,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(unmatched_rows)

issue_fields = [
    "scientific_name",
    "issue",
    "value",
]

with issues_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=issue_fields,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(issue_rows)
print("Bird records:", len(birds))
print("Exact eBird matches:", exact_matches)
print("Complete taxonomy matches:", complete_matches)
print("Unmatched species:", len(unmatched_rows))
print("Taxonomy issues:", len(issue_rows))
print("Preview written to:", preview_path)
print("Unmatched report:", unmatched_path)
print("Issues report:", issues_path)
