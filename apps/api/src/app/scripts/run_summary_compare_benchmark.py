"""執行雙語 summary/compare benchmark suite 的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.core.settings import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.services.summary_compare_benchmark import (
    run_summary_compare_benchmark,
    write_summary_compare_benchmark_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 benchmark CLI 參數的 parser。
    """

    parser = argparse.ArgumentParser(description="執行雙語 summary/compare benchmark suite。")
    parser.add_argument("--area-id", required=True, help="要執行 benchmark 的 area id。")
    parser.add_argument("--dataset-dir", required=True, help="benchmark suite 或 package 目錄。")
    parser.add_argument("--actor-sub", required=True, help="以哪個使用者身分執行 benchmark。")
    parser.add_argument("--judge-model", default=None, help="覆寫預設 judge model。")
    parser.add_argument(
        "--max-parallel-workers",
        type=int,
        default=6,
        help="同時執行的 item lanes 數，最大為 6。",
    )
    parser.add_argument("--output-path", required=True, help="JSON report 輸出路徑。")
    return parser


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：直接輸出 benchmark summary 到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    def report_progress(event: dict[str, object]) -> None:
        """將 benchmark 進度事件輸出到 stderr。

        參數：
        - `event`：可序列化進度事件。

        回傳：
        - `None`：僅輸出一行 JSON。
        """

        print(json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True)

    with session_factory() as session:
        report = run_summary_compare_benchmark(
            session=session,
            settings=settings,
            area_id=args.area_id,
            actor_sub=args.actor_sub,
            dataset_dir=Path(args.dataset_dir).resolve(),
            judge_model=args.judge_model,
            max_parallel_workers=args.max_parallel_workers,
            progress_reporter=report_progress,
        )
        json_path, markdown_path = write_summary_compare_benchmark_artifacts(
            report=report,
            output_path=Path(args.output_path).resolve(),
        )
        print(
            json.dumps(
                {
                    "json_report_path": str(json_path),
                    "markdown_summary_path": str(markdown_path),
                    "summary_benchmark_score": report.task_family_scores["summary_benchmark_score"].model_dump(mode="json"),
                    "compare_benchmark_score": report.task_family_scores["compare_benchmark_score"].model_dump(mode="json"),
                    "parallel_workers": report.execution.parallel_workers,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
