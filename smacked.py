import os

configfile: "config.yaml"

reference = config["reference"]
fastq_dir = config["fastq_dir"]
output_dir = config["output_dir"]
kraken_db = config["kraken_db"]
bracken_db = config.get("bracken_db", kraken_db)
centrifuge_db = config.get("centrifuge_db", "")
centrifuge_min_hitlen = config.get("centrifuge_min_hitlen", 22)
kraken_confidence = config.get("kraken_confidence", 0.03)
bracken_level = config.get("bracken_level", "S")
bracken_threshold = config.get("bracken_threshold", 2)

# Unified thread allocation from config.yaml
DEFAULT_THREADS = config.get("threads", 16)

# Optional cleanup toggle
CLEAN_INTERMEDIATES = config.get("clean_intermediates", False)

SAMPLES = glob_wildcards(f"{fastq_dir}/{{sample}}.fastq.gz").sample

rule all:
    input:
        f"{output_dir}/.cleaned" if CLEAN_INTERMEDIATES else f"{output_dir}/Results.html"

rule trim_reads:
    input:
        fastq=f"{fastq_dir}/{{sample}}.fastq.gz"
    output:
        trimmed=f"{output_dir}/{{sample}}.trimmed.fastq.gz"
    threads: DEFAULT_THREADS
    shell:
        r"""
        mkdir -p "{output_dir}"
        pigz -dc "{input.fastq}" | chopper -q 10 -l 100 | pigz -p {threads} > "{output.trimmed}"
        """

rule seqkit_stats_raw:
    input:
        fastq=f"{fastq_dir}/{{sample}}.fastq.gz"
    output:
        stats=f"{output_dir}/{{sample}}.raw.seqkit.tsv"
    threads: DEFAULT_THREADS
    shell:
        r"""
        mkdir -p "{output_dir}"
        seqkit stats -a -T -j {threads} "{input.fastq}" > "{output.stats}"
        """

rule map_to_human:
    input:
        reads=f"{output_dir}/{{sample}}.trimmed.fastq.gz"
    output:
        bam=f"{output_dir}/{{sample}}.bam"
    threads: DEFAULT_THREADS
    params:
        split_prefix=lambda wildcards: f"{output_dir}/{wildcards.sample}.tmp."
    shell:
        r"""
        mkdir -p "{output_dir}"
        minimap2 --split-prefix="{params.split_prefix}" -a -x sr "{reference}" "{input.reads}" -t {threads} | samtools view -@ {threads} -bh | samtools sort -@ {threads} -o "{output.bam}"
        samtools index -@ {threads} "{output.bam}"
        """

rule seqkit_stats_trimmed:
    input:
        fastq=f"{output_dir}/{{sample}}.trimmed.fastq.gz"
    output:
        stats=f"{output_dir}/{{sample}}.trimmed.seqkit.tsv"
    threads: DEFAULT_THREADS
    shell:
        r"""
        mkdir -p "{output_dir}"
        seqkit stats -a -T -j {threads} "{input.fastq}" > "{output.stats}"
        """

rule extract_microbial_reads:
    input:
        bam=f"{output_dir}/{{sample}}.bam"
    output:
        reads=f"{output_dir}/{{sample}}.microbial.fastq.gz"
    threads: DEFAULT_THREADS
    shell:
        r"""
        mkdir -p "{output_dir}"
        samtools fastq -@ {threads} -f 4 -F 1 "{input.bam}" | pigz -p {threads} > "{output.reads}"
        """

rule seqkit_stats_microbial:
    input:
        fastq=f"{output_dir}/{{sample}}.microbial.fastq.gz"
    output:
        stats=f"{output_dir}/{{sample}}.microbial.seqkit.tsv"
    threads: DEFAULT_THREADS
    shell:
        r"""
        mkdir -p "{output_dir}"
        seqkit stats -a -T -j {threads} "{input.fastq}" > "{output.stats}"
        """

rule kraken2_classify:
    input:
        reads=f"{output_dir}/{{sample}}.microbial.fastq.gz"
    output:
        classification=f"{output_dir}/{{sample}}.kraken2",
        report=f"{output_dir}/{{sample}}.k2report"
    threads: DEFAULT_THREADS
    params:
        db=kraken_db,
        confidence=kraken_confidence
    shell:
        r"""
        mkdir -p "{output_dir}"
        kraken2 --db "{params.db}" --threads {threads} --confidence {params.confidence} --report "{output.report}" "{input.reads}" > "{output.classification}"
        """

rule centrifuge_classify:
    input:
        reads=f"{output_dir}/{{sample}}.microbial.fastq.gz"
    output:
        out=f"{output_dir}/{{sample}}_centrifuge.out",
        report=f"{output_dir}/{{sample}}_centrifuge_report.tsv"
    threads: DEFAULT_THREADS
    params:
        db=centrifuge_db,
        min_hitlen=centrifuge_min_hitlen
    shell:
        r"""
        mkdir -p "{output_dir}"
        centrifuge -x "{params.db}" -q --quiet --min-hitlen {params.min_hitlen} -U "{input.reads}" --out-fmt tab --threads {threads} --report-file "{output.report}" -S "{output.out}"
        """

