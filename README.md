# CandidateForge — Multi-Source Candidate Data Transformer

CandidateForge is a production-quality Python data pipeline designed to ingest messy, heterogeneous candidate profiles from multiple distinct sources, clean and normalize them, resolve merge conflicts under defined priorities, track granular field-level provenance, and output structured, validated candidate records.

This implementation is built for the Jul–Dec 2026 Eightfold Engineering Intern assignment.

## Source Types Handled & Rationale

We ingest from three distinct sources to simulate the real-world challenge of applicant tracking at Eightfold:
1. **ATS JSON (Structured Schema Mismatch):** Simulates standard candidate database records where schemas and keys must be translated dynamically.
2. **GitHub Profile URL (Public REST API):** Extracts real-time data from an active profile, mapping languages to skills and biographies to headlines.
3. **Recruiter Notes TXT (Messy Unstructured Text):** Extracts information from notes using regex-based phrase matching.

---

## Pipeline Architecture

The pipeline runs sequentially across 7 stages:
1. **Ingest (`pipeline/ingestion/`):** Safely loads raw inputs. Gracefully handles network failures, 403 API rate limits, 404s, and empty note files without crashing. Includes a local fixture backup for offline testing (`inputs/mock_github_response.json`).
2. **Extract (`pipeline/extraction/`):** Maps raw source keys into internal candidate attributes. Employs word boundaries (`\b`) to match multi-word skill phrases (e.g., `"Spring Boot"`, `"Tailwind CSS"`).
3. **Normalize (`pipeline/normalization/`):** Normalizes values to global standards:
   - Phones -> E.164 (using `phonenumbers`, assuming default region `IN` if missing code).
   - Dates -> `YYYY-MM` (using `dateutil`).
   - Countries -> ISO-3166 alpha-2 (using `pycountry`).
   - Skills -> Canonical names (using `skill_aliases.yaml`).
   - Locations -> Splitting and parsing city/region/country codes.
4. **Merge (`pipeline/merger.py`):** Merges properties using priority `github_api` > `ats_json` > `recruiter_notes`. Groups experience/education using fuzzy institution matching (`rapidfuzz`), resolving date conflicts, and calculating total experience years.
5. **Confidence Scoring (`pipeline/confidence.py`):** Calculates score per field (based on source count, source priority, and normalization assumptions) and computes a weighted `overall_confidence`.
6. **Project (`pipeline/projector.py`):** Extracts configured paths (supporting list indexing `emails[0]` or subfields `skills[].name`) to generate distinct profile variants.
7. **Validate (`pipeline/validator.py`):** Assures structural validity by running outputs against the JSON Schema (`schemas/output_schema.json`) using `jsonschema`.

---

## How to Setup & Run

### 1. Installation
Install the project dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run CLI commands

**Note on Windows/PowerShell:** The multi-line backslash (`\`) syntax is for Unix bash. For Windows PowerShell, you can run them as a single line (removing the `\` and newlines) or replace `\` with a backtick (`` ` ``).

#### Default Canonical Profile (Output default schema)
Runs the pipeline on the sample candidate "Aarav Sharma" and writes to `outputs/default_output.json`:
```bash
# Unix / Multi-line format
python main.py \
  --ats inputs/sample_ats.json \
  --github aarav-sharma \
  --notes inputs/sample_notes.txt \
  --output outputs/default_output.json

# Windows / Single-line format (Recommended for PowerShell)
python main.py --ats inputs/sample_ats.json --github aarav-sharma --notes inputs/sample_notes.txt --output outputs/default_output.json
```

#### Custom Profile Variant (Rename fields, omit provenance)
Projects output using the configuration in `config/custom_config.json`:
```bash
# Unix / Multi-line format
python main.py \
  --ats inputs/sample_ats.json \
  --github aarav-sharma \
  --notes inputs/sample_notes.txt \
  --config config/custom_config.json \
  --output outputs/custom_output.json

# Windows / Single-line format (Recommended for PowerShell)
python main.py --ats inputs/sample_ats.json --github aarav-sharma --notes inputs/sample_notes.txt --config config/custom_config.json --output outputs/custom_output.json
```

