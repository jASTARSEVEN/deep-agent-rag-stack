# Deep Agent RAG Stack

![實際畫面預覽](actual-dashboard-live.png)
![權限管理介面測試](access-modal-test.png)
![Chunk-Aware 文件預覽](chunk-aware.png)

一個以企業約束為核心設計的可自架 NotebookLM 風格文件問答平台。

[English README](README.md)

## Purpose

Deep Agent RAG Stack 是一個可自架知識助理的 MVP。產品流程刻意收斂在五件事：

1. 使用者登入
2. 建立 Knowledge Area
3. 上傳文件
4. 背景索引處理
5. 在 area 權限邊界內提問並查看 citations

這個倉庫不是「先做聊天介面」的展示專案，而是要驗證一條更接近企業內部實際落地的完整路徑，涵蓋認證、授權、文件生命週期、檢索品質與本機可重現性。

## 背景

企業內部 RAG 系統真正困難的地方，通常不是接上 LLM，而是：

- 在檢索結果回傳前就先完成授權檢查
- 確保非 `ready` 文件永遠不會流入 chat
- 在成本可控前提下結合向量召回與關鍵字召回
- 讓整套系統可以被單一團隊在本機或自架環境重現

這個專案就是為了驗證這些限制而存在，並把它們放進同一條技術棧：`FastAPI`、`React`、`Celery`、`PostgreSQL + pgvector + PGroonga`、`MinIO`、`Keycloak`、`LangGraph` 與 `Docker Compose`。

## 專案亮點

- 以 `deny-by-default`、same-`404`、`JWT sub/groups`、effective role 合併與 SQL gate 為核心的安全邊界
- 嚴格的 ready-only 文件生命週期，只有 `status=ready` 的文件可以參與檢索與問答
- `SQL gate + vector recall + PGroonga FTS + RRF + rerank + assembled-context citations` 的混合檢索主線
- 已具備 rerank optimization：包含 parent-level candidate aggregation、`Header/Content` 組裝、provider abstraction、受控的 `RERANK_TOP_N`、受控的單文件字數上限，以及 fail-open fallback
- 支援 `PDF`、`DOCX`、`PPTX`、`XLSX`、`TXT/MD`、`HTML` 的 table-aware ingest 與 retrieval
- 一頁式 Dashboard 體驗，整合 area 導覽、串流對話、文件抽屜、權限管理與 chunk-aware 預覽
- 以 LangGraph + Deep Agents 作為 chat runtime，並保留 retrieval trace 與 tool-call 觀測能力
- benchmark-driven 的檢索治理方式，固定 baseline，並以 anti-domain-overfit 作為主線守門條件

## Retrieval 與 Evaluation 流程

### Hybrid Search

目前主線不是單純的 vector search。實際流程是：

1. 先套用 SQL gate 與 ready-only 過濾
2. 執行 vector recall 與 PGroonga full-text recall
3. 用 `RRF` 合併候選
4. 將合併後的 parent-level candidates 送進 rerank
5. 最後組裝成 chat 可用的 contexts 與 citations

### Reranker

reranker 在目前主線中是實際存在的排序層，不是未來規劃用的 placeholder。

- 先做 parent-level aggregation，降低 child-level fragmentation 對排序的干擾
- rerank 輸入會標準化成 `Header:` 與 `Content:` 格式
- provider 可切換：`self-hosted`、本機 `huggingface` rerank、`Cohere` 與 `deterministic`
- 成本受 `RERANK_TOP_N` 與 `RERANK_MAX_CHARS_PER_DOC` 控制
- provider 失敗時採 fail-open fallback，避免授權邊界與 ready-only 語意退化

### Evaluation Pipeline

retrieval 品質不是只靠回答 demo 主觀判斷，而是透過內建 evaluation pipeline 做正式量測。

1. 建立 area-scoped dataset 與 gold source spans
2. 預覽 `recall`、`rerank`、`assembled` 三階段候選
3. 用和產品同一條 retrieval pipeline 執行 benchmark profiles
4. 將新 run 與固定 baseline 比較
5. 只有通過 anti-domain-overfit 檢查的改善才保留

## 目前狀況

目前最新完成里程碑為 `Phase 7 — Retrieval Correctness Evaluation v1`。

現在的 MVP 已經具備：

