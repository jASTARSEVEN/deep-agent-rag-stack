---
name: project-documentation-governance
description: Use this skill when creating or updating Summary.md, PROJECT_STATUS.md, ROADMAP.md, or ARCHITECTURE.md in this repository, or when you need to decide what belongs in each file and enforce the writing rules for these project-level documents.
---

# Project Documentation Governance

此 skill 專門用來維護本專案的四份專案級文件：
- `Summary.md`
- `PROJECT_STATUS.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`

只有當任務與這四份文件的建立、更新、拆分責任、撰寫規則有關時才使用。

## 先讀哪些檔案

1. 先讀根目錄 `AGENTS.md`
2. 再讀 `PROJECT_STATUS.md`
3. 再讀 `ROADMAP.md`
4. 再讀 `ARCHITECTURE.md`
5. 若需要產品/架構背景，再讀 `Summary.md`

若這些文件尚未存在，先依本 skill 建立初版。

## 四份文件的責任分工

### `Summary.md`
- 用來回答「這個專案要做什麼」
- 必須記錄：
  - 產品目標
  - 固定技術棧
  - 範圍內 / 範圍外
  - 核心業務規則
  - 高層需求與非功能性要求
- 應偏向「長期穩定的產品背景」
- 不要把目前 phase、進度、done 清單寫進這裡

### `PROJECT_STATUS.md`
- 用來回答「現在做到哪」
- 必須記錄：
  - 目前 phase
  - 已完成內容
  - Current Focus
  - 下一步
  - Agent Rules
- 應偏向「當前事實」
- 內容要可被 agent 快速讀懂，不要寫成長篇設計文件

### `ROADMAP.md`
- 用來回答「接下來按什麼順序做」
- 必須記錄：
  - phases
  - 每個 phase 的目標
  - 每個 phase 的內容
  - phase 狀態
  - 近期建議順序
- 應偏向「階段規劃」
- 不要塞進過多目前執行細節

### `ARCHITECTURE.md`
- 用來回答「系統應該怎麼設計」
- 必須記錄：
  - 系統組成
  - 模組責任
  - 核心架構原則
  - 預期資料流
  - 目前骨架與目標架構差異
- 應偏向「設計與結構」
- 不要把 phase 進度寫進這裡

## 撰寫規則

- 使用台灣繁體中文
- 標題清楚，段落短
- 優先寫「事實、邊界、責任」，避免空泛口號
- 不要讓四份文件內容大幅重複
- 有變更時，只更新受影響的文件
- 若是產品範圍、核心需求、固定技術棧改變，至少要更新：
  - `Summary.md`
- 若是 phase 完成，至少要更新：
  - `PROJECT_STATUS.md`
  - `ROADMAP.md`
- 若是設計改變，至少要更新：
  - `ARCHITECTURE.md`
  - 視情況更新 `PROJECT_STATUS.md`

## 更新判斷規則

- 「產品目標、範圍、固定技術棧、核心規則改了」：更新 `Summary.md`
- 「這輪做完什麼」：更新 `PROJECT_STATUS.md`
- 「下一階段順序改了」：更新 `ROADMAP.md`
- 「授權模型、資料流、模組責任改了」：更新 `ARCHITECTURE.md`
- 若同時有產品、進度與設計變更，四份文件都可能要更新

## 實作時的限制

- 不要把四份文件混成一份
- 不要在沒有產品定義變更時重寫整份 `Summary.md`
- 不要在沒有狀態變更時重寫整份 `PROJECT_STATUS.md`
- 不要在沒有架構變更時重寫整份 `ARCHITECTURE.md`
- 不要把 prompt 歷史直接貼進文件
- 不要把臨時討論內容當成正式規則

## 需要更細規則時

讀 `references/file-rules.md`。
