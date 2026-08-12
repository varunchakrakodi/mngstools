import os

configfile: "config.yaml"

reference = config["reference"]
fastq_dir = config["fastq_dir"]
output_dir = config["output_dir"]

kraken_db = config["kraken_db"]
bracken_db = config.get("bracken_db", kraken_db)

kraken_confidence = config.get("kraken_confidence", 0.03)
bracken_level = config.get("bracken_level", "S")
bracken_threshold = config.get("bracken_threshold", 2)

trim_threads = config.get("trim_threads", 4)
map_threads = config.get("map_threads", 16)
kraken_threads = config.get("kraken_threads", 16)
seqkit_threads = config.get("seqkit_threads", 4)

SAMPLES = glob_wildcards(f"{fastq_dir}/{{sample}}.fastq.gz").sample


rule all:
    input:
        expand(f"{output_dir}/bracken/{{sample}}.bracken", sample=SAMPLES),
        expand(f"{output_dir}/reports/{{sample}}.b2report", sample=SAMPLES),
        expand(f"{output_dir}/alpha/{{sample}}.alpha.txt", sample=SAMPLES),
        expand(f"{output_dir}/krona/{{sample}}.html", sample=SAMPLES),
        f"{output_dir}/summary/sample_metrics.tsv",
        f"{output_dir}/summary/beta_diversity.tsv",
        f"{output_dir}/summary/interactive_summary.html"


rule trim_reads:
    input:
        fastq=f"{fastq_dir}/{{sample}}.fastq.gz"
    output:
        trimmed=f"{output_dir}/trimmed/{{sample}}.trimmed.fastq.gz"
    threads: trim_threads
    shell:
        r"""
        mkdir -p "$(dirname {output.trimmed})"
        pigz -dc "{input.fastq}" | chopper -q 10 -l 100 | pigz -p {threads} > "{output.trimmed}"
        """


rule seqkit_stats_raw:
    input:
        fastq=f"{fastq_dir}/{{sample}}.fastq.gz"
    output:
        stats=f"{output_dir}/stats/raw/{{sample}}.seqkit.tsv"
    threads: seqkit_threads
    shell:
        r"""
        mkdir -p "$(dirname {output.stats})"
        seqkit stats -a -T -j {threads} "{input.fastq}" > "{output.stats}"
        """


rule map_to_human:
    input:
        reads=f"{output_dir}/trimmed/{{sample}}.trimmed.fastq.gz"
    output:
        bam=f"{output_dir}/mapping/{{sample}}.bam"
    threads: map_threads
    params:
        split_prefix=lambda wildcards: f"{output_dir}/tmp/{wildcards.sample}."
    shell:
        r"""
        mkdir -p "$(dirname {output.bam})" "$(dirname {params.split_prefix})"
        minimap2 --split-prefix="{params.split_prefix}" -a -x sr "{reference}" "{input.reads}" -t {threads} | samtools view -@ {threads} -bh | samtools sort -@ {threads} -o "{output.bam}"
        samtools index -@ {threads} "{output.bam}"
        """


rule seqkit_stats_trimmed:
    input:
        fastq=f"{output_dir}/trimmed/{{sample}}.trimmed.fastq.gz"
    output:
        stats=f"{output_dir}/stats/trimmed/{{sample}}.seqkit.tsv"
    threads: seqkit_threads
    shell:
        r"""
        mkdir -p "$(dirname {output.stats})"
        seqkit stats -a -T -j {threads} "{input.fastq}" > "{output.stats}"
        """


rule extract_microbial_reads:
    input:
        bam=f"{output_dir}/mapping/{{sample}}.bam"
    output:
        reads=f"{output_dir}/microbial/{{sample}}.microbial.fastq.gz"
    shell:
        r"""
        mkdir -p "$(dirname {output.reads})"
        samtools fastq -f 4 -F 1 "{input.bam}" | pigz -p 1 > "{output.reads}"
        """


rule seqkit_stats_microbial:
    input:
        fastq=f"{output_dir}/microbial/{{sample}}.microbial.fastq.gz"
    output:
        stats=f"{output_dir}/stats/microbial/{{sample}}.seqkit.tsv"
    threads: seqkit_threads
    shell:
        r"""
        mkdir -p "$(dirname {output.stats})"
        seqkit stats -a -T -j {threads} "{input.fastq}" > "{output.stats}"
        """


rule kraken2_classify:
    input:
        reads=f"{output_dir}/microbial/{{sample}}.microbial.fastq.gz"
    output:
        classification=f"{output_dir}/kraken/{{sample}}.kraken2",
        report=f"{output_dir}/reports/{{sample}}.k2report"
    threads: kraken_threads
    params:
        db=kraken_db,
        confidence=kraken_confidence
    shell:
        r"""
        mkdir -p "$(dirname {output.classification})" "$(dirname {output.report})"
        kraken2 --db "{params.db}" --threads {threads} --confidence {params.confidence} --report "{output.report}" "{input.reads}" > "{output.classification}"
        """


rule bracken_estimate:
    input:
        report=f"{output_dir}/reports/{{sample}}.k2report"
    output:
        abundance=f"{output_dir}/bracken/{{sample}}.bracken",
        report=f"{output_dir}/reports/{{sample}}.b2report"
    params:
        db=bracken_db,
        level=bracken_level,
        threshold=bracken_threshold
    shell:
        r"""
        mkdir -p "$(dirname {output.abundance})" "$(dirname {output.report})"
        bracken -d "{params.db}" -i "{input.report}" -o "{output.abundance}" -w "{output.report}" -l "{params.level}" -t {params.threshold}
        """


rule alpha_diversity:
    input:
        bracken=f"{output_dir}/bracken/{{sample}}.bracken"
    output:
        alpha=f"{output_dir}/alpha/{{sample}}.alpha.txt"
    shell:
        r"""
        mkdir -p "$(dirname {output.alpha})"
        alpha_diversity.py -f "{input.bracken}" -a Sh > "{output.alpha}"
        """


rule krona_plot:
    input:
        report=f"{output_dir}/reports/{{sample}}.b2report"
    output:
        html=f"{output_dir}/krona/{{sample}}.html"
    shell:
        r"""
        mkdir -p "$(dirname {output.html})"
        ktImportTaxonomy -q 2 -t 3 -o "{output.html}" "{input.report}"
        """


rule collect_metrics:
    input:
        raw=expand(f"{output_dir}/stats/raw/{{sample}}.seqkit.tsv", sample=SAMPLES),
        trimmed=expand(f"{output_dir}/stats/trimmed/{{sample}}.seqkit.tsv", sample=SAMPLES),
        microbial=expand(f"{output_dir}/stats/microbial/{{sample}}.seqkit.tsv", sample=SAMPLES),
        kraken=expand(f"{output_dir}/kraken/{{sample}}.kraken2", sample=SAMPLES),
        bracken=expand(f"{output_dir}/bracken/{{sample}}.bracken", sample=SAMPLES),
        alpha=expand(f"{output_dir}/alpha/{{sample}}.alpha.txt", sample=SAMPLES),
        krona=expand(f"{output_dir}/krona/{{sample}}.html", sample=SAMPLES)
    output:
        metrics=f"{output_dir}/summary/sample_metrics.tsv",
        beta=f"{output_dir}/summary/beta_diversity.tsv"
    script:
        "scripts/metrics.py"


rule interactive_summary:
    input:
        metrics=f"{output_dir}/summary/sample_metrics.tsv",
        beta=f"{output_dir}/summary/beta_diversity.tsv"
    output:
        html=f"{output_dir}/summary/interactive_summary.html"
    script:
        "scripts/summary.py"
