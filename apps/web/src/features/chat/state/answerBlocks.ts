/** Chat answer block 的前端 fallback parser。 */

import type { ChatAnswerBlock, ChatContextReference, ChatDisplayCitation } from "../../../lib/types";


/** 回答中的 citation marker，例如 `[[C1]]` 或 `[[C1,C2]]`。 */
const CITATION_MARKER_PATTERN = /\[\[(?<labels>C\d+(?:\s*,\s*C\d+)*)\]\]/g;


/**
 * 依既有 citations 建立 label 對照表。
 *
 * @param citations 當前回答可用的 citation metadata。
 * @returns 以 `context_label` 為 key 的查找表。
 */
function buildCitationLookup(citations: ChatContextReference[]): Map<string, ChatDisplayCitation> {
  return new Map(
    citations.map((citation) => [
      citation.context_label,
      {
        context_index: citation.context_index,
        context_label: citation.context_label,
        document_id: citation.document_id,
        document_name: citation.document_name,
        heading: citation.heading,
      },
    ]),
  );
}


/**
 * 將原始文字中的 citation marker 解析為 answer blocks。
 *
 * @param answer 原始回答文字。
 * @param citations 當前回答可用的 citation metadata。
 * @returns 清理後文字與結構化 answer blocks。
 */
export function deriveAnswerBlocksFromText(
  answer: string,
  citations: ChatContextReference[],
): { cleanAnswer: string; answerBlocks: ChatAnswerBlock[] } {
  const trimmedAnswer = answer.trim();
  if (!trimmedAnswer) {
    return { cleanAnswer: "", answerBlocks: [] };
  }

  const citationLookup = buildCitationLookup(citations);
  const rawBlocks = trimmedAnswer.split(/\n\s*\n/);
  const answerBlocks: ChatAnswerBlock[] = [];

  rawBlocks.forEach((rawBlock) => {
    const labels: string[] = [];
    const cleanedText = rawBlock
      .replace(CITATION_MARKER_PATTERN, (_, labelsGroup: string) => {
        labelsGroup
          .split(",")
          .map((label) => label.trim())
          .filter(Boolean)
          .forEach((label) => {
            if (!labels.includes(label)) {
              labels.push(label);
            }
          });
        return "";
      })
      .replace(/[ \t]{2,}/g, " ")
      .trim();

    if (!cleanedText) {
      return;
    }

    const displayCitations = labels
      .map((label) => citationLookup.get(label))
      .filter((citation): citation is ChatDisplayCitation => citation !== undefined);

    answerBlocks.push({
      text: cleanedText,
      citation_context_indices: displayCitations.map((citation) => citation.context_index),
      display_citations: displayCitations,
    });
  });

  if (answerBlocks.length > 0) {
    return {
      cleanAnswer: answerBlocks.map((block) => block.text).join("\n\n"),
      answerBlocks,
    };
  }

  const cleanAnswer = trimmedAnswer.replace(CITATION_MARKER_PATTERN, "").trim() || trimmedAnswer;
  return {
    cleanAnswer,
    answerBlocks: [
      {
        text: cleanAnswer,
        citation_context_indices: [],
        display_citations: [],
      },
    ],
  };
}


/**
 * 優先使用後端 `answer_blocks`；若缺失或不完整，則回退為前端 marker parser。
 *
 * @param answer 原始回答文字。
 * @param answerBlocks 後端傳來的結構化 blocks。
 * @param citations 當前回答可用的 citation metadata。
 * @returns 清理後文字與可顯示的 answer blocks。
 */
export function resolveAnswerBlocks(
  answer: string,
  answerBlocks: ChatAnswerBlock[],
  citations: ChatContextReference[],
): { cleanAnswer: string; answerBlocks: ChatAnswerBlock[] } {
  const hasUsableBlocks = answerBlocks.some((block) => block.text.trim().length > 0);
  const textContainsMarker = CITATION_MARKER_PATTERN.test(answer);
  CITATION_MARKER_PATTERN.lastIndex = 0;

  if (hasUsableBlocks && !textContainsMarker) {
    return {
      cleanAnswer: answer.trim(),
      answerBlocks,
    };
  }

  return deriveAnswerBlocksFromText(answer, citations);
}
