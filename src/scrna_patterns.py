"""
scrna_patterns.py - scRNA-seq specific error patterns for Nextflow log analysis.
Extends BioOps Guardian to support nf-core/scrnaseq pipelines.

New patterns cover: STARsolo, Cell Ranger, kallisto-bustools, AnnData errors.
Contributed by: Mansi Chandra
Based on real errors encountered running nf-core/scrnaseq on PDAC data (GSE155698).
"""

import re

SCRNA_PATTERNS = [
    {
        # STARsolo needs ~32GB RAM for human genome + barcode whitelist
        # Exit code 137 = process killed by OS due to memory
        "id": "starsolo_memory",
        "label": "STARsolo Memory Exceeded",
        "patterns": [
            re.compile(r"STARsolo.*exit code.*137", re.I),
            re.compile(r"STAR.*killed.*signal 9", re.I),
            re.compile(r"solo.*out of memory", re.I),
            re.compile(r"genome load.*failed", re.I),
            re.compile(r"STAR.*cannot allocate", re.I),
        ],
        "severity": "critical",
        "icon": "🧠",
        "cause": (
            "STARsolo requires ~32GB RAM to load the human genome index "
            "plus barcode whitelist simultaneously. Allocated memory is insufficient."
        ),
        "fix": (
            "Increase memory to at least 32GB in nextflow.config. "
            "For mouse genome minimum 28GB. Enable retry with escalating memory."
        ),
        "command": (
            "# In nextflow.config:\n"
            "process {\n"
            "  withName: 'STARSOLO' {\n"
            "    memory = { 32.GB * task.attempt }\n"
            "    errorStrategy = 'retry'\n"
            "    maxRetries = 2\n"
            "  }\n"
            "}"
        ),
    },
    {
        # 10x Chromium uses a whitelist of known cell barcodes
        # v2 whitelist: ~737k barcodes, v3 whitelist: ~6.8M barcodes
        # If file is missing, STARsolo cannot demultiplex cells
        "id": "barcode_whitelist_missing",
        "label": "Barcode Whitelist Missing",
        "patterns": [
            re.compile(r"soloCBwhitelist.*not found", re.I),
            re.compile(r"whitelist.*file.*does not exist", re.I),
            re.compile(r"barcode.*whitelist.*missing", re.I),
            re.compile(r"--soloCBwhitelist.*error", re.I),
            re.compile(r"CB whitelist.*cannot open", re.I),
        ],
        "severity": "critical",
        "icon": "🔖",
        "cause": (
            "The 10x Chromium barcode whitelist file is missing or path is incorrect. "
            "STARsolo needs this file to identify valid cell barcodes. "
            "v2 and v3 chemistry use different whitelists."
        ),
        "fix": (
            "Download the correct whitelist for your chemistry version. "
            "Specify path with --soloCBwhitelist in your params."
        ),
        "command": (
            "# Download 10x v3 whitelist:\n"
            "wget https://raw.githubusercontent.com/10XGenomics/cellranger/"
            "master/lib/python/cellranger/barcodes/3M-february-2018.txt.gz\n"
            "gunzip 3M-february-2018.txt.gz\n\n"
            "# In params.yaml:\n"
            "barcode_whitelist: '/path/to/3M-february-2018.txt'"
        ),
    },
    {
        # User passes --chemistry 10xv2 but library was made with v3 (or vice versa)
        # Results in near-zero cell detection — pipeline runs but output is empty
        "id": "wrong_chemistry",
        "label": "Wrong 10x Chemistry Specified",
        "patterns": [
            re.compile(r"chemistry.*not recognized", re.I),
            re.compile(r"invalid.*chemistry", re.I),
            re.compile(r"soloType.*invalid", re.I),
            re.compile(r"unknown chemistry.*10x", re.I),
            re.compile(r"--chemistry.*error", re.I),
        ],
        "severity": "high",
        "icon": "🧪",
        "cause": (
            "The specified 10x chemistry version does not match the library preparation. "
            "Using 10xv2 params on a v3 library (or vice versa) causes near-zero cell detection."
        ),
        "fix": (
            "Check your library preparation protocol for the chemistry version. "
            "Valid options: 10xv2, 10xv3, 10xv3_5prime. "
            "Use --chemistry auto if unsure."
        ),
        "command": (
            "# In nextflow run command:\n"
            "nextflow run nf-core/scrnaseq \\\n"
            "  --chemistry 10xv3 \\\n"
            "  --input samplesheet.csv\n\n"
            "# Valid chemistry options: 10xv2, 10xv3, 10xv3_5prime"
        ),
    },
    {
        # Pipeline completes but outputs 0 or near-0 cells
        # Usually chemistry mismatch or wrong barcode whitelist
        "id": "empty_cell_output",
        "label": "Empty Cell Output",
        "patterns": [
            re.compile(r"no cells detected", re.I),
            re.compile(r"0 cells? (passed|found|detected)", re.I),
            re.compile(r"empty barcode.*matrix", re.I),
            re.compile(r"cell number.*0", re.I),
            re.compile(r"filtered.*matrix.*empty", re.I),
        ],
        "severity": "critical",
        "icon": "🕳️",
        "cause": (
            "Pipeline ran successfully but detected zero or near-zero cells. "
            "Common causes: wrong chemistry version, incorrect barcode whitelist, "
            "or reads in wrong orientation."
        ),
        "fix": (
            "Check chemistry version matches library prep. "
            "Verify barcode whitelist matches chemistry. "
            "Check FASTQ orientation (R1 should be barcode+UMI, R2 should be cDNA)."
        ),
        "command": (
            "# Check your FASTQ orientation:\n"
            "zcat sample_R1.fastq.gz | head -8\n"
            "# R1 should be short (28bp for 10xv3: 16bp barcode + 12bp UMI)\n\n"
            "# Check cell count in output:\n"
            "wc -l outs/filtered_feature_bc_matrix/barcodes.tsv.gz"
        ),
    },
    {
        # Cell Ranger requires specific FASTQ naming convention
        # Must follow: SampleName_S1_L001_R1_001.fastq.gz
        "id": "cellranger_fastq_naming",
        "label": "Cell Ranger FASTQ Naming Error",
        "patterns": [
            re.compile(r"cellranger.*invalid.*fastq", re.I),
            re.compile(r"fastq.*naming.*convention", re.I),
            re.compile(r"could not.*detect.*fastq.*cellranger", re.I),
            re.compile(r"no input FASTQs.*cellranger", re.I),
            re.compile(r"_R1_001\.fastq.*not found", re.I),
        ],
        "severity": "high",
        "icon": "📄",
        "cause": (
            "Cell Ranger requires FASTQ files named exactly as: "
            "SampleName_S1_L001_R1_001.fastq.gz. "
            "Any deviation from this format causes Cell Ranger to fail silently or not find files."
        ),
        "fix": (
            "Rename FASTQ files to Cell Ranger format. "
            "R1 = barcode+UMI read (28bp), R2 = cDNA read."
        ),
        "command": (
            "# Rename FASTQs to Cell Ranger format:\n"
            "mv sample_1.fastq.gz sample_S1_L001_R1_001.fastq.gz\n"
            "mv sample_2.fastq.gz sample_S1_L001_R2_001.fastq.gz\n\n"
            "# Verify naming:\n"
            "ls -la *.fastq.gz"
        ),
    },
    {
        # kallisto-bustools pipeline fails when bus file is empty
        # Usually means wrong genome index or chemistry
        "id": "kallisto_empty_bus",
        "label": "kallisto-bustools Empty BUS File",
        "patterns": [
            re.compile(r"bus file.*empty", re.I),
            re.compile(r"kallisto.*0 records", re.I),
            re.compile(r"kb.*run.*failed", re.I),
            re.compile(r"bustools.*empty", re.I),
            re.compile(r"no reads.*pseudoaligned", re.I),
        ],
        "severity": "critical",
        "icon": "🚌",
        "cause": (
            "kallisto produced an empty BUS file — zero reads pseudoaligned. "
            "Usually caused by wrong genome index (species mismatch), "
            "incorrect chemistry flag, or corrupted index."
        ),
        "fix": (
            "Verify genome index matches your species. "
            "Rebuild index if corrupted. "
            "Check chemistry flag matches library prep."
        ),
        "command": (
            "# Rebuild kallisto index:\n"
            "kb ref -d human -i index.idx -g t2g.txt\n\n"
            "# Check pseudoalignment rate:\n"
            "cat run_info.json | grep pseudoaligned\n"
            "# Expect >40% — if <10% the index or chemistry is wrong"
        ),
    },
    {
        # AnnData h5ad file written by newer version than what is installed
        # Common when sharing files between environments
        "id": "anndata_version_mismatch",
        "label": "AnnData Version Mismatch",
        "patterns": [
            re.compile(r"anndata.*version.*incompatible", re.I),
            re.compile(r"h5ad.*cannot.*read", re.I),
            re.compile(r"AnnData.*unsupported.*format", re.I),
            re.compile(r"backed.*h5ad.*error", re.I),
            re.compile(r"anndata.*AttributeError", re.I),
        ],
        "severity": "high",
        "icon": "📦",
        "cause": (
            "The .h5ad file was written by a newer version of AnnData than is installed "
            "in the current environment. AnnData format changes between major versions."
        ),
        "fix": (
            "Update AnnData to latest version, or convert the file "
            "using the version that created it."
        ),
        "command": (
            "# Update AnnData:\n"
            "pip install --upgrade anndata\n\n"
            "# Check current version:\n"
            "python -c \"import anndata; print(anndata.__version__)\"\n\n"
            "# Convert h5ad if needed:\n"
            "python -c \""
            "import anndata as ad; "
            "adata = ad.read_h5ad('old_file.h5ad'); "
            "adata.write_h5ad('new_file.h5ad')\""
        ),
    },
    {
        # Genome FASTA and GTF are from different assembly versions
        # e.g. GRCh38 FASTA with GRCh37 GTF — chromosome names won't match
        "id": "scrna_genome_mismatch",
        "label": "scRNA-seq Genome/GTF Mismatch",
        "patterns": [
            re.compile(r"chromosome.*not found.*GTF", re.I),
            re.compile(r"GTF.*chromosome.*mismatch", re.I),
            re.compile(r"contig.*not in.*genome", re.I),
            re.compile(r"seqname.*not found.*fasta", re.I),
            re.compile(r"genome.*annotation.*incompatible", re.I),
        ],
        "severity": "critical",
        "icon": "🧬",
        "cause": (
            "The genome FASTA and GTF annotation file are from different assembly versions "
            "(e.g. GRCh38 FASTA with GRCh37 GTF). Chromosome names do not match, "
            "causing alignment to fail or produce zero mapped reads."
        ),
        "fix": (
            "Use matching FASTA and GTF from the same Ensembl release. "
            "Download both from the same Ensembl release page."
        ),
        "command": (
            "# Download matching genome + GTF (Ensembl release 109):\n"
            "wget https://ftp.ensembl.org/pub/release-109/fasta/"
            "homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz\n"
            "wget https://ftp.ensembl.org/pub/release-109/gtf/"
            "homo_sapiens/Homo_sapiens.GRCh38.109.gtf.gz\n\n"
            "# Always use the SAME release number for both files"
        ),
    },
]
