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

SAMPLES = glob_wildcards(
    f"{fastq_dir}/{{sample}}.fastq.gz"
).sample


rule all:
    input:
        expand(
            f"{output_dir}/bracken/{{sample}}.bracken",
            sample=SAMPLES
        ),
        expand(
            f"{output_dir}/reports/{{sample}}.b2report",
            sample=SAMPLES
        )


rule trim_reads:
    input:
        fastq=f"{fastq_dir}/{{sample}}.fastq.gz"
    output:
        trimmed=f"{output_dir}/trimmed/{{sample}}.trimmed.fastq.gz"
    threads: trim_threads
    shell:
        r"""
        mkdir -p "$(dirname {output.trimmed})"

        pigz -dc "{input.fastq}" \
          | chopper -q 10 -l 100 \
          | pigz -p {threads} > "{output.trimmed}"
        """


rule map_to_human:
    input:
        reads=f"{output_dir}/trimmed/{{sample}}.trimmed.fastq.gz"
    output:
        bam=f"{output_dir}/mapping/{{sample}}.bam"
    threads: map_threads
    params:
        split_prefix=lambda wildcards: (
            f"{output_dir}/tmp/{wildcards.sample}."
        )
    shell:
        r"""
        mkdir -p "$(dirname {output.bam})"
        mkdir -p "$(dirname {params.split_prefix})"

        minimap2 \
          --split-prefix="{params.split_prefix}" \
          -a -x sr "{reference}" "{input.reads}" \
          | samtools view -@ {threads} -bh \
          | samtools sort -@ {threads} -o "{output.bam}"

        samtools index -@ {threads} "{output.bam}"
        """


rule extract_microbial_reads:
    input:
        bam=f"{output_dir}/mapping/{{sample}}.bam"
    output:
        reads=f"{output_dir}/microbial/{{sample}}.microbial.fastq.gz"
    shell:
        r"""
        mkdir -p "$(dirname {output.reads})"

        samtools fastq -f 4 -F 1 "{input.bam}" \
          | pigz -p 1 > "{output.reads}"
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
        mkdir -p "$(dirname {output.classification})"
        mkdir -p "$(dirname {output.report})"

        kraken2 \
          --db "{params.db}" \
          --threads {threads} \
          --confidence {params.confidence} \
          --report "{output.report}" \
          "{input.reads}" > "{output.classification}"
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
        mkdir -p "$(dirname {output.abundance})"
        mkdir -p "$(dirname {output.report})"

        bracken \
          -d "{params.db}" \
          -i "{input.report}" \
          -o "{output.abundance}" \
          -w "{output.report}" \
          -l "{params.level}" \
          -t {params.threshold}
        """
