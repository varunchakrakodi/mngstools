import argparse
import csv
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download genomes via ncbi-genome-download, align reads using minimap2/samtools, and generate coverage maps."
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Path to input TSV file"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="Base output folder for reference genome downloads",
    )
    parser.add_argument(
        "-r",
        "--reads",
        required=True,
        help="Path to FASTQ reads (e.g., Sample.microbial.fastq.gz)",
    )
    parser.add_argument(
        "-s",
        "--sample-prefix",
        default="Sample",
        help="Sample prefix for BAM and coverage outputs",
    )
    parser.add_argument(
        "-j",
        "--json-out",
        default=None,
        help="Output path for combined coverage JSON file",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="NCBI API key (falls back to NCBI_API_KEY env var if omitted)",
    )
    parser.add_argument(
        "-t",
        "--threads",
        default="4",
        help="Number of threads for minimap2 and samtools (default: 4)",
    )
    return parser.parse_args()


def extract_taxids(tsv_path):
    """Extracts unique Taxonomy IDs from Column 2 (0-indexed index 1)."""
    tax_ids = set()
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) >= 2:
                val = row[1].strip().replace(",", "")
                # Skip header if present
                if val and not val.lower().startswith("tax") and val.isdigit():
                    tax_ids.add(val)
    return sorted(list(tax_ids))


def download_and_extract(tax_id, output_dir, env):
    final_fna = output_dir / f"{tax_id}.fna"

    if final_fna.exists() and final_fna.stat().st_size > 0:
        print(f"[{tax_id}] Found {final_fna.name}. Skipping download.")
        return final_fna

    temp_download_dir = output_dir / f"tmp_dl_{tax_id}"
    temp_download_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ncbi-genome-download",
        "-s",
        "refseq",
        "-F",
        "fasta",
        "-R",
        "reference",
        "-t",
        tax_id,
        "-o",
        str(temp_download_dir),
        "all",
    ]

    print(f"[{tax_id}] Downloading reference genome...")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[{tax_id}] Download command failed:\n{res.stderr}", file=sys.stderr)
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        return None

    fna_gz_files = list(temp_download_dir.glob("**/*.fna.gz"))
    if not fna_gz_files:
        print(f"[{tax_id}] Warning: No .fna.gz files found for TaxID {tax_id}.", file=sys.stderr)
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        return None

    print(f"[{tax_id}] Extracting into {final_fna.name}...")
    with open(final_fna, "wb") as out_f:
        for gz_path in fna_gz_files:
            with gzip.open(gz_path, "rb") as in_f:
                shutil.copyfileobj(in_f, out_f)

    shutil.rmtree(temp_download_dir, ignore_errors=True)
    return final_fna


def run_alignment_and_coverage(tax_id, fna_path, reads_path, sample_prefix, threads):
    """Aligns reads, checks mapped read count, and generates coverage map."""
    bam_out = Path(f"{sample_prefix}_{tax_id}.bam")
    print(f"[{tax_id}] Aligning reads and sorting BAM -> {bam_out}")

    pipe_cmd = (
        f"minimap2 -t {threads} --split-prefix=tmp{os.getpid()}_{tax_id} -a -xsr "
        f"'{fna_path}' '{reads_path}' | "
        f"samtools view -@ {threads} -bh - | "
        f"samtools sort -@ {threads} -o '{bam_out}' -"
    )

    p1 = subprocess.run(pipe_cmd, shell=True, executable="/bin/bash")
    if p1.returncode != 0:
        print(f"[{tax_id}] Alignment failed.", file=sys.stderr)
        return "ERROR_ALIGNMENT_FAILED"

    # Count mapped reads (exclude unmapped flag 0x4)
    count_cmd = f"samtools view -@ {threads} -c -F 4 '{bam_out}'"
    p_count = subprocess.run(count_cmd, shell=True, executable="/bin/bash", capture_output=True, text=True)
    mapped_count = int(p_count.stdout.strip()) if p_count.returncode == 0 and p_count.stdout.strip().isdigit() else 0

    if mapped_count == 0:
        try:
            bam_out.unlink()
        except OSError:
            pass
        return "NO_MAPPING_READS"

    print(f"[{tax_id}] Generating coverage histogram (-m)...")
    cov_cmd = f"samtools coverage -m '{bam_out}'"
    p2 = subprocess.run(cov_cmd, shell=True, executable="/bin/bash", capture_output=True, text=True)

    try:
        bam_out.unlink()
    except OSError:
        pass

    if p2.returncode != 0 or not p2.stdout.strip():
        return "ERROR_COVERAGE_FAILED"

    return p2.stdout

def execute(input_path, reads_path, downloads_dir, sample_prefix, json_out, api_key=None, threads="4"):
    env = os.environ.copy()
    key = api_key or env.get("NCBI_API_KEY")
    if key:
        env["NCBI_API_KEY"] = key

    out_dir = Path(downloads_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tax_ids = extract_taxids(input_path)
    print(f"Found {len(tax_ids)} unique Taxonomy IDs to process.")

    coverage_map = {}
    for tax_id in tax_ids:
        fna_path = download_and_extract(tax_id, out_dir, env)
        if not fna_path or not fna_path.exists():
            # Explicitly mark download failure
            coverage_map[tax_id] = "REF_NOT_FOUND"
        else:
            status_or_plot = run_alignment_and_coverage(
                tax_id=tax_id,
                fna_path=fna_path,
                reads_path=reads_path,
                sample_prefix=sample_prefix,
                threads=threads,
            )
            coverage_map[tax_id] = status_or_plot

    if json_out:
        Path(json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(coverage_map, f, indent=2)

if "snakemake" in globals():
    # Called directly by Snakemake's `script:` directive
    execute(
        input_path=snakemake.input.comparison,
        reads_path=snakemake.input.microbial_fastq,
        downloads_dir=snakemake.params.downloads_dir,
        sample_prefix=f"{snakemake.params.output_dir}/{snakemake.wildcards.sample}",
        json_out=snakemake.output.coverage_json,
        api_key=snakemake.params.api_key,
        threads=str(snakemake.threads),
    )
elif __name__ == "__main__":
    # Called directly from command line
    args = parse_arguments()
    execute(
        input_path=args.input,
        reads_path=args.reads,
        downloads_dir=args.output,
        sample_prefix=args.sample_prefix,
        json_out=args.json_out,
        api_key=args.api_key,
        threads=args.threads,
    )
