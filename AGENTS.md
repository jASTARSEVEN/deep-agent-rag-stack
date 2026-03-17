# AGENTS.md

## 專案概述
本專案要實作一個可自架的 NotebookLM 風格文件問答平台。

核心產品流程：
1. 使用者登入
2. 建立 Knowledge Area
3. 上傳檔案
4. 背景索引處理
5. 以引用來源進行問答

## 固定技術棧
- 後端：Python + FastAPI
- 資料庫：PostgreSQL + pgvector + PGroonga (Supabase)
- 背景工作：Celery + Redis
- 物件儲存：MinIO
- 身分與授權：Keycloak
- 前端：React + Tailwind
- 檢索與流程編排：LangChain loaders、LangGraph
- LLM / rerank：OpenAI、Cohere Rerank v4
- 本機編排：Docker Compose

## 產品邊界
範圍內：
- 僅支援檔案上傳作為知識來源
- 檔案類型：PDF、DOCX、TXT/MD、PPTX、HTML
- Knowledge Area 管理
- 以 Keycloak group 為基礎的授權
- 背景索引與進度顯示
- 以 area 為範圍的問答與 citations
- SQL gate + vector recall + FTS recall + Cohere rerank

範圍外：
- NotebookLM workspace / studio 類功能
- 檔案層級 ACL
- OCR / 掃描 PDF
- 上傳期間的串流式 ingest
- `pg_trgm` 模糊搜尋
- Multi-tenant / multi-realm

## 不可妥協的業務規則
- 授權必須採用 deny-by-default。
- JWT claims 使用 `sub` 與 `groups`。
- 有效角色等於直接使用者角色與 Keycloak group 映射角色中的最大值。
- 沒有有效角色的使用者，必須在 SQL / 資料存取層被阻擋，且不得取得受保護資料。
- 只有 `status = 'ready'` 的文件可以參與檢索與問答。
- SQL gate 必須在檢索結果回傳給使用者前執行。
- 不得引入 `pg_trgm`。
- Rerank 候選數與 chunk 大小必須受控，以限制成本。

## 倉庫結構
- `apps/api`：FastAPI 應用程式
- `apps/worker`：Celery worker 與 ingest / index pipeline
- `apps/web`：React + Tailwind 前端
- `infra`：Docker Compose、Dockerfiles、基礎設施啟動設定
- `packages/shared`：必要時放共用型別或設定

## 全域工程規則
- 優先做最小、可運作、可審查的修改。
- 不要引入不必要的框架或抽象。
- 維持前後端契約一致。
- 初期實作以 MVP 為優先。
- 不要默默擴大既定產品邊界。
- 在所有授權敏感路徑保留 deny-by-default 語意。
- 安全敏感行為必須明確、可文件化、可測試。
- Python ORM 一律使用 SQLAlchemy 2 寫法；不得新增 `session.query(...)` 這類 1.x 風格 API。

## 專案級文件規則
以下四份文件是本專案的長期上下文來源，所有 agent 在規劃或實作前都必須先閱讀：
- `Summary.md`：產品背景、需求範圍、核心業務規則與固定技術選型
- `PROJECT_STATUS.md`：記錄目前做到哪、已完成內容、目前 focus、下一步
- `ROADMAP.md`：記錄 phase、里程碑、推薦實作順序
- `ARCHITECTURE.md`：記錄系統設計、模組責任、資料流與核心約束

使用規則：
- 若需要理解產品背景、需求邊界、固定技術棧與長期不易變動的業務規則，先讀 `Summary.md`。
- 開始新任務前，先確認 `PROJECT_STATUS.md` 的目前 phase 與已完成內容。
- 若要調整實作順序、phase 拆分、里程碑規劃，必須同步更新 `ROADMAP.md`。
- 若架構決策、資料流、模組責任、授權設計有變更，必須同步更新 `ARCHITECTURE.md`。
- 若產品範圍、需求邊界、固定技術選型、核心業務規則有變更，必須同步更新 `Summary.md`。
- 若完成重大里程碑或完成一輪功能交付，必須同步更新 `PROJECT_STATUS.md`。
- 不得只更新其中一份文件卻讓其餘文件失真。
- 若任務與這四份文件的建立、更新、治理有關，應使用專案級 skill：`project-documentation-governance`。