- 以 Keycloak group 為基礎的 area 權限管理
- 文件上傳、刪除、reindex 與 ingest progress 追蹤
- chunk-aware 文件預覽與 citation 導航
- worker chunking 中已保留可選的 fact-heavy evidence-centric child refinement 路徑，但目前預設關閉，且不屬於 current baseline
- 以 Deep Agents 為核心的 LangGraph chat runtime
- retrieval evaluation dataset、reviewer UI、CLI runner 與 baseline compare
- 以 `Caddy` 收斂 `/`、`/api/*`、`/auth/*` 的單一公開入口模型

## Benchmark Snapshot

benchmark 分數是本專案把 retrieval 品質視為一級工程成果，而不是附屬指標。

目前固定 baseline 起點為 `2026-04-05` 的 `production_like_v1` snapshot；若外部資料集原始任務需要文件上下文，指定文件 benchmark row 會隨重跑結果更新。

針對 `qasper-*`、`uda-*` 與 `drcd-*` evaluation datasets，benchmark run 現在會使用 gold source document 作為指定文件 scope。這對齊這些資料集的原始任務契約：每題本來都綁定實際文件，而不是無 scope 的多文件查詢。

| Dataset | 語系 | Recall@10 | nDCG@10 | MRR@10 | 角色定位 |
| --- | --- | ---: | ---: | ---: | --- |
| `dureader-robust-curated-v1-100` | `zh-TW` | `1.0000` | `0.9677` | `0.9570` | 近 ceiling 中文 sanity check |
| `msmarco-curated-v1-100` | `en` | `1.0000` | `0.9674` | `0.9550` | 近 ceiling passage matching sanity check |
| `drcd-curated-v1-100` | `zh-TW` | `1.0000` | `0.8894` | `0.8517` | 指定文件繁體中文 rerank 哨兵 |
| `nq-curated-v1-100` | `en` | `0.7500` | `0.7443` | `0.7425` | assembler 壓力測試 lane |
| `tw-insurance-rag-benchmark-v1` | `zh-TW` | `0.8667` | `0.7254` | `0.6792` | 自家領域 benchmark |
| `uda-curated-v1-100` | `en` | `0.7900` | `0.6537` | `0.6104` | 指定文件 same-document localization lane |
| `qasper-curated-v1-100` | `en` | `0.9300` | `0.5905` | `0.4813` | 指定文件 scientific-paper hard lane |

README 層級保留的 benchmark 判讀如下：

- rerank 在目前主線中已是實際存在的優化層，而不只是 pipeline 圖上的規劃方塊；系統現在使用 parent-level rerank，並搭配成本 guardrails 與可觀測的 fallback 行為
- `QASPER 100` 仍是主要的外部 hard lane
- `NQ 100` 是 assembler 壓力測試 lane
- `DRCD 100` 是繁體中文 rerank 哨兵 lane
- `DuReader-robust 100` 與 `MS MARCO 100` 已接近 ceiling，較適合作為 sanity check

完整 benchmark 分析請看 [`docs/retrieval-benchmark-strategy-analysis.md`](docs/retrieval-benchmark-strategy-analysis.md)。

## How To Start

### 先備條件

- Docker 與 Docker Compose
- 若維持預設 `PDF_PARSER_PROVIDER=opendataloader`，需要 `Java 11+`
- 至少一組可用的 embedding provider 憑證，供真實 ingest 與 retrieval 使用：
  - `SELF_HOSTED_EMBEDDING_API_KEY`，或
  - `OPENAI_API_KEY`，或
  - `OPENROUTER_API_KEY`，或
- 若你要改用本機 Hugging Face 模型，而不是 hosted embedding / rerank：
  - 將 `EMBEDDING_PROVIDER=huggingface`，搭配本機 `Qwen/Qwen3-Embedding-0.6B`
  - 將 `RERANK_PROVIDER=huggingface`，搭配本機 `BAAI/bge-reranker-v2-m3`
  - 本機 Python 請安裝 `pip install -e .[dev,local-huggingface]`；Docker Compose 請先設定 `API_INSTALL_OPTIONAL_GROUPS=local-huggingface` 與 `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface`
- 若目前設定的 rerank provider 需要金鑰，還需準備：
  - `SELF_HOSTED_RERANK_API_KEY`，或
  - `COHERE_API_KEY`，或
- 若要對外提供 HTTPS，需準備可連到主機的 `PUBLIC_HOST` 與 `TLS_ACME_EMAIL`

