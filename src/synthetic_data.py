"""
synthetic_data.py - Generate realistic synthetic Nextflow log files for training.

Each generated log has:
  - A realistic header (NF version, pipeline, revision, executor)
  - Random process progress lines (some complete, some partial)
  - An injected error block matching one of the 8 failure categories
  - Realistic surrounding context (work dirs, commands, tips)

Usage:
    from src.synthetic_data import generate_dataset
    dataset = generate_dataset(n_per_category=200, seed=42)
    # Returns list of {"text": str, "label": str, "meta": dict}
"""

import random
import string
import os
from datetime import datetime, timedelta


# ── Building blocks ──────────────────────────────────────────────

NF_VERSIONS = ["21.04.0", "21.10.6", "22.04.5", "22.10.8", "23.04.3", "23.10.0", "24.04.2"]

PIPELINES = [
    ("nf-core/rnaseq", ["3.10.1", "3.11.0", "3.12.0", "3.14.0"]),
    ("nf-core/sarek", ["3.2.3", "3.3.0", "3.4.0"]),
    ("nf-core/atacseq", ["2.0", "2.1.2"]),
    ("nf-core/chipseq", ["2.0.0", "2.1.0"]),
    ("nf-core/viralrecon", ["2.5", "2.6.0"]),
    ("nf-core/mag", ["2.3.0", "2.5.0"]),
    ("nf-core/ampliseq", ["2.6.1", "2.7.0"]),
    ("nf-core/fetchngs", ["1.10.0", "1.12.0"]),
    ("nf-core/taxprofiler", ["1.0.0", "1.1.0"]),
    ("nf-core/differentialabundance", ["1.2.0", "1.4.0"]),
    ("nf-core/methylseq", ["2.4.0", "2.6.0"]),
    ("nf-core/smrnaseq", ["2.1.0", "2.3.0"]),
    ("nf-core/scrnaseq", ["2.5.0", "2.6.0", "2.7.0"]),
]

EXECUTORS = ["local", "slurm", "sge", "pbs", "lsf", "awsbatch", "google-lifesciences", "k8s"]

RUN_NAMES = [
    "happy_darwin", "angry_turing", "jolly_knuth", "pensive_lovelace",
    "crazy_torvalds", "clever_shannon", "modest_curie", "hungry_hopper",
    "naughty_babbage", "fervent_tesla", "trusting_pasteur", "stoic_mendel",
    "reverent_crick", "goofy_watson", "elegant_rosalind", "boring_euler",
]

PROCESSES_BY_PIPELINE = {
    "nf-core/rnaseq": [
        "NFCORE_RNASEQ:RNASEQ:INPUT_CHECK:SAMPLESHEET_CHECK",
        "NFCORE_RNASEQ:RNASEQ:FASTQC",
        "NFCORE_RNASEQ:RNASEQ:TRIMGALORE",
        "NFCORE_RNASEQ:RNASEQ:ALIGN_STAR",
        "NFCORE_RNASEQ:RNASEQ:SAMTOOLS_SORT",
        "NFCORE_RNASEQ:RNASEQ:SAMTOOLS_INDEX",
        "NFCORE_RNASEQ:RNASEQ:PICARD_MARKDUPLICATES",
        "NFCORE_RNASEQ:RNASEQ:FEATURECOUNTS",
        "NFCORE_RNASEQ:RNASEQ:MULTIQC",
    ],
    "nf-core/sarek": [
        "NFCORE_SAREK:SAREK:INPUT_CHECK:SAMPLESHEET_CHECK",
        "NFCORE_SAREK:SAREK:FASTQC",
        "NFCORE_SAREK:SAREK:FASTP",
        "NFCORE_SAREK:SAREK:BWAMEM2_MEM",
        "NFCORE_SAREK:SAREK:SAMTOOLS_SORT",
        "NFCORE_SAREK:SAREK:MARKDUPLICATES",
        "NFCORE_SAREK:SAREK:BASERECALIBRATOR",
        "NFCORE_SAREK:SAREK:APPLYBQSR",
        "NFCORE_SAREK:SAREK:GATK4_HAPLOTYPECALLER",
        "NFCORE_SAREK:SAREK:MULTIQC",
    ],
    "nf-core/scrnaseq": [
        "NFCORE_SCRNASEQ:SCRNASEQ:INPUT_CHECK:SAMPLESHEET_CHECK",
        "NFCORE_SCRNASEQ:SCRNASEQ:FASTQC",
        "NFCORE_SCRNASEQ:SCRNASEQ:STARSOLO",
        "NFCORE_SCRNASEQ:SCRNASEQ:GENE_MAP",
        "NFCORE_SCRNASEQ:SCRNASEQ:MTX_TO_H5AD",
        "NFCORE_SCRNASEQ:SCRNASEQ:CONCAT_H5AD",
        "NFCORE_SCRNASEQ:SCRNASEQ:MULTIQC",
    ],
}