#### Running in Verbose Mode
Use the `--verbose` flag to see detailed logs showing each pipeline stage firing:
```bash
python main.py --ats inputs/sample_ats.json --github aarav-sharma --notes inputs/sample_notes.txt --output outputs/default_output.json --verbose
```

#### CLI Options
- `--ats` : Path to ATS JSON file (optional).
- `--github` : GitHub username (optional; use `aarav-sharma` to load local mock fixture).
- `--notes` : Path to recruiter notes TXT file (optional).
- `--config` : Path to custom output configuration JSON (optional).
- `--output` : Path to write output JSON (defaults to stdout).
- `--verbose` : Enabling this prints detailed step-by-step pipeline execution logs to stderr. Without this, only warnings/errors are displayed.

---

## Web UI

CandidateForge features a single-page Flask-based visual dashboard:
```bash
python -m ui.app
```
Open your browser to `http://127.0.0.1:5000`. You can:
- Paste or upload ATS JSON, GitHub username, and Recruiter notes.
- Select your Output Schema (Default or Custom configuration).
- Click **Run Transformer Pipeline** to see the syntax-highlighted JSON output, overall confidence badge, and a granular **Field-Level Provenance Grid**.
- Click **Load Sample Candidate** to pre-fill forms with testing credentials.

---

## Run Unit Tests

Execute the unit test suite:
```bash
python -m pytest tests/
```

### Test Coverage Details
Our test files cover the following functionality:
- `test_normalizers.py`: Validates phone normalization to E.164 (both with and without country codes), phone parsing error handling, skill canonicalization alias lookups, and flexible date parsing formats to `YYYY-MM` (including "Present" handling).
- `test_merger.py`: Asserts priority-based scalar conflict resolution, granular provenance conflict state recordings (`conflict_discarded`), skill unions, list deduplication, and pipeline execution with missing sources.
- `test_projector.py`: Verifies configuration path evaluation, index list slicing, attribute extraction, and confidence/provenance inclusion flags.
- `test_edge_cases.py`: Checks fallback behavior on GitHub API 404 errors, handles empty/blank notes file scenarios safely, tests single-source partial profile generation, and validates candidate identity verification checks (rejecting and logging when a mismatched GitHub profile is linked).

---

## Key Design Decisions & Assumptions

- **Deterministic ID Generation:** The `candidate_id` is generated by hashing the primary email using SHA-256. If email is missing, we hash `full_name + github_url` to guarantee determinism.
- **Granular Provenance:** Tracking is field-level rather than record-level. We preserve conflict resolution history by tagging overridden/losing source records in provenance with a `"conflict_discarded"` flag.
- **Years Experience Computation:** Sums the months of all parsed experience records (using `2026-06` as reference for present) and converts it to years (total months / 12.0) rounded to 1 decimal place.
- **GitHub Identity Verification Check:** Compares GitHub details against other sources. If there is zero email overlap and name similarity is below 60% (via `rapidfuzz` token set ratio), it rejects the GitHub record with a `github_identity_mismatch` error log to keep data pristine.

---

## What I Deliberately Left Out (Descoped)

To keep the pipeline focused, robust, and state-of-the-art, the following items were deliberately descoped:
- **LinkedIn Scraping:** Excluded due to LinkedIn's Terms of Service and robot.txt scraping restrictions (anti-bot protection).
- **PDF Resume Parsing:** Excluded due to the unreliability of native PDF text extraction tools under strict execution constraints. We prioritize structured inputs (ATS JSON) and clean text (notes).
- **No Persistent Database:** The pipeline is stateless by design to maintain pure determinism (same input always produces the exact same output).
- **OAuth Token Configuration:** The GitHub Ingester operates using public REST API requests. To prevent rate-limit crashes during evaluations, we implement a fallback to a local JSON mock fixture for the demo profile (`aarav-sharma`).

---

## Demo Video

You can watch the video walkthrough demonstrating the CandidateForge command-line pipeline execution (including custom configurations) and the interactive web interface [here](https://vimeo.com/placeholder-demo-video).
