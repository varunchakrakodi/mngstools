from itertools import combinations
from pathlib import Path
import re
import pandas as pd

OUTPUT_METRICS = snakemake.output.metrics
OUTPUT_BETA = snakemake.output.beta

Path(OUTPUT_METRICS).parent.mkdir(parents=True, exist_ok=True)
Path(OUTPUT_BETA).parent.mkdir(parents=True, exist_ok=True)


def sample_from_path(path, prefix="", suffix=""):
    name = Path(path).name
    if prefix and name.startswith(prefix):
        name = name[len(prefix):]
    if suffix and name.endswith(suffix):
        name = name[:-len(suffix)]
    return name


def seqkit_stats(path):
    df = pd.read_csv(path, sep="\t")
    if df.empty:
        return {"num_seqs": 0, "sum_len": 0, "avg_len": 0, "min_len": 0, "max_len": 0, "Q20": 0, "Q30": 0}
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
    classified, unclassified = 0, 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                continue
            status = fields[0].strip()
            if status == "C":
                classified += 1
            elif status == "U":
                unclassified += 1
    return classified, unclassified


def bracken_abundance(path):
    try:
        df = pd.read_csv(path, sep="\t")
    except Exception:
        return pd.Series(dtype=float)
    name_col = next((c for c in ("name", "taxonomy_name") if c in df.columns), None)
    count_col = next((c for c in ("new_est_reads", "est_reads", "added_reads") if c in df.columns), None)
    if not name_col or not count_col or df.empty:
        return pd.Series(dtype=float)
    names = df[name_col].astype(str)
    counts = pd.to_numeric(df[count_col], errors="coerce").fillna(0.0)
    counts.index = names
    return counts.groupby(level=0).sum().sort_values(ascending=False)


def centrifuge_total_reads(path):
    try:
        df = pd.read_csv(path, sep="\t")
        if "numReads" in df.columns:
            return float(df["numReads"].sum())
    except Exception:
        pass
    return 0.0


def read_alpha(path):
    results = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                match = re.search(r"([^:=]+)[:=]\s*([-+0-9.eE]+)", line)
                if match:
                    # Clean up names e.g., "Shannon's alpha", "Berger-Parker", "Fisher's Alpha"
                    key = match.group(1).strip()
                    key = re.sub(r"['\"]", "", key)
                    key = re.sub(r"[\s\-\.]+", "_", key)
                    results[key] = float(match.group(2))
    except Exception:
        pass
    return results


def bray_curtis(first, second):
    taxa = first.index.union(second.index)
    x = first.reindex(taxa, fill_value=0).astype(float)
    y = second.reindex(taxa, fill_value=0).astype(float)
    denominator = x.sum() + y.sum()
    return float((x - y).abs().sum() / denominator) if denominator > 0 else 0.0


raw_by_sample = {sample_from_path(p, suffix=".raw.seqkit.tsv"): p for p in snakemake.input.raw}
trimmed_by_sample = {sample_from_path(p, suffix=".trimmed.seqkit.tsv"): p for p in snakemake.input.trimmed}
microbial_by_sample = {sample_from_path(p, suffix=".microbial.seqkit.tsv"): p for p in snakemake.input.microbial}
kraken_by_sample = {sample_from_path(p, suffix=".kraken2"): p for p in snakemake.input.kraken}
bracken_by_sample = {sample_from_path(p, suffix=".bracken"): p for p in snakemake.input.bracken}
centrifuge_by_sample = {sample_from_path(p, prefix="filtered_", suffix=".tsv"): p for p in snakemake.input.centrifuge_filtered}
alpha_by_sample = {sample_from_path(p, suffix=".alpha.txt"): p for p in snakemake.input.alpha}

samples = sorted(bracken_by_sample)
rows = []
abundances = {}

for sample in samples:
    raw = seqkit_stats(raw_by_sample[sample])
    trimmed = seqkit_stats(trimmed_by_sample[sample])
    microbial = seqkit_stats(microbial_by_sample[sample])
    classified, unclassified = kraken_read_counts(kraken_by_sample[sample])
    abundance = bracken_abundance(bracken_by_sample[sample])
    cent_reads = centrifuge_total_reads(centrifuge_by_sample.get(sample, ""))
    alpha = read_alpha(alpha_by_sample.get(sample, ""))

    abundances[sample] = abundance

    row = {
        "sample": sample,
        "kraken_classified_reads": classified,
        "kraken_unclassified_reads": unclassified,
        "bracken_estimated_reads": float(abundance.sum()),
        "centrifuge_estimated_reads": cent_reads,
    }

    for stage, values in (("raw", raw), ("trimmed", trimmed), ("microbial", microbial)):
        for key, value in values.items():
            row[f"{stage}_{key}"] = value

    for index, value in alpha.items():
        row[f"alpha_{index}"] = value

    rows.append(row)

pd.DataFrame(rows).to_csv(OUTPUT_METRICS, sep="\t", index=False)

beta_rows = []
for first, second in combinations(samples, 2):
    beta_rows.append({
        "sample_a": first,
        "sample_b": second,
        "bray_curtis": bray_curtis(abundances[first], abundances[second]),
    })

for sample in samples:
    beta_rows.append({"sample_a": sample, "sample_b": sample, "bray_curtis": 0.0})

pd.DataFrame(beta_rows, columns=["sample_a", "sample_b", "bray_curtis"]).to_csv(OUTPUT_BETA, sep="\t", index=False)