# Default process list for pipelines not explicitly mapped
DEFAULT_PROCESSES = [
    "INPUT_CHECK:SAMPLESHEET_CHECK",
    "FASTQC",
    "TRIMGALORE",
    "ALIGN",
    "SAMTOOLS_SORT",
    "SAMTOOLS_INDEX",
    "MARKDUPLICATES",
    "QUANTIFY",
    "MULTIQC",
]

SAMPLE_IDS = [f"SAMPLE_{i:02d}" for i in range(1, 49)]

GENOMES = ["GRCh38", "GRCh37", "GRCm39", "GRCm38", "TAIR10", "WBcel235", "R64-1-1"]

REFERENCES = [
    "/data/references/{genome}/genome.fa",
    "/home/user/genomes/{genome}/Sequence/WholeGenomeFasta/genome.fa",
    "/scratch/genomes/{genome}/genome.fasta",
    "s3://nf-core-awsmegatests/references/{genome}/genome.fa",
    "/mnt/shared/references/{genome}/genome.fa",
]

WORK_DIRS = [
    "/home/{user}/work",
    "/scratch/{user}/nf-work",
    "/tmp/nextflow-work",
    "/data/pipeline_runs/{user}/work",
    "s3://my-bucket/work",
]

CONTAINER_IMAGES = [
    "nfcore/rnaseq:latest",
    "nfcore/sarek:3.4.0",
    "quay.io/biocontainers/star:2.7.10b--h9ee0642_0",
    "quay.io/biocontainers/samtools:1.17--hd87286a_1",
    "quay.io/biocontainers/fastqc:0.11.9--hdfd78af_1",
    "quay.io/biocontainers/trimgalore:0.6.7--hdfd78af_0",
    "quay.io/biocontainers/picard:3.0.0--hdfd78af_1",
    "quay.io/biocontainers/hisat2:2.2.1--hdbdd923_6",
    "biocontainers/bwa:v0.7.17_cv1",
    "docker://nfcore/atacseq:2.1.2",
]

USERS = ["ubuntu", "ec2-user", "analyst", "bioinfo", "pipeline_user", "john", "maria", "lab_admin"]


def _rand_hash():
    a = "".join(random.choices("abcdef0123456789", k=2))
    b = "".join(random.choices("abcdef0123456789", k=6))
    return f"{a}/{b}"


def _rand_hex(n=20):
    return "".join(random.choices("0123456789abcdef", k=n))


def _rand_timestamp(base=None):
    if base is None:
        base = datetime(2024, random.randint(1, 12), random.randint(1, 28),
                        random.randint(0, 23), random.randint(0, 59))
    offset = timedelta(seconds=random.randint(0, 3600))
    ts = base + offset
    return ts.strftime("%b-%d %H:%M:%S.") + f"{random.randint(0, 999):03d}"


