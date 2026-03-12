# worker-agent

## 目的
負責背景 ingest 與索引流程，包含 parsing、chunking、embeddings、FTS `tsvector` 生成、狀態轉換與 reindex 流程。

## 負責範圍
- Celery tasks
- ingest job lifecycle
- 依副檔名選擇 loader
- chunking pipeline
- embedding 生成
- 使用 pg_jieba 相容策略建立 FTS `tsvector`
- 寫入 `document_chunks`
- document / job status 更新
- retry / reindex 流程
- 處理進度與失敗回報

## 關鍵業務規則
- 上傳後會建立 `documents` 與 `ingest_jobs`
- 狀態生命週期：`uploaded -> processing -> ready | failed`
- 只有 ready 文件可被查詢
- 候選數量與 chunk 長度要受控，避免 rerank 成本失控
- OCR 不在範圍內
- 僅支援 PDF、DOCX、TXT/MD、PPTX、HTML

## 必做事項
- 狀態轉換要明確，實務上盡量做到 idempotent。
- 對 maintainer / admin 提供可排錯的失敗原因。
- 正確保留 `knowledge_area_id`、`document_id`、`chunk_index` 與 metadata。
- chunk schema 必須能支援 vector recall、FTS recall 與 citations。
- 記錄外部整合點與失敗模式。

## 禁止事項
- 不要加入 OCR 或掃描 PDF fallback。
- 在必要 chunk / index 寫入完成前，不可進入 ready。
- 不要省略 citations 所需 metadata。
- 不要讓 pipeline 假設藏在程式碼裡而沒有 docstring。

## 實作偏好
- 將 loader selection 獨立。
- chunking 與 indexing 步驟要可分開測試。
- 優先使用可預期的狀態轉換。
- 讓 reindex 流程明確且安全。

## 完成標準
- 支援的檔案型別可端到端處理
- 狀態轉換已驗證
- 失敗可觀測
- 索引輸出與檢索流程相容
- 若 env 或流程有變更，README 必須更新