### 快速啟動

1. 複製環境變數範本。

```bash
cp .env.example .env
```

2. 編輯 `.env`。

- 本機開發可先保留預設的 `localhost` URL。
- 填入和你實際選用的 embedding / rerank provider 對應的金鑰。
- 若使用本機 Hugging Face 模型，請記得在重建 Compose image 前同步開啟 optional dependency groups。
- 若要啟用公開 HTTPS，而不是本機 `localhost`，請同步設定 `PUBLIC_HOST`、`PUBLIC_BASE_URL` 與 `TLS_ACME_EMAIL`。

3. 啟動完整 stack。

```bash
./scripts/compose.sh up --build
```

4. 開啟本機服務。

- Web：`http://localhost`
- API health：`http://localhost/api/health`
- Keycloak：`http://localhost/auth`
- MinIO API：`http://localhost:19000`
- MinIO Console：`http://localhost:19001`

5. 驗證主流程。

- 從 Web 登入
- 建立一個 Knowledge Area
- 上傳支援的文件
- 等待文件進入 `ready`
- 提問並確認回答附帶 citations

6. 使用完後關閉 stack。

```bash
./scripts/compose.sh down
```

本機 Compose 會自動匯入開發用的 Keycloak realm。

## 直接操作的快速入口

如果你現在只是想把系統跑起來並實際玩一次，只看此章節即可。

### 本機預設帳號

本機 Compose stack 在第一次啟動時，會自動匯入固定的 Keycloak 開發 realm。

| 帳號 | 密碼 | groups | 建議用途 |
| --- | --- | --- | --- |
| `alice` | `alice123` | `/dept/hr` | 第一次互動示範最推薦 |
| `bob` | `bob123` | `/dept/finance` | 驗證跨群組權限 |
| `carol` | `carol123` | `/dept/rd` | 一般使用者示範 |
| `dave` | `dave123` | 無 | 驗證 `deny-by-default` |
| `erin` | `erin123` | `/dept/hr`, `/dept/rd` | 驗證 multi-group effective role |
| `frank` | `frank123` | `/platform/knowledge-admins` | 平台管理型測試身份 |

補充：

- Keycloak realm：`deep-agent-dev`
- Keycloak client：`deep-agent-web`
- 這些帳號來自 [`infra/keycloak/deep-agent-dev-realm.json`](infra/keycloak/deep-agent-dev-realm.json)。
- 如果你不是第一次啟動 Keycloak，之後才去改 realm import，單純重啟 container 不會套用新帳號，必須先重置 Keycloak 持久化資料。

### 怎麼使用這個應用？ 

最標準的操作路徑就是：

1. 開 `http://localhost`
2. 點 `使用 Keycloak 登入`
3. 用上表任一帳號登入
4. 進入 `/areas`
5. 如果是第一次使用，就先建立一個 Knowledge Area
6. 在該 area 上傳文件
7. 等文件狀態變成 `ready`
8. 在 chat 面板提問，並查看 citations

第一次登入後常見情況：

- 在全新系統裡，你可能會先看到沒有任何可存取 area，這是正常的。
- 最簡單的第一步就是自己建立一個 area。
- area 建立者會自動成為該 area 的 `admin`。
- 能不能看到既有 area，不只取決於是否登入成功，還取決於該 area 的 user/group access mapping。

### 5 分鐘試玩流程

如果你只想最短路徑跑一次，直接用 `alice / alice123`：

1. 用 `./scripts/compose.sh up --build` 啟動整套服務
2. 開 `http://localhost`
3. 用 `alice` 登入
4. 建立一個 area，例如 `HR Policies`
5. 上傳一個 `PDF`、`DOCX`、`TXT/MD`、`PPTX`、`HTML` 或 `XLSX` 檔案
6. 等文件從 `uploaded` 或 `processing` 變成 `ready`
7. 問一個可以直接從該文件回答的具體問題
8. 點 citations，確認右側預覽欄能對到來源內容

### 最簡單的權限驗證流程

如果你想快速理解授權模型，可以這樣操作：

1. 先用 `alice` 登入並建立一個 area
2. 在 access settings 把 `/dept/hr` 加成 `reader`
3. 登出後改用 `bob` 登入
4. `bob` 不應該看得到該 area，因為 `bob` 屬於 `/dept/finance`
5. 再改用 `dave` 登入
6. `dave` 也應該被擋下，因為 `dave` 沒有任何 group

