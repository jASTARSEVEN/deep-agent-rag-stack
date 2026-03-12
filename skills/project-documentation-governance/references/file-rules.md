# 文件撰寫細則

## `Summary.md`

### 應包含
- 產品目標
- 固定技術棧
- 範圍內 / 範圍外
- 核心業務規則
- 高層需求
- 非功能性要求

### 應避免
- 當前進度
- phase 狀態
- done 清單
- 每日變動的任務規劃

## `PROJECT_STATUS.md`

### 應包含
- 專案概況
- 目前狀態
- 已完成功能
- 目前階段重點
- 下一步
- Agent Rules

### 應避免
- 長篇架構設計
- 過去已失效的討論紀錄
- 與 `ROADMAP.md` 完全重複的 phase 詳細說明

## `ROADMAP.md`

### 應包含
- phase 名稱
- 每個 phase 的目標
- 每個 phase 的範圍
- phase 狀態
- 近期建議順序

### 應避免
- 過度細碎的 task checklist
- 與 `PROJECT_STATUS.md` 的 done 清單完全重複

## `ARCHITECTURE.md`

### 應包含
- 系統組成
- 模組責任
- 關鍵原則
- 資料流
- 當前骨架與目標差異

### 應避免
- 以 phase 當主軸
- 將每日進度寫進來

## 共同規則

- 使用台灣繁體中文
- 使用一致術語：
  - Knowledge Area
  - SQL gate
  - retrieval
  - citations
  - worker
  - skeleton
- 專有名詞可保留英文，但敘述句要用繁中
- 內容應讓後續 agent 在 1 次閱讀內理解
