# AGENTS.md

此模組負責本機基礎設施與可重現啟動。

## 聚焦範圍
- Docker Compose
- Dockerfiles
- health checks
- pinned build inputs
- env docs
- local bootstrap

## 關鍵規則
- 固定 pg_jieba fork / commit
- 記錄 Keycloak group claim 前提
- 本機啟動要清楚可理解
- 避免不必要的平台綁定與複雜度
- 所有 function / method docstring 都必須包含參數與回傳說明