rule filter_centrifuge:
    input:
        report=f"{output_dir}/{{sample}}_centrifuge_report.tsv"
    output:
        filtered=f"{output_dir}/filtered_{{sample}}.tsv"
    params:
        level=bracken_level,
        threshold=bracken_threshold
    script:
        "scripts/filter_centrifuge.py"

rule bracken_estimate:
    input:
        report=f"{output_dir}/{{sample}}.k2report"
    output:
        abundance=f"{output_dir}/{{sample}}.bracken",
        report=f"{output_dir}/{{sample}}.b2report"
    params:
        db=bracken_db,
        level=bracken_level,
        threshold=bracken_threshold
    shell:
        r"""
        mkdir -p "{output_dir}"
        bracken -d "{params.db}" -i "{input.report}" -o "{output.abundance}" -w "{output.report}" -l "{params.level}" -t {params.threshold}
        """

rule compare_taxa:
    input:
        bracken=f"{output_dir}/{{sample}}.bracken",
        centrifuge=f"{output_dir}/filtered_{{sample}}.tsv"
    output:
        comparison=f"{output_dir}/{{sample}}_taxa_comparison.tsv"
    params:
        level=bracken_level
    script:
        "scripts/compare_taxa.py"

rule alpha_diversity:
    input:
        bracken=f"{output_dir}/{{sample}}.bracken"
    output:
        alpha=f"{output_dir}/{{sample}}.alpha.txt"
    shell:
        r"""
        mkdir -p "{output_dir}"
        alpha_diversity.py -f "{input.bracken}" -a Sh >  "{output.alpha}"
        alpha_diversity.py -f "{input.bracken}" -a BP >> "{output.alpha}"
        alpha_diversity.py -f "{input.bracken}" -a Si >> "{output.alpha}"
        alpha_diversity.py -f "{input.bracken}" -a ISi >> "{output.alpha}"
        alpha_diversity.py -f "{input.bracken}" -a F >> "{output.alpha}"
        """

rule collect_metrics:
    input:
        raw=expand(f"{output_dir}/{{sample}}.raw.seqkit.tsv", sample=SAMPLES),
        trimmed=expand(f"{output_dir}/{{sample}}.trimmed.seqkit.tsv", sample=SAMPLES),
        microbial=expand(f"{output_dir}/{{sample}}.microbial.seqkit.tsv", sample=SAMPLES),
        kraken=expand(f"{output_dir}/{{sample}}.kraken2", sample=SAMPLES),
        bracken=expand(f"{output_dir}/{{sample}}.bracken", sample=SAMPLES),
        centrifuge_filtered=expand(f"{output_dir}/filtered_{{sample}}.tsv", sample=SAMPLES),
        alpha=expand(f"{output_dir}/{{sample}}.alpha.txt", sample=SAMPLES)
    output:
        metrics=f"{output_dir}/sample_metrics.tsv",
        beta=f"{output_dir}/beta_diversity.tsv"
    script:
        "scripts/metrics.py"

rule reversematch_coverage:
    input:
        comparison=f"{output_dir}/{{sample}}_taxa_comparison.tsv",
        microbial_fastq=f"{output_dir}/{{sample}}.microbial.fastq.gz"
    output:
        coverage_json=f"{output_dir}/{{sample}}_taxa_coverage.json"
    threads: DEFAULT_THREADS
    params:
        output_dir=output_dir,
        downloads_dir=f"{output_dir}/shared_references",
        api_key=config.get("ncbi_api_key", "")
    script:
        "scripts/reversematch.py"

rule interactive_summary:
    input:
        metrics=f"{output_dir}/sample_metrics.tsv",
        beta=f"{output_dir}/beta_diversity.tsv",
        bracken=expand(f"{output_dir}/{{sample}}.bracken", sample=SAMPLES),
        centrifuge=expand(f"{output_dir}/filtered_{{sample}}.tsv", sample=SAMPLES),
        comparison=expand(f"{output_dir}/{{sample}}_taxa_comparison.tsv", sample=SAMPLES),
        coverage=expand(f"{output_dir}/{{sample}}_taxa_coverage.json", sample=SAMPLES)
    output:
        html=f"{output_dir}/Results.html"
    script:
        "scripts/summary.py"

rule clean_intermediates:
    input:
        html=f"{output_dir}/Results.html"
    output:
        touch(f"{output_dir}/.cleaned")
    params:
        out_dir=output_dir
    shell:
        r"""
        find "{params.out_dir}" -maxdepth 1 -type f ! -name "Results.html" ! -name ".cleaned" -exec rm -f {{}} +
        find "{params.out_dir}" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {{}} +
        """