# OCR Task10 Benchmark

This benchmark has two explicit test layers:

- `ocr_fake`: deterministic algorithm and browser-coordinate tests. These tests
  never claim PaddleOCR accuracy.
- `ocr_real_model`: opt-in tests and the benchmark CLI that load installed
  PaddleOCR models and use real Chrome screenshots.

## Corpus

`v1/manifest.json` freezes corpus version `1.0.0`, random seed `20260816`,
renderer metadata, PNG hashes, CSS/pixel ground-truth boxes, target roles,
matching modes, effects, fonts, and font sizes.

Regenerate the corpus with the checked-in HTML and system Chrome:

```bash
cd backend
.venv/bin/python tests/fixtures/ocr_benchmark/v1/generate_corpus.py
bash scripts/run_pytest.sh -q tests/benchmarks/test_ocr_benchmark_contract.py
```

DOM geometry is used only by the fixture generator to create frozen ground
truth. Product OCR, benchmark evaluation, and target resolution use PNG pixels.

## Real Acceptance

Production keeps `VAT_OCR_ALLOW_MODEL_DOWNLOAD=false`. A development machine may
download approved official models only when the benchmark command explicitly
passes `--allow-model-download`:

```bash
cd backend
VAT_RUN_REAL_OCR_BENCHMARK=1 \
  .venv/bin/python scripts/run_ocr_benchmark.py \
  --allow-model-download \
  --performance-iterations 20 \
  --output tests/benchmarks/results/task10-local.json
```

After models are installed, omit `--allow-model-download`:

```bash
VAT_RUN_REAL_OCR_BENCHMARK=1 \
  .venv/bin/python scripts/run_ocr_benchmark.py \
  --performance-iterations 20 \
  --output tests/benchmarks/results/task10-local.json
```

The command exits non-zero if any approved threshold fails. Its JSON records
raw counts, timing samples, hardware, OS, Python/package/Chrome versions,
corpus hash, git state, and model file SHA256 values.

Run the real Playwright/PaddleOCR E2E tests directly with:

```bash
VAT_RUN_REAL_OCR_BENCHMARK=1 \
  bash scripts/run_pytest.sh -q \
  tests/workers/test_playwright_real_ocr_e2e.py
```
