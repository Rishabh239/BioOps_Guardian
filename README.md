# 🧬 BioOps Guardian

**NGS Pipeline Failure Prediction & Triage System**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.30%2B-FF4B4B.svg)](https://streamlit.io)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3%2B-F7931E.svg)](https://scikit-learn.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-42%20passing-brightgreen.svg)](#running-tests)

BioOps Guardian is a Python tool for bioinformaticians that catches Nextflow pipeline failures **before** and **after** they happen. It combines a pre-flight validator, an ML-powered log classifier, and a sample sheet checker into a single Streamlit dashboard.

---

## Features

### 🚀 Pre-Flight Check
Validate your pipeline inputs **before launching** — catch problems before they waste hours of compute:
- **Sample sheet validation** — missing columns, duplicate IDs, invalid strandedness, FASTQ path checks
- **Config parsing** — detects memory, CPU, genome, container engine settings; catches syntax errors
- **File existence checks** — verifies FASTQs, genome FASTA, GTF, and index files exist on disk
- **Memory sufficiency** — knows STAR on GRCh38 needs ~32 GB and warns if your config allocates less
- **Disk space estimation** — estimates space needed based on sample count and checks free space
- **Tool availability** — checks if Nextflow, Java, and your container engine are installed

### 🔬 Log Analyzer
Upload a `.nextflow.log` and get an ML-powered diagnosis:
- **Hybrid ML classifier** — TF-IDF text features + structured features (exit codes, memory values, process counts, regex pattern flags) fed into a Gradient Boosting model
- **9 categories** — memory exceeded, missing file, container/environment issue, reference/index issue, permission denied, failed process, invalid parameter, disk space, clean
- **Explainable predictions** — see which features drove the diagnosis
- **Actionable fixes** — cause, fix description, and copy-paste shell commands for each error type

### 📋 Sheet Validator
Standalone sample sheet validation with detailed issue reports:
- Required column checks (sample, fastq_1, fastq_2, strandedness)
- Strandedness value validation
- Paired-end naming convention checks
- Duplicate sample ID detection

### 📖 Pattern Reference
Browse all 8 error categories with their regex patterns, causes, fixes, and suggested commands.

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Rishabh239/BioOps_Guardian.git
cd BioOps_Guardian

# Install dependencies
pip install -r requirements.txt

# Train the ML model (generates synthetic data automatically)
python src/train.py --n_per_category 200

# Launch the dashboard
streamlit run app/streamlit_app.py
```

Then open http://localhost:8501 in your browser.


## Project Structure

```
bioops-guardian/
├── .streamlit/
│   └── config.toml                   # Streamlit theme (light, purple accent)
├── app/
│   └── streamlit_app.py              # Streamlit dashboard (all 4 tabs)
├── src/
│   ├── __init__.py
│   ├── patterns.py                   # 8 error pattern definitions (regex + metadata)
│   ├── log_parser.py                 # Nextflow log parsing engine
│   ├── sample_validator.py           # CSV sample sheet validation
│   ├── classifier.py                 # Rule-based failure classifier (legacy)
│   ├── feature_extractor.py          # Structured feature extraction (34 features)
│   ├── ml_classifier.py              # Hybrid ML classifier with SHAP support
│   ├── synthetic_data.py             # Synthetic training data generator
│   ├── preflight.py                  # Pre-flight validation engine
│   └── train.py                      # Model training script
├── models/
│   └── guardian_v1.pkl               # Trained model
├── data/
│   ├── demo_assets/                  # Demo log + sample sheet for the UI
│   ├── real_logs/                    # Real-world labeled logs for training
│   │   ├── labels.csv                # Label index (filename, label, pipeline, executor)
│   │   └── run_*.log                 # 18 real Nextflow logs
│   └── training/                     # Generated synthetic training data
├── tests/
│   ├── test_log_parser.py            # 8 tests
│   ├── test_sample_validator.py      # 8 tests
│   ├── test_ml_pipeline.py           # 11 tests
│   └── test_preflight.py            # 15 tests
├── requirements.txt
└── README.md
```

---

## How It Works

### ML Classifier Architecture

The classifier uses a hybrid approach combining text and structured features:

```
                  ┌─────────────────┐
   Raw log text → │  TF-IDF (3000   │──┐
                  │  n-gram features)│  │
                  └─────────────────┘  │    ┌──────────────────┐     ┌────────────┐
                                       ├──→ │  Gradient Boosting │ ──→ │ Prediction │
                  ┌─────────────────┐  │    │  Classifier        │     │ + SHAP     │
   Raw log text → │  Structured     │──┘    └──────────────────┘     └────────────┘
                  │  features (34)  │
                  └─────────────────┘
```

**Structured features include:**
- Exit codes (raw value + one-hot for 137/1/127/126/139)
- Memory values (requested GB, available GB, ratio)
- Process counts (total, completed, failed, completion ratio)
- Log statistics (line count, error line count, error density)
- Binary markers (has_oom, has_permission, has_disk, has_container, has_conda_error, has_pipeline_failed, has_stack_trace, has_index, has_schema_error)
- Regex pattern match counts (one per error category)

**Why hybrid?** Pure regex is brittle — it flags "No such file" even in harmless cache-miss debug lines. Pure ML is a black box. The hybrid approach uses regex matches as *features* for the ML model, giving it strong signals for obvious cases while learning subtler patterns from the text.

### Pre-Flight Engine

The pre-flight validator runs 6 check categories in sequence:

1. **Sample sheet** → validates structure via `sample_validator.py`, then checks if FASTQ paths exist on disk
2. **Config** → parses `nextflow.config` for memory, CPUs, genome, container engine; checks brace matching
3. **References** → checks if FASTA, GTF, and index files exist at specified paths
4. **Memory** → cross-references genome name against known memory requirements (e.g., STAR on GRCh38 needs ~32 GB)
5. **Disk space** → estimates needed space (~5 GB per sample) and checks free space at the work directory
6. **Tools** → checks if `nextflow`, `java`, and the configured container engine are on PATH

---

## Training

### Train on Synthetic Data

```bash
# Default: 200 synthetic logs per category (1,800 total across 9 categories)
python src/train.py --n_per_category 200

# More data for better accuracy
python src/train.py --n_per_category 500

# Save synthetic logs to inspect them
python src/train.py --n_per_category 200 --save_synthetic
```

### Train with Real Data

Place your labeled `.log` files in `data/real_logs/` and add entries to `labels.csv`:

```csv
filename,label,pipeline,executor
my_oom_run.log,memory_exceeded,nf-core/rnaseq,slurm
missing_ref.log,missing_file,nf-core/sarek,local
clean_run.log,clean,nf-core/rnaseq,local
```

Then retrain:

```bash
python src/train.py --n_per_category 200 --real_data data/real_logs/labels.csv
```

Real logs are automatically oversampled 3x since they're more valuable than synthetic data.

### Valid Labels

| Label | Description |
|-------|-------------|
| `memory_exceeded` | OOM kills, insufficient memory allocation |
| `missing_file` | File not found, bad paths, missing references |
| `container_issue` | Docker/Singularity/Conda environment failures |
| `reference_index` | Genome index missing, incompatible, or corrupted |
| `permission_issue` | Permission denied, access errors |
| `failed_process` | Non-zero exit status, process termination |
| `invalid_parameter` | Bad parameters, schema validation failures |
| `disk_space` | No space left on device, quota exceeded |
| `clean` | Successful pipeline run |

### Versioning Models

```bash
# Save under a specific name
python src/train.py --model_output models/guardian_v2.pkl

# Keep a backup before retraining
cp models/guardian_v1.pkl models/guardian_v1_backup.pkl
python src/train.py --n_per_category 200 --real_data data/real_logs/labels.csv
```

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

42 tests covering the log parser, sample validator, ML pipeline (synthetic data generator + feature extractor), and pre-flight validator.

---

## Extending

### Add a New Error Pattern

Edit `src/patterns.py` — add a new dict to `ERROR_PATTERNS`:

```python
{
    "id": "my_new_error",
    "label": "My New Error",
    "patterns": [
        re.compile(r"my error regex", re.I),
    ],
    "severity": "high",
    "icon": "🔥",
    "cause": "Description of what causes this.",
    "fix": "How to fix it.",
    "command": "# Shell command to fix it\nsome_command --fix",
},
```

Then add synthetic templates in `src/synthetic_data.py` and retrain. The feature extractor automatically picks up new regex patterns as features.

### Add New Structured Features

Edit `src/feature_extractor.py`:
1. Add the feature extraction logic in `extract_features()`
2. Add the feature name to `get_feature_names()`
3. Retrain the model

---

## Tech Stack

- **Python 3.9+**
- **Streamlit** — dashboard UI
- **scikit-learn** — Gradient Boosting classifier, TF-IDF, cross-validation
- **NumPy / SciPy** — feature matrix operations
- **SHAP** — model explainability (falls back to feature importance if SHAP fails)

---

## Roadmap

- [ ] Collect more real-world logs (especially memory, permission, disk space, reference index failures)
- [ ] Historical run tracking — trend analysis across multiple runs
- [ ] MultiQC / FastQC report parsing for upstream quality signals
- [ ] Auto-generate corrected `nextflow.config` based on detected issues
- [ ] Batch mode — analyze multiple logs at once with summary report
- [ ] REST API endpoint for CI/CD integration

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Add tests for new functionality
4. Run `python -m unittest discover -s tests -v` to verify all tests pass
5. Submit a pull request

To contribute training data, add labeled `.log` files to `data/real_logs/` with corresponding entries in `labels.csv` and submit a PR.
