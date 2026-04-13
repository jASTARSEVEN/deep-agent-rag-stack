"""summary/compare 離線 judge packet 讀寫與回填工具。"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.summary_compare_offline_judge import (
    SummaryCompareOfflineJudgeDecision,
    SummaryCompareOfflineJudgePacket,
)


def write_offline_judge_packets(
    *,
    packets: list[SummaryCompareOfflineJudgePacket],
    output_path: Path,
) -> Path:
    """將離線 judge packets 寫成 JSONL。

    參數：
    - `packets`：要寫出的 packet 清單。
    - `output_path`：JSONL 檔案路徑。

    回傳：
    - `Path`：實際寫出的檔案路徑。
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for packet in packets:
            file.write(json.dumps(packet.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return output_path


def load_offline_judge_packets(*, packet_path: Path) -> list[SummaryCompareOfflineJudgePacket]:
    """讀取離線 judge packets。

    參數：
    - `packet_path`：packet JSONL 路徑。

    回傳：
    - `list[SummaryCompareOfflineJudgePacket]`：依檔案順序排列的 packet 清單。
    """

    packets: list[SummaryCompareOfflineJudgePacket] = []
    with packet_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            packets.append(SummaryCompareOfflineJudgePacket.model_validate(json.loads(stripped)))
    return packets


def load_offline_judge_decisions(
    *,
    decision_path: Path,
) -> dict[str, SummaryCompareOfflineJudgeDecision]:
    """讀取離線 judge 回填結果並以 packet id 建索引。

    參數：
    - `decision_path`：decision JSONL 路徑。

    回傳：
    - `dict[str, SummaryCompareOfflineJudgeDecision]`：`packet_id -> decision` 對照表。
    """

    decisions: dict[str, SummaryCompareOfflineJudgeDecision] = {}
    with decision_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            decision = SummaryCompareOfflineJudgeDecision.model_validate(json.loads(stripped))
            decisions[decision.packet_id] = decision
    return decisions
