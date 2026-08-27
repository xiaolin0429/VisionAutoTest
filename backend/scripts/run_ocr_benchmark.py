#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_BACKEND_ROOT))

from tests.benchmarks.ocr_runner import (
    BACKEND_ROOT,
    DEFAULT_CHROME,
    assert_real_model_opt_in,
    build_pipeline,
    build_result,
    evaluate_thresholds,
    load_manifest,
    prewarm_models,
    require_passing_thresholds,
    run_accuracy_benchmark,
    run_performance_benchmark,
    run_web_e2e_benchmark,
    write_result,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Task10 against real PaddleOCR and real Chrome."
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=BACKEND_ROOT / ".data" / "ocr-models",
    )
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Allow official PaddleOCR model downloads for this development run.",
    )
    parser.add_argument(
        "--chrome-executable",
        type=Path,
        default=DEFAULT_CHROME,
    )
    parser.add_argument(
        "--preprocessing-profile",
        choices=("fast", "balanced", "robust"),
        default="balanced",
    )
    parser.add_argument(
        "--max-preprocess-variants",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--minimum-confidence",
        type=float,
        default=0.40,
    )
    parser.add_argument(
        "--performance-iterations",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_ROOT / "output" / "ocr-benchmark" / "task10-latest.json",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Write the real result but do not return non-zero for failed thresholds.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    assert_real_model_opt_in()
    manifest = load_manifest()
    pipeline = build_pipeline(
        manifest=manifest,
        model_root=args.model_root.resolve(),
        allow_model_download=args.allow_model_download,
        preprocessing_profile=args.preprocessing_profile,
        max_preprocess_variants=args.max_preprocess_variants,
        minimum_confidence=args.minimum_confidence,
    )
    warmup = prewarm_models(pipeline, manifest=manifest)
    accuracy = run_accuracy_benchmark(pipeline, manifest=manifest)
    performance = run_performance_benchmark(
        pipeline,
        chrome_executable=args.chrome_executable.resolve(),
        iterations=args.performance_iterations,
        preprocessing_profile=args.preprocessing_profile,
    )
    web_e2e = run_web_e2e_benchmark(
        pipeline,
        chrome_executable=args.chrome_executable.resolve(),
    )
    thresholds = evaluate_thresholds(
        manifest=manifest,
        accuracy=accuracy,
        performance=performance,
        web_e2e=web_e2e,
    )
    result = build_result(
        manifest=manifest,
        model_root=args.model_root.resolve(),
        preprocessing_profile=args.preprocessing_profile,
        max_preprocess_variants=args.max_preprocess_variants,
        minimum_confidence=args.minimum_confidence,
        warmup=warmup,
        accuracy=accuracy,
        performance=performance,
        web_e2e=web_e2e,
        thresholds=thresholds,
        command=[sys.executable, *sys.argv],
    )
    write_result(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "result_path": _display_path(args.output.resolve()),
                "detection_f1": accuracy["detection"]["f1"],
                "cer": accuracy["recognition"]["cer"],
                "disturbed_target_success_rate": accuracy["targeting"][
                    "disturbed_success_rate"
                ],
                "wrong_operation_rate": accuracy["targeting"][
                    "wrong_operation_rate"
                ],
                "unique_interaction_success_rate": web_e2e[
                    "unique_interaction_success_rate"
                ],
                "web_e2e_wrong_operation_rate": web_e2e[
                    "wrong_operation_rate"
                ],
                "ambiguity_rejection_rate": accuracy["ambiguity"][
                    "rejection_rate"
                ],
                "viewport_p95_ms": performance["viewport_1920x1080"][
                    "p95_ms"
                ],
                "three_viewport_page_p95_ms": performance[
                    "three_viewport_page"
                ]["p95_ms"],
                "passed": thresholds["passed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not args.report_only:
        require_passing_thresholds(thresholds)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


if __name__ == "__main__":
    main()