def _build_header(rng, pipeline_name, pipeline_rev, nf_ver, executor, run_name):
    """Build the standard Nextflow log header."""
    lines = [
        f"N E X T F L O W  ~  version {nf_ver}",
        f"Launching `{pipeline_name}` [{run_name}] DSL2 - revision: {pipeline_rev}",
    ]
    n_tasks = rng.randint(8, 48)
    lines.append(f"executor >  {executor} ({n_tasks})")
    return lines, n_tasks


def _build_process_lines(rng, pipeline_name, n_samples, fail_at_index):
    """Build process progress lines. Processes before fail_at_index complete; the rest don't."""
    procs = PROCESSES_BY_PIPELINE.get(pipeline_name, DEFAULT_PROCESSES)
    lines = []
    process_info = []

    for i, proc in enumerate(procs):
        h = _rand_hash()
        sample = rng.choice(SAMPLE_IDS[:n_samples])
        display = f"{proc} ({sample})"

        if i < fail_at_index:
            pct = "100%"
            completed = n_samples
            total = n_samples
        elif i == fail_at_index:
            pct = f"  {rng.randint(0, 50)}%"
            completed = rng.randint(0, n_samples - 1)
            total = n_samples
        else:
            continue  # processes after the failure don't appear

        lines.append(
            f"[{h}] process > {display:<72} [{pct}] {completed} of {total}"
        )
        process_info.append({"hash": h, "name": display, "completed": completed, "total": total})

    return lines, process_info


