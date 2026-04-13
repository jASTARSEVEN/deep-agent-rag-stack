"""執行 Phase 8A summary/compare checkpoint 的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.core.settings import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.services.summary_compare_checkpoint import (
    export_summary_compare_checkpoint_offline_packets,
    run_summary_compare_checkpoint,
    run_summary_compare_checkpoint_from_offline_packets,
    write_summary_compare_checkpoint_artifacts,
)
from app.services.summary_compare_offline_judge import write_offline_judge_packets


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 checkpoint 指令的 parser。
    """

    parser = argparse.ArgumentParser(description="執行 Phase 8A summary/compare evaluation checkpoint。")
    parser.add_argument("--area-id", required=True, help="要執行 checkpoint 的 area id。")
    parser.add_argument("--dataset-dir", required=True, help="checkpoint dataset 目錄。")
    parser.add_argument("--actor-sub", required=True, help="以哪個使用者身分執行 checkpoint。")
    parser.add_argument("--judge-model", default=None, help="覆寫預設 judge model。")
    parser.add_argument(
        "--judge-mode",
        choices=("openai", "offline-export", "offline-import"),
        default="openai",
        help="judge 模式：openai、離線匯出 packet、或從離線結果匯入。",
    )
    parser.add_argument(
        "--judge-packets-path",
        default=None,
        help="離線 judge packet JSONL 路徑；offline-export 會寫出，offline-import 會讀取。",
    )
    parser.add_argument(
        "--judge-results-path",
        default=None,
        help="離線 judge 回填結果 JSONL 路徑；僅 offline-import 需要。",
    )
    parser.add_argument(
        "--thinking-mode",
        choices=("true", "false"),
        default="true",
        help="是否以 thinking-mode synthesis lane 執行 checkpoint；預設為 true。",
    )
    parser.add_argument("--output-path", required=True, help="JSON report 輸出路徑。")
    return parser


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：直接輸出 JSON summary 到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    thinking_mode = args.thinking_mode == "true"

    def report_progress(event: dict[str, object]) -> None:
        """將 checkpoint 進度事件輸出到 stderr。

        參數：
        - `event`：可序列化的進度事件。

        回傳：
        - `None`：僅輸出一行 JSON。
        """

        print(json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True)

    with session_factory() as session:
        if args.judge_mode == "offline-export":
            if not args.judge_packets_path:
                raise ValueError("offline-export 需要提供 --judge-packets-path。")
            manifest, packets = export_summary_compare_checkpoint_offline_packets(
                session=session,
                settings=settings,
                area_id=args.area_id,
                actor_sub=args.actor_sub,
                dataset_dir=Path(args.dataset_dir),
                thinking_mode=thinking_mode,
                judge_label=args.judge_model or "offline-codex",
            )
            packet_path = write_offline_judge_packets(
                packets=packets,
                output_path=Path(args.judge_packets_path),
            )
            print(
                json.dumps(
                    {
                        "mode": args.judge_mode,
                        "benchmark_name": manifest.benchmark_name,
                        "item_count": manifest.item_count,
                        "judge_packets_path": str(packet_path),
                    },
                    ensure_ascii=False,
                )
            )
            return

        if args.judge_mode == "offline-import":
            if not args.judge_packets_path or not args.judge_results_path:
                raise ValueError("offline-import 需要同時提供 --judge-packets-path 與 --judge-results-path。")
            report = run_summary_compare_checkpoint_from_offline_packets(
                settings=settings,
                area_id=args.area_id,
                actor_sub=args.actor_sub,
                dataset_dir=Path(args.dataset_dir),
                thinking_mode=thinking_mode,
                judge_packets_path=Path(args.judge_packets_path),
                judge_results_path=Path(args.judge_results_path),
                judge_label=args.judge_model or "offline-codex",
            )
        else:
            report = run_summary_compare_checkpoint(
                session=session,
                settings=settings,
                area_id=args.area_id,
                actor_sub=args.actor_sub,
                dataset_dir=Path(args.dataset_dir),
                thinking_mode=thinking_mode,
                judge_model=args.judge_model,
                progress_reporter=report_progress,
            )
        json_path, markdown_path = write_summary_compare_checkpoint_artifacts(
            report=report,
            output_path=Path(args.output_path),
        )
        print(
            json.dumps(
                {
                    "mode": args.judge_mode,
                    "passed": report.passed,
                    "json_report_path": str(json_path),
                    "markdown_summary_path": str(markdown_path),
                    "thinking_mode": report.run_metadata.thinking_mode,
                    "aggregate_metrics": report.aggregate_metrics.model_dump(mode="json"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
