/** 此腳本會從 API OpenAPI schema 產生前端 REST contract types。 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";


/** 產生後檔案使用的固定標頭。 */
const GENERATED_HEADER = [
  "/**",
  " * 此檔案由 `npm run generate:rest-types` 自動產生。",
  " * 請勿手動編輯；若 API schema 變更，請重新產生。",
  " */",
  "",
].join("\n");

/** OpenAPI schema 匯出腳本模組路徑。 */
const OPENAPI_EXPORT_MODULE = "app.scripts.export_openapi";

/** 需要在 generated 檔案額外輸出的別名對照。 */
const REST_ALIAS_MAP = [
  ["ApiHealthPayload", 'components["schemas"]["HealthResponse"]'],
  ["AuthContextPayload", 'components["schemas"]["AuthContextResponse"]'],
  ["UserSearchResult", 'components["schemas"]["UserSearchResult"]'],
  ["GroupSearchResult", 'components["schemas"]["GroupSearchResult"]'],
  ["AreaRole", 'components["schemas"]["Role"]'],
  ["AreaSummary", 'components["schemas"]["AreaSummaryResponse"]'],
  ["AreaListPayload", 'components["schemas"]["AreaListResponse"]'],
  ["AccessUserEntry", 'components["schemas"]["AccessUserEntry"]'],
  ["AccessGroupEntry", 'components["schemas"]["AccessGroupEntry"]'],
  ["AreaAccessPayload", 'components["schemas"]["AreaAccessManagementResponse"]'],
  ["CreateAreaPayload", 'components["schemas"]["CreateAreaRequest"]'],
  ["UpdateAreaPayload", 'components["schemas"]["UpdateAreaRequest"]'],
  ["ReplaceAreaAccessPayload", 'components["schemas"]["ReplaceAreaAccessRequest"]'],
  ["DocumentStatus", 'components["schemas"]["DocumentStatus"]'],
  ["IngestJobStatus", 'components["schemas"]["IngestJobStatus"]'],
  ["ChunkSummary", 'components["schemas"]["ChunkSummary"]'],
  ["DocumentSummary", 'components["schemas"]["DocumentSummary"]'],
  ["IngestJobSummary", 'components["schemas"]["IngestJobSummary"]'],
  ["DocumentListPayload", 'components["schemas"]["DocumentListResponse"]'],
  ["UploadDocumentPayload", 'components["schemas"]["UploadDocumentResponse"]'],
  ["ReindexDocumentPayload", 'components["schemas"]["ReindexDocumentResponse"]'],
  ["PreviewChunk", 'components["schemas"]["DocumentPreviewChunk"]'],
  ["PreviewRegion", 'components["schemas"]["PreviewRegion"]'],
  ["DocumentPreviewPayload", 'components["schemas"]["DocumentPreviewResponse"]'],
  ["ChatSessionSummary", 'components["schemas"]["ChatSessionSummaryResponse"]'],
  ["ChatSessionListPayload", 'components["schemas"]["ChatSessionListResponse"]'],
  ["RegisterChatSessionPayload", 'components["schemas"]["RegisterChatSessionRequest"]'],
  ["UpdateChatSessionPayload", 'components["schemas"]["UpdateChatSessionRequest"]'],
  ["EvaluationQueryType", 'components["schemas"]["EvaluationQueryType"]'],
  ["EvaluationLanguage", 'components["schemas"]["EvaluationLanguage"]'],
  ["EvaluationProfile", 'components["schemas"]["EvaluationProfile"]'],
  ["CreateEvaluationDatasetPayload", 'components["schemas"]["CreateEvaluationDatasetRequest"]'],
  ["CreateEvaluationItemPayload", 'components["schemas"]["CreateEvaluationItemRequest"]'],
  ["MarkEvaluationSpanPayload", 'components["schemas"]["MarkEvaluationSpanRequest"]'],
  ["RunEvaluationDatasetPayload", 'components["schemas"]["RunEvaluationDatasetRequest"]'],
  ["EvaluationDatasetSummary", 'components["schemas"]["EvaluationDatasetSummary"]'],
  ["EvaluationItemSpan", 'components["schemas"]["EvaluationItemSpanResponse"]'],
  ["EvaluationItemSummary", 'components["schemas"]["EvaluationItemSummary"]'],
  ["EvaluationStageCandidate", 'components["schemas"]["EvaluationStageCandidate"]'],
  ["EvaluationCandidateStage", 'components["schemas"]["EvaluationCandidateStageResponse"]'],
  ["EvaluationDocumentSearchHit", 'components["schemas"]["EvaluationDocumentSearchHit"]'],
  ["EvaluationCandidatePreviewPayload", 'components["schemas"]["EvaluationCandidatePreviewResponse"]'],
  ["EvaluationPreviewDebugPayload", 'components["schemas"]["EvaluationPreviewDebugRequest"]'],
  ["EvaluationQueryRoutingDetail", 'components["schemas"]["EvaluationQueryRoutingDetail"]'],
  ["EvaluationSelectionDetail", 'components["schemas"]["EvaluationSelectionDetail"]'],
  ["EvaluationPerQueryStageDetail", 'components["schemas"]["EvaluationPerQueryStageDetail"]'],
  ["EvaluationPerQueryDetail", 'components["schemas"]["EvaluationPerQueryDetail"]'],
  ["EvaluationRunStatus", 'components["schemas"]["EvaluationRunStatus"]'],
  ["EvaluationStageMetricSummary", 'components["schemas"]["EvaluationStageMetricSummary"]'],
  ["EvaluationSummaryByDimension", 'components["schemas"]["EvaluationSummaryByDimension"]'],
  ["EvaluationRunSummary", 'components["schemas"]["EvaluationRunSummary"]'],
  ["EvaluationRunReportPayload", 'components["schemas"]["EvaluationRunReportResponse"]'],
  ["EvaluationDatasetDetailPayload", 'components["schemas"]["EvaluationDatasetDetailResponse"]'],
];


