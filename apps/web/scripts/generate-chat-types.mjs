/** 此腳本會從 API chat/runtime contract schema 產生前端 TypeScript types。 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";


/** 產生後檔案使用的固定標頭。 */
const GENERATED_HEADER = [
  "/**",
  " * 此檔案由 `npm run generate:chat-types` 自動產生。",
  " * 請勿手動編輯；若 API chat contract 變更，請重新產生。",
  " */",
  "",
].join("\n");

/** chat contract schema 匯出腳本模組路徑。 */
const CHAT_CONTRACT_EXPORT_MODULE = "app.scripts.export_chat_contracts";

/** 需要在 generated 檔案額外輸出的別名對照。 */
const CHAT_ALIAS_MAP = [
  ["ChatCitationRegion", 'components["schemas"]["ChatCitationRegion"]'],
  ["ChatDisplayCitation", 'components["schemas"]["ChatDisplayCitation"]'],
  ["ChatAnswerBlock", 'components["schemas"]["ChatAnswerBlock"]'],
  ["ChatCitation", 'components["schemas"]["ChatCitation"]'],
  ["ChatAssembledContext", 'components["schemas"]["ChatAssembledContext"]'],
  ["ChatTrace", 'components["schemas"]["ChatTrace"]'],
  ["ChatMessageArtifact", 'components["schemas"]["ChatMessageArtifact"]'],
  ["ChatRuntimeResult", 'components["schemas"]["ChatRuntimeResult"]'],
  ["ChatMessageArtifactPayload", 'components["schemas"]["ChatMessageArtifactPayload"]'],
  ["ChatPhaseEventPayload", 'components["schemas"]["ChatPhaseEventPayload"]'],
  ["ChatToolCallEventPayload", 'components["schemas"]["ChatToolCallEventPayload"]'],
  ["ChatTokenEventPayload", 'components["schemas"]["ChatTokenEventPayload"]'],
  ["ChatReferencesEventPayload", 'components["schemas"]["ChatReferencesEventPayload"]'],
  ["AgentToolPayload", 'components["schemas"]["AgentToolPayload"]'],
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
 * @returns {string} `src/generated/chat.ts` 絕對路徑。
 */
function resolveOutputPath() {
  return path.resolve(import.meta.dirname, "../src/generated/chat.ts");
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

  throw new Error("找不到可用的 Python interpreter，無法匯出 chat contract schema。");
}


/**
 * 執行 chat contract export script，並回傳暫存 JSON 路徑。
 *
 * @returns {string} 暫存 chat contract JSON 檔案路徑。
 */
function exportChatContractToTempFile() {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "deep-agent-chat-contract-"));
  const chatContractPath = path.join(tempDirectory, "chat-contract.json");
  const python = resolvePythonCommand();

  execFileSync(
    python.command,
    [
      ...python.argsPrefix,
      "-m",
      CHAT_CONTRACT_EXPORT_MODULE,
      "--output",
      chatContractPath,
    ],
    {
      cwd: resolveApiWorkingDirectory(),
      stdio: "inherit",
    },
  );

  return chatContractPath;
}


/**
 * 產生 convenience alias 區塊。
 *
 * @returns {string} 產生後的 alias TypeScript 內容。
 */
function buildAliasBlock() {
  const aliasLines = CHAT_ALIAS_MAP.map(([aliasName, target]) => `export type ${aliasName} = ${target};`);
  return [
    "",
    "/** 以產品語意命名的 chat/runtime contract aliases。 */",
    ...aliasLines,
    "",
  ].join("\n");
}


/**
 * 呼叫 openapi-typescript 產生基礎型別內容。
 *
 * @param {string} contractPath chat contract JSON 檔案路徑。
 * @returns {string} raw generated TypeScript 內容。
 */
function generateRawTypes(contractPath) {
  const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";
  return execFileSync(
    npxCommand,
    ["openapi-typescript", contractPath, "--alphabetize"],
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
 * @returns {string} 最終要寫入 `chat.ts` 的完整內容。
 */
function buildGeneratedOutput() {
  const contractPath = exportChatContractToTempFile();
  const rawGeneratedTypes = generateRawTypes(contractPath).trim();
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
      throw new Error("Chat generated types 已與目前 API chat contract 不一致，請執行 `npm run generate:chat-types`。");
    }
    return;
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, nextContent, "utf-8");
}


/**
 * 執行 chat type generation 主流程。
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