## 文件規範
每個原始碼檔案都必須遵守以下規則：
- 每個檔案都需要檔案層級說明。
- 每個 class 都要有 class docstring。
- 每個 function / method 都要有 function-level docstring，且必須包含參數說明與回傳說明。
- 每個全域變數 / module-level constant 都要有用途註解。
- 只要是類似 Model、DTO、Bean、interface、Base 的資料結構型別，其所有欄位 / 變數都必須有用途註解。
- 涉及安全、授權、SQL gate、外部整合的程式碼，必須記錄前置條件與風險。
- 除 `README.md` 外，所有的說明 / docstring / `.md` 都要使用台灣繁體中文。
- 所有對外 README 主版都必須使用英文，包含根目錄 `README.md` 與各模組的 `README.md`。
- 每一份英文 README 都必須同步維護對應的 `README.zh-TW.md`，內容需與英文版在主要資訊上保持一致，作為繁體中文版本。

## 模組 README 規範
`apps/*`、`infra/*`、`packages/*` 下的每個頂層模組都必須包含 `README.md`。

每個有自己 `pyproject.toml` 或 `package.json` 的獨立模組，也都必須包含 `README.md`。

所有模組若包含 `README.md`，也必須同步包含 `README.zh-TW.md`。

每份 README 必須包含：
- Purpose
- How to start
- Environment variables
- Main directory structure
- Public interfaces
- Troubleshooting

## 測試要求
單元測試至少涵蓋：
- effective role 計算
- deny-by-default
- `status != ready` 的文件不能被檢索
- Cohere rerank 前後的 candidate 結構
- FTS query builder 與 SQL 組裝

整合測試至少涵蓋：
- Keycloak group A 可讀 area1，group B 不可
- upload 狀態轉換 `uploaded -> processing -> ready`
- 已授權使用者可提問並取得 citations
- 未授權使用者不可看見或操作 area / document / chat
- maintainer 可刪除與 reindex 文件
- admin 可修改 access，maintainer 不可

## Agent 執行模型
任務可拆分時，使用專責 sub-agent。

主要角色：
- planner
- api-agent
- worker-agent
- web-agent
- infra-agent
- qa-security-agent

可選角色：
- ui-design-agent

## 角色邊界
- planner：拆解工作、安排順序、識別依賴；除非明確要求，否則不實作業務邏輯。
- api-agent：實作 FastAPI endpoints、auth integration、SQL gate、schemas、service logic；不負責 worker pipeline 或前端 UI。
- worker-agent：實作 loaders、chunking、embeddings、indexing、job transitions；不負責 web UI。
- web-agent：實作 React / Tailwind UI、auth flow、upload / chat UX、API integration；若非必要且已協調，不修改後端業務規則。
- infra-agent：負責 Docker Compose、Dockerfiles、startup scripts、health checks、env 文件、本機啟動流程。
- qa-security-agent：負責測試、授權驗證、誤用案例、回歸檢查與安全敏感審查。
- ui-design-agent：將 Figma 轉成資訊架構、元件清單、頁面區塊與互動備註。

## 協作指引
實作功能時建議流程：
1. planner 先定義範圍、依賴與任務切分，並顯示列出 sub-agent task split，再依 split 執行。
2. 相關實作 sub-agent 在可行時並行工作
3. qa-security-agent 驗證正確性與安全性
4. planner 或主責 agent 總結修改內容與剩餘缺口

## 避免事項
- 不要以記憶體過濾取代 SQL gate 作為主要保護模型。
- 不要透過 API 形狀或錯誤細節暴露未授權資源是否存在。
- 不要讓非 ready 文件進入檢索。
- 不要讓 web UI 緊耦合於不穩定的後端內部實作。
- 未經明確需求，不要在現有技術棧之外加新基礎設施。