def _build_error_block(rng, category, pipeline_name, user, genome):
    """Build the error-specific section of the log."""
    procs = PROCESSES_BY_PIPELINE.get(pipeline_name, DEFAULT_PROCESSES)
    failed_proc = rng.choice(procs[1:])  # don't fail on samplesheet check
    sample = rng.choice(SAMPLE_IDS)
    work_hash = _rand_hash()
    work_base = rng.choice(WORK_DIRS).format(user=user)
    work_dir = f"{work_base}/{work_hash}{_rand_hex(14)}"
    ref_path = rng.choice(REFERENCES).format(genome=genome)

    error_lines = []
    context_lines = []

    if category == "memory_exceeded":
        req_gb = rng.choice([16, 24, 32, 36, 48, 64, 72, 96, 128])
        avail_gb = round(rng.uniform(3.5, req_gb * 0.6), 1)
        exit_status = rng.choice(["-", "137", "1"])

        error_templates = [
            [f"Process requirement exceeds available memory -- req: {req_gb} GB; avail: {avail_gb} GB"],
            [f"java.lang.OutOfMemoryError: Java heap space",
             f"  at java.base/java.util.Arrays.copyOf(Arrays.java:3512)"],
            [f"Cannot allocate memory (errno=12)",
             f"  Failed to allocate {req_gb}G for STAR genome index"],
            [f"oom-kill:constraint_MEMCG:oom_memcg:/slurm/uid_{rng.randint(1000,9999)}/job_{rng.randint(10000,99999)}",
             f"Killed process {rng.randint(10000, 99999)} (STAR) total-vm:{req_gb * 1024 * 1024}kB"],
            [f"Process `{failed_proc} ({sample})` exceeded memory limit ({req_gb}.GB > {avail_gb}.GB)",
             f"SIGKILL received - process terminated"],
        ]
        error_lines = rng.choice(error_templates)

        commands = [
            f"STAR --runMode alignReads --genomeDir star_index --readFilesIn {sample}_R1.fq.gz {sample}_R2.fq.gz --runThreadN {rng.choice([4,8,12,16])}",
            f"STAR --runMode alignReads --genomeDir {ref_path.replace('genome.fa', 'star_index')} --outSAMtype BAM SortedByCoordinate",
            f"hisat2 -x {ref_path.replace('.fa', '')} -1 {sample}_R1.fq.gz -2 {sample}_R2.fq.gz -p {rng.choice([4,8,16])}",
            f"samtools sort -@ {rng.choice([4,8])} -m {req_gb}G -o sorted.bam input.bam",
        ]
        context_lines = [
            f"Command executed:\n  {rng.choice(commands)}",
            f"Command exit status: {exit_status}",
        ]

    elif category == "missing_file":
        missing_targets = [
            ref_path,
            f"/data/reads/{sample}_R1.fastq.gz",
            f"{ref_path}.fai",
            f"{ref_path.replace('.fa', '.dict')}",
            f"/data/references/{genome}/genes.gtf",
            f"/data/references/{genome}/star_index/Genome",
            f"{work_base}/staged_inputs/{sample}.bam",
        ]
        target = rng.choice(missing_targets)

        error_templates = [
            [f"No such file or directory: '{target}'"],
            [f"java.io.FileNotFoundException: {target} (No such file or directory)"],
            [f"Missing input file: {target}",
             f"  Make sure the file exists and is accessible"],
            [f"Path does not exist: {target}"],
            [f"Unable to access '{target}' -- No such file or directory"],
            [f"Error: file not found: {target}",
             f"  Check that the path is correct and the file hasn't been moved"],
        ]
        error_lines = rng.choice(error_templates)

        exit_status = rng.choice(["1", "2", "127"])
        context_lines = [
            f"Command executed:\n  cat {target}",
            f"Command exit status: {exit_status}",
        ]

    elif category == "container_issue":
        image = rng.choice(CONTAINER_IMAGES)
        engine = rng.choice(["docker", "singularity", "podman"])
        conda_envs = [
            "bioconda::star=2.7.10b", "bioconda::samtools=1.17",
            "bioconda::fastqc=0.11.9", "bioconda::trimgalore=0.6.7",
            "bioconda::hisat2=2.2.1", "bioconda::salmon=1.10.0",
            "bioconda::picard=3.0.0", "bioconda::subread=2.0.6",
        ]
        conda_env = rng.choice(conda_envs)

        error_templates = [
            [f"Unable to pull image '{image}': connection timed out"],
            [f"FATAL: container creation failed: mount {work_dir}/work: no such file or directory"],
            [f"{engine}: command not found",
             f"  Make sure {engine} is installed and in your PATH"],
            [f"Container execution failed for image {image}",
             f"  OCI runtime create failed: container_linux.go:380: starting container process caused: exec: \"bash\": executable file not found in $PATH"],
            [f"ERROR: {engine} pull failed for {image}",
             f"  FATAL: While making image from oci registry: error fetching image to cache"],
            [f"permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock"],
            [f"java.lang.IllegalStateException: Failed to create Conda environment",
             f"  command: conda create --mkdir --yes --prefix {work_dir}/conda_env {conda_env}",
             f"  status : {rng.choice([1, 2])}"],
            [f"Failed to create Conda environment",
             f"  CondaError: Downloaded bytes did not match Content-Length"],
            [f"Failed to create Conda environment -- command: mamba create --mkdir --yes --prefix {work_dir}/env {conda_env}",
             f"  mamba error: Could not solve for environment specs"],
            [f"error [java.lang.IllegalStateException]: java.lang.IllegalStateException: Failed to create Conda environment",
             f"  Session aborted -- Cause: java.lang.IllegalStateException: Failed to create Conda environment"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = rng.choice(["1", "125", "127"])
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "reference_index":
        aligner = rng.choice(["STAR", "hisat2", "bowtie2", "bwa"])
        idx_path = ref_path.replace(".fa", f"/{aligner.lower()}_index")

        error_templates = [
            [f"EXITING because of FATAL ERROR: could not open genome index file {idx_path}/Genome"],
            [f"STAR --runMode genomeGenerate failed",
             f"  Genome index is incompatible with STAR version 2.7.{rng.randint(8,11)}a"],
            [f"(ERR): {aligner.lower()}-build was not found in the PATH"],
            [f"Error: samtools faidx failed for {ref_path}",
             f"  {ref_path}.fai not found -- run 'samtools faidx {ref_path}' first"],
            [f"Fatal error: genome index missing or corrupted at {idx_path}",
             f"  Please rebuild with {aligner} --runMode genomeGenerate"],
            [f"incompatible genome index version -- found v2.7.4a, need v2.7.{rng.randint(9,11)}a",
             f"  Solution: rebuild the index with the current STAR version"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = rng.choice(["1", "104"])
        context_lines = [
            f"Command executed:\n  {aligner} --runMode alignReads --genomeDir {idx_path}",
            f"Command exit status: {exit_status}",
        ]

    elif category == "permission_issue":
        targets = [
            f"{work_dir}/.command.run",
            f"/data/reads/{sample}_R1.fastq.gz",
            ref_path,
            f"/results/{pipeline_name.split('/')[-1]}/multiqc/",
            f"{work_base}/tmp/",
            f"/var/run/docker.sock",
        ]
        target = rng.choice(targets)

        error_templates = [
            [f"Permission denied: '{target}'"],
            [f"Operation not permitted: cannot write to '{target}'"],
            [f"Access denied: insufficient permissions for {target}"],
            [f"cannot open '{target}' for reading: Permission denied"],
            [f"EACCES: permission denied, open '{target}'"],
            [f"bash: {target}: Permission denied",
             f"  Run 'chmod +x {target}' or check file ownership"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = rng.choice(["1", "126"])
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "failed_process":
        exit_code = rng.choice([1, 2, 127, 134, 139, 143, 255])

        error_templates = [
            [f"Error executing process > '{failed_proc} ({sample})'"],
            [f"Process `{failed_proc} ({sample})` terminated with an error exit status ({exit_code})"],
            [f"Command exit status: {exit_code}",
             f"  Command output: (empty)"],
            [f"Task {failed_proc} ({sample}) failed with exit code {exit_code}",
             f"  Check .command.err for details"],
            [f"Error executing process > '{failed_proc} ({sample})'",
             f"Caused by:",
             f"  Process `{failed_proc} ({sample})` terminated with an error exit status ({exit_code})"],
        ]
        error_lines = rng.choice(error_templates)

        tool_commands = [
            f"STAR --runMode alignReads --genomeDir star_index --readFilesIn {sample}_R1.fq.gz {sample}_R2.fq.gz",
            f"samtools sort -@ 4 -o {sample}.sorted.bam {sample}.bam",
            f"featureCounts -a genes.gtf -o counts.txt {sample}.sorted.bam",
            f"trim_galore --paired {sample}_R1.fq.gz {sample}_R2.fq.gz",
            f"fastqc {sample}_R1.fq.gz {sample}_R2.fq.gz --threads 4",
            f"picard MarkDuplicates I={sample}.sorted.bam O={sample}.dedup.bam M=metrics.txt",
        ]
        context_lines = [
            f"Command executed:\n  {rng.choice(tool_commands)}",
            f"Command exit status: {exit_code}",
        ]

    elif category == "invalid_parameter":
        bad_params = [
            ("--aligner_star", "--aligner star"),
            ("--trimmer fastp", "--trimmer 'fastp'"),
            ("--genome hg38", "--genome GRCh38"),
            ("--max_cpus", "--max_cpus 16"),
            ("--outdir results/", "--outdir 'results'"),
            ("--skip_qc true", "--skip_qc"),
            ("--input samples.csv", "--input 'samples.csv'"),
            ("--pseudo_aligner", "--pseudo_aligner salmon"),
        ]
        bad_param, suggestion = rng.choice(bad_params)

        error_templates = [
            [f"Unknown parameter: {bad_param}",
             f"  Did you mean: {suggestion}?"],
            [f"ERROR ~ invalid option: {bad_param}"],
            [f"ERROR ~ Schema validation failed:",
             f"  - Unrecognized argument: {bad_param}",
             f"  - Valid parameters are listed in the pipeline schema"],
            [f"'{bad_param.split()[0]}' is not a valid parameter for {pipeline_name}",
             f"  Run 'nextflow run {pipeline_name} --help' to see available parameters"],
            [f"ERROR ~ Validation of pipeline parameters failed!",
             f"  * --{bad_param.lstrip('-').split()[0]}: Unrecognized parameter"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "disk_space":
        mount_points = ["/", "/scratch", "/data", "/tmp", "/home", work_base]
        mount = rng.choice(mount_points)

        error_templates = [
            [f"No space left on device (os error 28)",
             f"  Failed to write to {work_dir}/output.bam"],
            [f"Disk quota exceeded for user {user} on {mount}",
             f"  Current usage: {rng.randint(90, 100)}% of {rng.choice([100, 200, 500, 1000])}GB"],
            [f"write error: No space left on device",
             f"  ENOSPC: {mount} is full ({rng.randint(95, 100)}% used)"],
            [f"cannot write to '{work_dir}/{sample}.sorted.bam': No space left on device"],
            [f"OSError: [Errno 28] No space left on device: '{work_dir}/tmp_{_rand_hex(8)}'",
             f"  Filesystem {mount} has {rng.choice([0, 12, 48, 128])}MB remaining"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = rng.choice(["1", "28"])
        context_lines = [f"Command exit status: {exit_status}"]

    # ── scRNA-seq error categories ────────────────────────────────
    elif category == "starsolo_memory":
        req_gb = rng.choice([32, 36, 48, 64])
        avail_gb = round(rng.uniform(8, req_gb * 0.5), 1)
        error_templates = [
            [f"STARsolo process killed with exit code 137",
             f"  Cannot allocate {req_gb}G for genome + whitelist loading"],
            [f"STAR genomeLoad failed -- cannot allocate memory",
             f"  solo out of memory: requested {req_gb}GB, available {avail_gb}GB"],
            [f"STAR process killed by signal 9 (SIGKILL)",
             f"  Genome load failed: insufficient memory for STARsolo"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "137"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "barcode_whitelist_missing":
        whitelist_paths = [
            "/data/whitelists/3M-february-2018.txt",
            "/ref/10x/737K-august-2016.txt",
            f"{work_dir}/whitelist.txt",
            "/opt/cellranger/lib/python/cellranger/barcodes/3M-february-2018.txt",
        ]
        wl_path = rng.choice(whitelist_paths)
        error_templates = [
            [f"EXITING: soloCBwhitelist file not found: {wl_path}"],
            [f"Whitelist file does not exist: {wl_path}",
             f"  --soloCBwhitelist error: cannot open file"],
            [f"Barcode whitelist missing: {wl_path}",
             f"  CB whitelist cannot open '{wl_path}'"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "wrong_chemistry":
        wrong = rng.choice(["10xv2", "10xv3", "10xv3_5prime"])
        error_templates = [
            [f"Chemistry '{wrong}' not recognized for this library"],
            [f"Invalid chemistry specification: {wrong}",
             f"  soloType invalid for the given barcode length"],
            [f"Unknown chemistry version: {wrong}",
             f"  --chemistry error: does not match detected barcode structure"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "empty_cell_output":
        error_templates = [
            [f"WARNING: no cells detected in filtered output",
             f"  0 cells passed filtering threshold"],
            [f"Empty barcode matrix: 0 cells found",
             f"  Cell number: 0 -- check chemistry and whitelist"],
            [f"Filtered matrix empty after cell calling",
             f"  0 cells detected -- possible chemistry mismatch"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "0"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "cellranger_fastq_naming":
        bad_name = rng.choice(["sample_1.fastq.gz", "reads_R1.fq.gz", "SRR1234_1.fastq.gz"])
        error_templates = [
            [f"cellranger: invalid FASTQ file name: {bad_name}",
             f"  Expected format: SampleName_S1_L001_R1_001.fastq.gz"],
            [f"FASTQ naming convention error for cellranger",
             f"  Could not detect FASTQ files matching cellranger pattern"],
            [f"No input FASTQs found for cellranger",
             f"  _R1_001.fastq.gz not found in input directory"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "kallisto_empty_bus":
        error_templates = [
            [f"BUS file is empty: 0 records processed",
             f"  kallisto pseudoalignment: 0 reads mapped"],
            [f"kb run failed: empty output",
             f"  bustools: empty BUS file, no reads pseudoaligned"],
            [f"No reads pseudoaligned to transcriptome",
             f"  kallisto 0 records -- check genome index and chemistry"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "anndata_version_mismatch":
        old_ver = rng.choice(["0.7.6", "0.8.0", "0.9.1"])
        new_ver = rng.choice(["0.10.0", "0.10.3", "0.11.0"])
        error_templates = [
            [f"anndata version {old_ver} incompatible with file written by {new_ver}",
             f"  h5ad cannot be read by current AnnData installation"],
            [f"AnnData unsupported format: file requires anndata>={new_ver}",
             f"  Installed: {old_ver}"],
            [f"anndata AttributeError: module has no attribute 'read_h5ad'",
             f"  backed h5ad error: version mismatch ({old_ver} vs {new_ver})"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    elif category == "scrna_genome_mismatch":
        assemblies = [("GRCh38", "GRCh37"), ("GRCm39", "GRCm38"), ("hg38", "hg19")]
        fasta_asm, gtf_asm = rng.choice(assemblies)
        error_templates = [
            [f"Chromosome names in GTF ({gtf_asm}) not found in FASTA ({fasta_asm})",
             f"  GTF chromosome names do not match genome FASTA"],
            [f"Contig 'chr1' from GTF not in genome FASTA",
             f"  Genome annotation incompatible: {fasta_asm} FASTA vs {gtf_asm} GTF"],
            [f"seqname 'chr1' not found in FASTA reference",
             f"  Genome/GTF mismatch: ensure both are from the same assembly"],
        ]
        error_lines = rng.choice(error_templates)
        exit_status = "1"
        context_lines = [f"Command exit status: {exit_status}"]

    # Build the full error block
    block = [
        f"Error executing process > '{failed_proc} ({sample})'",
        "",
        "Caused by:",
    ]
    for el in error_lines:
        block.append(f"  {el}")
    block.append("")
    for cl in context_lines:
        block.append(cl)
    block.extend([
        "",
        f"Work dir: {work_dir}",
        "",
        "Tip: you can replicate the issue by changing to the process work dir and entering the command `bash .command.run`",
        "",
        " -- Check '.nextflow.log' file for details",
    ])

    # Add pipeline failure message (randomly vary the format like real logs)
    fail_msgs = [
        "Pipeline completed with errors",
        f"Pipeline failed. Please refer to troubleshooting docs: https://nf-co.re/docs/usage/troubleshooting",
        f"Session aborted -- Cause: {error_lines[0] if error_lines else 'unknown error'}",
    ]
    block.append(rng.choice(fail_msgs))

    return block, failed_proc, sample


def _build_clean_log(rng, pipeline_name, pipeline_rev, nf_ver, executor, run_name, n_samples):
    """Build a clean (no errors) log for the 'clean' category."""
    header_lines, n_tasks = _build_header(rng, pipeline_name, pipeline_rev, nf_ver, executor, run_name)
    procs = PROCESSES_BY_PIPELINE.get(pipeline_name, DEFAULT_PROCESSES)

    proc_lines = []
    for proc in procs:
        h = _rand_hash()
        sample = rng.choice(SAMPLE_IDS[:n_samples])
        proc_lines.append(
            f"[{h}] process > {proc} ({sample}){' ' * max(1, 60 - len(proc) - len(sample))} [100%] {n_samples} of {n_samples}"
        )

    completion_lines = [
        "",
        f"Completed at: {_rand_timestamp()}",
        f"Duration    : {rng.randint(1, 48)}h {rng.randint(0, 59)}m {rng.randint(0, 59)}s",
        f"CPU hours   : {round(rng.uniform(10, 500), 1)}",
        f"Succeeded   : {len(procs) * n_samples}",
        "",
        "Pipeline completed successfully!",
    ]

    return "\n".join(header_lines + proc_lines + completion_lines)


def generate_single_log(category, seed=None):
    """Generate a single synthetic Nextflow log with the given error category."""
    rng = random.Random(seed)

    pipeline_name, revisions = rng.choice(PIPELINES)
    pipeline_rev = rng.choice(revisions)
    nf_ver = rng.choice(NF_VERSIONS)
    executor = rng.choice(EXECUTORS)
    run_name = rng.choice(RUN_NAMES)
    user = rng.choice(USERS)
    genome = rng.choice(GENOMES)
    n_samples = rng.randint(2, 24)

    if category == "clean":
        text = _build_clean_log(rng, pipeline_name, pipeline_rev, nf_ver, executor, run_name, n_samples)
        return {
            "text": text,
            "label": "clean",
            "meta": {"pipeline": pipeline_name, "revision": pipeline_rev, "executor": executor},
        }

    header_lines, n_tasks = _build_header(rng, pipeline_name, pipeline_rev, nf_ver, executor, run_name)
    procs = PROCESSES_BY_PIPELINE.get(pipeline_name, DEFAULT_PROCESSES)
    fail_at = rng.randint(1, len(procs) - 1)

    proc_lines, _ = _build_process_lines(rng, pipeline_name, n_samples, fail_at)
    error_block, failed_proc, failed_sample = _build_error_block(
        rng, category, pipeline_name, user, genome
    )

    all_lines = header_lines + proc_lines + [""] + error_block
    text = "\n".join(all_lines)

    return {
        "text": text,
        "label": category,
        "meta": {
            "pipeline": pipeline_name,
            "revision": pipeline_rev,
            "executor": executor,
            "failed_process": failed_proc,
            "failed_sample": failed_sample,
        },
    }


def generate_dataset(n_per_category=200, include_clean=True, seed=42):
    """Generate a full labeled dataset across all error categories (+ optional clean)."""
    categories = [
        "memory_exceeded",
        "missing_file",
        "container_issue",
        "reference_index",
        "permission_issue",
        "failed_process",
        "invalid_parameter",
        "disk_space",
        "starsolo_memory",
        "barcode_whitelist_missing",
        "wrong_chemistry",
        "empty_cell_output",
        "cellranger_fastq_naming",
        "kallisto_empty_bus",
        "anndata_version_mismatch",
        "scrna_genome_mismatch",
    ]
    if include_clean:
        categories.append("clean")

    rng = random.Random(seed)
    dataset = []

    for cat in categories:
        for i in range(n_per_category):
            item = generate_single_log(cat, seed=rng.randint(0, 2**31))
            dataset.append(item)

    rng.shuffle(dataset)
    return dataset


def save_dataset(dataset, output_dir="data/training"):
    """Save dataset to disk as individual .log files + a labels.csv index."""
    import csv

    os.makedirs(output_dir, exist_ok=True)

    index_rows = []
    for i, item in enumerate(dataset):
        filename = f"{item['label']}_{i:04d}.log"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            f.write(item["text"])
        index_rows.append({
            "filename": filename,
            "label": item["label"],
            "pipeline": item["meta"].get("pipeline", ""),
            "executor": item["meta"].get("executor", ""),
        })

    index_path = os.path.join(output_dir, "labels.csv")
    with open(index_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "label", "pipeline", "executor"])
        writer.writeheader()
        writer.writerows(index_rows)

    return index_path


if __name__ == "__main__":
    print("Generating synthetic training dataset...")
    dataset = generate_dataset(n_per_category=200, include_clean=True, seed=42)
    index_path = save_dataset(dataset)
    label_counts = {}
    for item in dataset:
        label_counts[item["label"]] = label_counts.get(item["label"], 0) + 1
    print(f"Generated {len(dataset)} logs -> {index_path}")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")
