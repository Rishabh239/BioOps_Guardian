# scRNA-seq Extension — Contribution Notes

**Contributor:** Mansi Chandra  
**Date:** May 2026  
**Branch:** feature/scrna-seq-patterns

---

## Overview

This contribution extends BioOps Guardian with single-cell RNA-seq (scRNA-seq)
pipeline support, adding it alongside the existing bulk RNA-seq coverage.

BioOps Guardian already does a great job catching common Nextflow pipeline
failures. This module adds the same level of support for nf-core/scrnaseq
workflows — covering STARsolo, Cell Ranger, kallisto-bustools, and AnnData
specific errors that single-cell users commonly encounter.

---

## Background

While running nf-core/scrnaseq to reproduce a published PDAC single-cell
study (Peng et al. 2019, GSE155698), I found myself wishing BioOps Guardian
could triage the scRNA-seq specific errors I was hitting — things like
barcode whitelist mismatches and STARsolo memory failures that look different
from their bulk RNA-seq equivalents.

This module is the result of that experience.

---

## What's included

Two new files, following the existing BioOps Guardian code structure exactly:

**`src/scrna_patterns.py`** — 8 scRNA-seq error patterns

| Pattern ID | Error | Tool |
|---|---|---|
| `starsolo_memory` | OOM loading genome + whitelist | STARsolo |
| `barcode_whitelist_missing` | Whitelist file not found | STARsolo |
| `wrong_chemistry` | 10xv2/v3 chemistry mismatch | nf-core/scrnaseq |
| `empty_cell_output` | Pipeline runs but 0 cells detected | STARsolo / Cell Ranger |
| `cellranger_fastq_naming` | Wrong FASTQ naming convention | Cell Ranger |
| `kallisto_empty_bus` | Empty BUS file, zero reads aligned | kallisto-bustools |
| `anndata_version_mismatch` | h5ad written by newer AnnData version | AnnData |
| `scrna_genome_mismatch` | FASTA and GTF from different assemblies | STARsolo |

**`tests/test_scrna_patterns.py`** — 13 tests, all passing

---

## How to integrate

The patterns follow the exact same dictionary structure as `src/patterns.py`
and can be combined with the existing patterns like this:

```python
from src.scrna_patterns import SCRNA_PATTERNS
from src.patterns import ERROR_PATTERNS

ALL_PATTERNS = ERROR_PATTERNS + SCRNA_PATTERNS
```

---

## Test results
Ran 55 tests in 0.152s — OK
42 original tests: all passing
13 new tests: all passing

---

## Running the tests

```bash
# scRNA-seq tests only
python -m unittest tests/test_scrna_patterns.py -v

# Full test suite
python -m unittest discover -s tests -v
```
