**Install the conda environment**

conda create --file environment.yml

**Configure the configfile.yaml according to requirements.**
Get your NCBI API key for uninterrupted download. See https://www.ncbi.nlm.nih.gov/datasets/docs/v2/api/api-keys/

To Run the workflow, activate the smacked environment

conda activate smacked

**For generating dag file use:**
snakemake --snakefile smacked.py --configfile config.yaml --dag | dot -Tpng > dag.png

**For running snakemake workflow:**
snakemake --snakefile smkalign.py --configfile config.yaml --cores n --latency-wait {seconds}

The Workflow has following dependencies:

1. chopper. https://anaconda.org/channels/bioconda/packages/chopper/overview
2. pigz. https://anaconda.org/channels/main/packages/pigz/overview
3. minimap2. https://anaconda.org/channels/bioconda/packages/minimap2/overview
4. samtools. https://anaconda.org/channels/bioconda/packages/samtools/overview
5. snakemake. https://anaconda.org/channels/bioconda/packages/snakemake/overview
6. kraken2. https://anaconda.org/channels/bioconda/packages/kraken2/overview
7. bracken. https://anaconda.org/channels/bioconda/packages/bracken/overview
8. centrifuge. https://anaconda.org/channels/bioconda/packages/centrifuge/overview
9. krakentools. https://anaconda.org/channels/bioconda/packages/krakentools/overview
10. seqkit. https://anaconda.org/channels/bioconda/packages/seqkit/overview
11. scipy. https://anaconda.org/channels/main/packages/scipy/overview
12. ncbi-genome-download. https://anaconda.org/channels/bioconda/packages/ncbi-genome-download/overview
13. graphviz. https://anaconda.org/channels/conda-forge/packages/graphviz/overview
14. plotly. https://anaconda.org/channels/main/packages/plotly/overview
15. pyside6. https://anaconda.org/channels/main/packages/pyside6/overview
