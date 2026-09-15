import re
from pathlib import Path
import pandas as pd

bracken_path = snakemake.input.bracken
centrifuge_path = snakemake.input.centrifuge
output_path = snakemake.output.comparison
level = str(snakemake.params.level).strip().upper()

rank_name = "Species" if level == "S" else ("Genus" if level == "G" else f"Taxon ({level})")

def clean_tax_id(val):
    if pd.isna(val):
        return ""
    # Remove commas, decimals, and spaces
    cleaned = re.sub(r"[,\s]", "", str(val).strip())
    if "." in cleaned:
        cleaned = cleaned.split(".")[0]
    return cleaned

bracken_taxa = {}
try:
    df_b = pd.read_csv(bracken_path, sep="\t")
    tax_col = next((c for c in ("taxonomy_id", "tax_id", "taxID") if c in df_b.columns), None)
    name_col = next((c for c in ("name", "taxonomy_name") if c in df_b.columns), None)
    if tax_col and name_col:
        for _, row in df_b.iterrows():
            tid = clean_tax_id(row[tax_col])
            if tid:
                bracken_taxa[tid] = str(row[name_col]).strip()
except Exception:
    pass

centrifuge_taxa = {}
try:
    df_c = pd.read_csv(centrifuge_path, sep="\t")
    tax_col_c = next((c for c in ("taxID", "taxonomy_id", "tax_id") if c in df_c.columns), None)
    name_col_c = next((c for c in ("name", "taxonomy_name") if c in df_c.columns), None)
    if tax_col_c and name_col_c:
        for _, row in df_c.iterrows():
            tid = clean_tax_id(row[tax_col_c])
            if tid:
                centrifuge_taxa[tid] = str(row[name_col_c]).strip()
except Exception:
    pass

all_tax_ids = sorted(
    set(bracken_taxa.keys()).union(set(centrifuge_taxa.keys())),
    key=lambda x: int(x) if x.isdigit() else x
)

rows = []
for idx, tid in enumerate(all_tax_ids, start=1):
    in_bracken = tid in bracken_taxa
    in_centrifuge = tid in centrifuge_taxa
    name = bracken_taxa.get(tid) or centrifuge_taxa.get(tid, "")

    rows.append({
        "Sl. No": idx,
        "Taxonomy ID": str(tid),
        "NCBI Taxonomy Browser": f"https://www.ncbi.nlm.nih.gov/datasets/taxonomy/browser/?taxon={tid}",
        rank_name: name,
        "Identified by both": "Yes" if (in_bracken and in_centrifuge) else "No",
        "Identified by Bracken only": "Yes" if (in_bracken and not in_centrifuge) else "No",
        "Identified by Centrifuge only": "Yes" if (in_centrifuge and not in_bracken) else "No"
    })

Path(output_path).parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(output_path, sep="\t", index=False)