# AGENTS.md

此模組負責 FastAPI 應用程式。

## 聚焦範圍
- routes
- schemas
- auth integration
- effective role logic
- SQL gate
- documents / job / chat APIs

## 關鍵規則
- deny-by-default 是強制要求
- 只有 ready 文件可以被檢索
- admin 可管理 access，maintainer 不可
- 避免洩漏受保護資源是否存在

## 實作風格
- route 要薄，service 要清楚
- auth / security-sensitive code 需有明確 docstring
- 反向路徑測試不可少
