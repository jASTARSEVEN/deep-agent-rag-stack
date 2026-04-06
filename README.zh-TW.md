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

目前固定 baseline 為 `2026-04-05` 的 `production_like_v1` snapshot。

| Dataset | 語系 | Recall@10 | nDCG@10 | MRR@10 | 角色定位 |
| --- | --- | ---: | ---: | ---: | --- |
| `dureader-robust-curated-v1-100` | `zh-TW` | `1.0000` | `0.9677` | `0.9570` | 近 ceiling 中文 sanity check |
| `msmarco-curated-v1-100` | `en` | `1.0000` | `0.9674` | `0.9550` | 近 ceiling passage matching sanity check |
| `drcd-curated-v1-100` | `zh-TW` | `0.9700` | `0.8650` | `0.8308` | 繁體中文 rerank 哨兵 |
| `nq-curated-v1-100` | `en` | `0.7500` | `0.7443` | `0.7425` | assembler 壓力測試 lane |
| `uda-curated-v1-pilot` | `en` | `0.8462` | `0.7333` | `0.7051` | pilot 穩定度集合 |
| `tw-insurance-rag-benchmark-v1` | `zh-TW` | `0.8667` | `0.7254` | `0.6792` | 自家領域 benchmark |
| `uda-curated-v1-100` | `en` | `0.8300` | `0.6818` | `0.6340` | same-document localization lane |
| `qasper-curated-v1-pilot` | `en` | `0.7778` | `0.5507` | `0.4844` | pilot hard set |
| `qasper-curated-v1-100` | `en` | `0.5900` | `0.3797` | `0.3142` | 主要外部 hard lane |

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
  - `OPENAI_API_KEY`，或
  - `OPENROUTER_API_KEY`，或
  - `EASYPINEX_HOST_EMBEDDING_API_KEY`
- 若目前設定的 rerank provider 需要金鑰，還需準備：
  - `COHERE_API_KEY`，或
  - `EASYPINEX_HOST_RERANK_API_KEY`
- 若要對外提供 HTTPS，需準備可連到主機的 `PUBLIC_HOST` 與 `TLS_ACME_EMAIL`

### 快速啟動

1. 複製環境變數範本。

```bash
cp .env.example .env
```

2. 編輯 `.env`。

- 本機開發可先保留預設的 `localhost` URL。
- 填入和你實際選用的 embedding / rerank provider 對應的金鑰。
- 若要啟用公開 HTTPS，而不是本機 `localhost`，請同步設定 `PUBLIC_HOST`、`PUBLIC_BASE_URL`、`WEB_PUBLIC_URL`、`API_PUBLIC_URL`、`KEYCLOAK_PUBLIC_URL` 與 `TLS_ACME_EMAIL`。

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

## Environment Variables

建議先優先檢查這幾組：

- 公開路由：`PUBLIC_HOST`、`PUBLIC_BASE_URL`、`WEB_PUBLIC_URL`、`API_PUBLIC_URL`、`KEYCLOAK_PUBLIC_URL`、`TLS_ACME_EMAIL`
- Auth：`KEYCLOAK_REALM`、`KEYCLOAK_CLIENT_ID`、`KEYCLOAK_ISSUER`、`KEYCLOAK_JWKS_URL`、`KEYCLOAK_GROUPS_CLAIM`
- 儲存與基礎設施：`POSTGRES_*`、`REDIS_URL`、`MINIO_*`、`STORAGE_BACKEND`
- Ingestion：`PDF_PARSER_PROVIDER`、`LLAMAPARSE_API_KEY`
- Retrieval：`EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`、`RERANK_PROVIDER`、`RERANK_MODEL`
- Chat 與觀測：`CHAT_PROVIDER`、`CHAT_MODEL`、`LANGSMITH_TRACING`

完整設定請以 [`.env.example`](.env.example) 為準。

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
- 若登入失敗，請重新檢查 `KEYCLOAK_PUBLIC_URL`、`VITE_KEYCLOAK_URL` 與 `PUBLIC_BASE_URL`。
- 若既有資料庫上的 retrieval 失敗，先在 API container 內重跑：

```bash
./scripts/compose.sh exec api python -m app.db.migration_runner
```

- 若 API 可用但回答品質很差或沒有內容，請確認 `.env` 內設定的 embedding / rerank provider 與實際填入的金鑰一致。

## Contact

- 作者：卓品至 Pin-Zhi Zhuo
- Email：`easypinex@gmail.com`
- GitHub：[easypinex/deep-agent-rag-stack](https://github.com/easypinex/deep-agent-rag-stack)

## License

本專案採用 `Apache-2.0` 授權，詳見 [LICENSE](LICENSE)。
