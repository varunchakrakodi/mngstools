from pathlib import Path
import pandas as pd

input_file = snakemake.input.report
output_file = snakemake.output.filtered
level = str(snakemake.params.level).strip()
threshold = int(snakemake.params.threshold)

rank_map = {
    "S": "species",
    "G": "genus",
    "F": "family",
    "O": "order",
    "C": "class",
    "P": "phylum",
    "D": "domain",
    "K": "kingdom"
}
target_rank = rank_map.get(level.upper(), level.lower())

Path(output_file).parent.mkdir(parents=True, exist_ok=True)

try:
    df = pd.read_csv(input_file, sep="\t")
    required_cols = {"taxRank", "numReads", "numUniqueReads"}
    if not df.empty and required_cols.issubset(df.columns):
        # Filter out any taxa where numReads <= 2 or numUniqueReads <= 2
        # Also respects user-configured Bracken/rank threshold
        filtered_df = df[
            (df["taxRank"].str.lower() == target_rank) &
            (df["numReads"] > 2) &
            (df["numUniqueReads"] > 2) &
            (df["numReads"] >= threshold)
        ].copy()
    else:
        filtered_df = pd.DataFrame(columns=["name", "taxID", "taxRank", "genomeSize", "numReads", "numUniqueReads", "abundance"])
except Exception:
    filtered_df = pd.DataFrame(columns=["name", "taxID", "taxRank", "genomeSize", "numReads", "numUniqueReads", "abundance"])

filtered_df.to_csv(output_file, sep="\t", index=False)