/**
 * 回傳目前 repo 根目錄。
 *
 * @returns {string} repo 根目錄絕對路徑。
 */
function resolveRepoRoot() {
  return path.resolve(import.meta.dirname, "../../..");
}


/**
 * 回傳 API 模組工作目錄。
 *
 * @returns {string} `apps/api` 絕對路徑。
 */
function resolveApiWorkingDirectory() {
  return path.resolve(import.meta.dirname, "../../api");
}


/**
 * 回傳 generated type 輸出路徑。
 *
 * @returns {string} `src/generated/rest.ts` 絕對路徑。
 */
function resolveOutputPath() {
  return path.resolve(import.meta.dirname, "../src/generated/rest.ts");
}


/**
 * 回傳目前可用的 Python 指令。
 *
 * @returns {{ command: string, argsPrefix: string[] }} Python 執行設定。
 */
function resolvePythonCommand() {
  const repoRoot = resolveRepoRoot();
  const candidates = process.platform === "win32"
    ? [
        path.join(repoRoot, ".venv", "Scripts", "python.exe"),
        "python",
        "py",
      ]
    : [
        path.join(repoRoot, ".venv", "bin", "python"),
        "python3",
        "python",
      ];

  for (const candidate of candidates) {
    if (path.isAbsolute(candidate) && fs.existsSync(candidate)) {
      return { command: candidate, argsPrefix: [] };
    }
    try {
      const args = candidate === "py" ? ["-3", "--version"] : ["--version"];
      execFileSync(candidate, args, { stdio: "ignore" });
      return {
        command: candidate,
        argsPrefix: candidate === "py" ? ["-3"] : [],
      };
    } catch {
      continue;
    }
  }

  throw new Error("找不到可用的 Python interpreter，無法匯出 OpenAPI schema。");
}


/**
 * 執行 OpenAPI export script，並回傳暫存 JSON 路徑。
 *
 * @returns {string} 暫存 OpenAPI JSON 檔案路徑。
 */
function exportOpenApiToTempFile() {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "deep-agent-openapi-"));
  const openApiPath = path.join(tempDirectory, "openapi.json");
  const python = resolvePythonCommand();

  execFileSync(
    python.command,
    [
      ...python.argsPrefix,
      "-m",
      OPENAPI_EXPORT_MODULE,
      "--output",
      openApiPath,
    ],
    {
      cwd: resolveApiWorkingDirectory(),
      stdio: "inherit",
    },
  );

  return openApiPath;
}


/**
 * 產生 convenience alias 區塊。
 *
 * @returns {string} 產生後的 alias TypeScript 內容。
 */
function buildAliasBlock() {
  const aliasLines = REST_ALIAS_MAP.map(([aliasName, target]) => `export type ${aliasName} = ${target};`);
  return [
    "",
    "/** 以產品語意命名的 REST contract aliases。 */",
    ...aliasLines,
    "",
  ].join("\n");
}


/**
 * 呼叫 openapi-typescript 產生基礎型別內容。
 *
 * @param {string} openApiPath OpenAPI JSON 檔案路徑。
 * @returns {string} raw generated TypeScript 內容。
 */
function generateRawTypes(openApiPath) {
  const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";
  return execFileSync(
    npxCommand,
    ["openapi-typescript", openApiPath, "--alphabetize"],
    {
      cwd: path.resolve(import.meta.dirname, ".."),
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
}


/**
 * 組裝最終 generated file 內容。
 *
 * @returns {string} 最終要寫入 `rest.ts` 的完整內容。
 */
function buildGeneratedOutput() {
  const openApiPath = exportOpenApiToTempFile();
  const rawGeneratedTypes = generateRawTypes(openApiPath).trim();
  return `${GENERATED_HEADER}${rawGeneratedTypes}\n${buildAliasBlock()}`;
}


/**
 * 寫入 generated file，或在 check mode 下驗證是否有 drift。
 *
 * @param {string} nextContent 新產生的檔案內容。
 * @param {boolean} checkOnly 是否僅檢查不寫檔。
 * @returns {void}
 */
function writeOrCheckOutput(nextContent, checkOnly) {
  const outputPath = resolveOutputPath();
  const currentContent = fs.existsSync(outputPath) ? fs.readFileSync(outputPath, "utf-8") : null;

  if (checkOnly) {
    if (currentContent !== nextContent) {
      throw new Error("REST generated types 已與目前 API OpenAPI schema 不一致，請執行 `npm run generate:rest-types`。");
    }
    return;
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, nextContent, "utf-8");
}


/**
 * 執行 REST type generation 主流程。
 *
 * @param {{ checkOnly: boolean }} options 腳本執行選項。
 * @returns {void}
 */
function run(options) {
  const nextContent = buildGeneratedOutput();
  writeOrCheckOutput(nextContent, options.checkOnly);
}


/**
 * 解析 CLI 旗標。
 *
 * @returns {{ checkOnly: boolean }} 解析後選項。
 */
function parseCliOptions() {
  return {
    checkOnly: process.argv.includes("--check"),
  };
}


/**
 * 腳本主入口。
 *
 * @returns {number} 結束碼。
 */
function main() {
  try {
    run(parseCliOptions());
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    return 1;
  }
}


process.exitCode = main();