這能直接看見兩個核心規則：

- 授權採 `deny-by-default`
- area 存取是靠 direct user role 與 Keycloak group path mapping 決定

### 我應該先用哪個帳號？

- 只想從頭到尾跑一次主流程：用 `alice`
- 想測平台管理型身份：用 `frank`
- 想測多群組使用者：用 `erin`
- 想驗證無群組使用者不會自動取得權限：用 `dave`

## Environment Variables

建議先優先檢查這幾組：

- 公開路由：`PUBLIC_HOST`、`PUBLIC_BASE_URL`、`TLS_ACME_EMAIL`、`KEYCLOAK_EXPOSE_ADMIN`
- Auth：`KEYCLOAK_REALM`、`KEYCLOAK_CLIENT_ID`、`KEYCLOAK_GROUPS_CLAIM`
- 儲存與基礎設施：`POSTGRES_*`、`REDIS_PORT`、`MINIO_*`、`STORAGE_BACKEND`
- Ingestion：`PDF_PARSER_PROVIDER`、`LLAMAPARSE_API_KEY`
- Model providers：`EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`、`RERANK_PROVIDER`、`RERANK_MODEL`
- Chat 與觀測：`CHAT_MODEL`、`LANGSMITH_TRACING`

常用 Compose 啟動設定請以 [`.env.example`](.env.example) 為準；若需要額外的 runtime-only 覆寫，請再參考 [apps/api/README.md](apps/api/README.md) 與 [apps/worker/README.md](apps/worker/README.md)。

## Main Directory Structure

- `apps/api`：FastAPI 應用、auth、RBAC、retrieval、evaluation 與 LangGraph runtime glue
- `apps/worker`：Celery ingest、parse、chunking、embedding 與 indexing
- `apps/web`：React + Tailwind Dashboard、登入流程、chat UI、文件 UI 與 evaluation UI
- `infra`：Dockerfile、Compose stack、Caddy 與 Keycloak bootstrap
- `benchmarks`：benchmark package 與 evaluation 資產
- `packages/shared`：需要時放共用型別與設定

## Public Interfaces

目前 MVP 的主要對外介面：

- Web Dashboard：`/`
- API health 與 auth context：`/api/health`、`/api/auth/context`
- Area、document、access 與 evaluation APIs：`/api/*`
- Keycloak login 與 OIDC endpoints：`/auth/*`
- 由 Web 透過 API service 消費的 LangGraph chat runtime

長期文件入口：

- 產品範圍：[Summary.md](Summary.md)
- 專案現況：[PROJECT_STATUS.md](PROJECT_STATUS.md)
- 里程碑順序：[ROADMAP.md](ROADMAP.md)
- 系統設計：[ARCHITECTURE.md](ARCHITECTURE.md)

## Troubleshooting

- 若 `./scripts/compose.sh` 一開始就失敗，先確認 repo 根目錄已建立 `.env`。
- 若 `opendataloader` 的 PDF 解析失敗，請先確認 `java -version` 可解析到 Java `11+`。
- 若登入失敗，請重新檢查 `PUBLIC_BASE_URL`，並確認 Keycloak realm 的 redirect URI 仍指向 `<PUBLIC_BASE_URL>/auth/callback` 與 `<PUBLIC_BASE_URL>/silent-check-sso.html`。
- 若既有資料庫上的 retrieval 失敗，先在 API container 內重跑：

```bash
./scripts/compose.sh exec api python -m app.db.migration_runner
```

- 若 API 可用但回答品質很差或沒有內容，請確認 `.env` 內設定的 embedding / rerank provider 與實際填入的金鑰一致。
- 若 `EMBEDDING_PROVIDER=huggingface` 或 `RERANK_PROVIDER=huggingface` 啟動失敗，請先確認是否已安裝 `local-huggingface` optional 依賴，且模型可正常下載或讀取本機路徑。

## Contact

- 作者：卓品至 Pin-Zhi Zhuo
- Email：`easypinex@gmail.com`
- GitHub：[easypinex/deep-agent-rag-stack](https://github.com/easypinex/deep-agent-rag-stack)

## License

本專案採用 `Apache-2.0` 授權，詳見 [LICENSE](LICENSE)。
