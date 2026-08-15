from itertools import combinations
from pathlib import Path
import re

import pandas as pd


OUTPUT_METRICS = snakemake.output.metrics
OUTPUT_BETA = snakemake.output.beta

Path(OUTPUT_METRICS).parent.mkdir(parents=True, exist_ok=True)
Path(OUTPUT_BETA).parent.mkdir(parents=True, exist_ok=True)


def sample_from_path(path, suffix):
    name = Path(path).name
    if not name.endswith(suffix):
        raise ValueError(f"Unexpected filename: {path}; expected suffix {suffix}")
    return name[: -len(suffix)]


def seqkit_stats(path):
    df = pd.read_csv(path, sep="\t")
    if df.empty:
        raise ValueError(f"Seqkit stats file is empty: {path}")

    row = df.iloc[0]

    def get_value(*names):
        for name in names:
            if name in df.columns:
                return row[name]
        return ""

    return {
        "num_seqs": get_value("num_seqs"),
        "sum_len": get_value("sum_len"),
        "avg_len": get_value("avg_len"),
        "min_len": get_value("min_len"),
        "max_len": get_value("max_len"),
        "Q20": get_value("Q20(%)"),
        "Q30": get_value("Q30(%)"),
    }


def kraken_read_counts(path):
    classified = 0
    unclassified = 0

    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                continue

            status = fields[0].strip()
            if status not in {"C", "U"}:
                continue

            if status == "C":
                classified += 1
            else:
                unclassified += 1

    return classified, unclassified


def bracken_abundance(path):
    df = pd.read_csv(path, sep="\t")

    name_col = next(
        (column for column in ("name", "taxonomy_name") if column in df.columns),
        None,
    )
    count_col = next(
        (
            column
            for column in ("new_est_reads", "est_reads", "added_reads")
            if column in df.columns
        ),
        None,
    )

    if name_col is None:
        raise ValueError(f"Could not find taxon-name column in Bracken file: {path}")
    if count_col is None:
        raise ValueError(f"Could not find abundance column in Bracken file: {path}")

    names = df[name_col].astype(str)
    counts = pd.to_numeric(df[count_col], errors="coerce").fillna(0.0)
    counts.index = names

    return counts.groupby(level=0).sum().sort_values(ascending=False)


def read_alpha(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    patterns = [
        r"Shannon(?:'s)?\s+alpha\s*[:=]\s*([-+0-9.eE]+)",
        r"Shannon\s*[:=]\s*([-+0-9.eE]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return {"Sh": float(match.group(1))}

    numbers = re.findall(
        r"[-+]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][-+]?\d+)?",
        text,
    )
    if numbers:
        return {"Sh": float(numbers[-1])}

    raise ValueError(
        f"Could not parse Shannon alpha diversity from {path}. "
        f"KrakenTools output was:\n{text}"
    )


def bray_curtis(first, second):
    taxa = first.index.union(second.index)
    x = first.reindex(taxa, fill_value=0).astype(float)
    y = second.reindex(taxa, fill_value=0).astype(float)
    denominator = x.sum() + y.sum()

    if denominator == 0:
        return 0.0

    return float((x - y).abs().sum() / denominator)


raw_by_sample = {
    sample_from_path(path, ".seqkit.tsv"): path
    for path in snakemake.input.raw
}
trimmed_by_sample = {
    sample_from_path(path, ".seqkit.tsv"): path
    for path in snakemake.input.trimmed
}
microbial_by_sample = {
    sample_from_path(path, ".seqkit.tsv"): path
    for path in snakemake.input.microbial
}
kraken_by_sample = {
    sample_from_path(path, ".kraken2"): path
    for path in snakemake.input.kraken
}
bracken_by_sample = {
    sample_from_path(path, ".bracken"): path
    for path in snakemake.input.bracken
}
alpha_by_sample = {
    sample_from_path(path, ".alpha.txt"): path
    for path in snakemake.input.alpha
}

samples = sorted(bracken_by_sample)
rows = []
abundances = {}

for sample in samples:
    raw = seqkit_stats(raw_by_sample[sample])
    trimmed = seqkit_stats(trimmed_by_sample[sample])
    microbial = seqkit_stats(microbial_by_sample[sample])
    classified, unclassified = kraken_read_counts(kraken_by_sample[sample])
    abundance = bracken_abundance(bracken_by_sample[sample])
    alpha = read_alpha(alpha_by_sample[sample])

    abundances[sample] = abundance

    row = {
        "sample": sample,
        "kraken_classified_reads": classified,
        "kraken_unclassified_reads": unclassified,
        "bracken_estimated_reads": float(abundance.sum()),
    }

    for stage, values in (
        ("raw", raw),
        ("trimmed", trimmed),
        ("microbial", microbial),
    ):
        for key, value in values.items():
            row[f"{stage}_{key}"] = value

    for index, value in alpha.items():
        row[f"alpha_{index}"] = value

    rows.append(row)

pd.DataFrame(rows).to_csv(OUTPUT_METRICS, sep="\t", index=False)

beta_rows = []
for first, second in combinations(samples, 2):
    beta_rows.append(
        {
            "sample_a": first,
            "sample_b": second,
            "bray_curtis": bray_curtis(
                abundances[first],
                abundances[second],
            ),
        }
    )

for sample in samples:
    beta_rows.append(
        {
            "sample_a": sample,
            "sample_b": sample,
            "bray_curtis": 0.0,
        }
    )

pd.DataFrame(
    beta_rows,
    columns=["sample_a", "sample_b", "bray_curtis"],
).to_csv(OUTPUT_BETA, sep="\t", index=False)