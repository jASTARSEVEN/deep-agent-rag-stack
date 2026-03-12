# Phase 1 驗證手冊

## 文件目的

此文件整理 `Phase 1 — Auth & Platform Foundations` 已完成部分的實際驗證流程。  
目標是證明以下鏈路在本機可運作：

1. Keycloak 使用者登入
2. 取得 JWT access token
3. 驗證 token 內含 `sub` 與 `groups`
4. 呼叫 `GET /auth/context`
5. 呼叫 `GET /areas/{area_id}/access-check`

此文件描述的是 **目前 repo 狀態下已驗證成功的最小流程**，不是未來正式產品 UX。

## 前置條件

### 服務已啟動

在專案根目錄執行：

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

確認以下服務可用：
- Keycloak：`http://localhost:18080`
- API：`http://localhost:18000`
- PostgreSQL：`localhost:15432`

### Keycloak 已完成自動匯入

本 repo 目前會在 Keycloak 第一次啟動時自動匯入 `deep-agent-dev` realm。  
請確認 `keycloak-db` 是全新 volume，或使用預設 import 後的環境。

預設身份資料如下：

- client：`deep-agent-web`
- groups：
  - `/reader`
  - `/maintainer`
  - `/admin`
- users：
  - `alice / alice123`：`/reader`
  - `bob / bob123`：`/maintainer`
  - `carol / carol123`：`/admin`
  - `dave / dave123`：無群組
  - `erin / erin123`：`/reader` + `/maintainer`

`deep-agent-web` 會預設帶有 `Group Membership` mapper，設定如下：
- `Token Claim Name = groups`
- `Add to access token = ON`
- `Full group path = ON`

### API schema 已建立

在容器內執行 migration：

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec api alembic upgrade head
```

成功後可確認資料表：

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec -T postgres \
  psql -U app -d deep_agent_rag -c "\dt"
```

至少應看到：
- `alembic_version`
- `areas`
- `area_user_roles`
- `area_group_roles`
- `documents`
- `ingest_jobs`

## 步驟 1：取得 access token

使用 password grant 從主機對 Keycloak 取得 token。  
以下先以 `alice` 驗證 `reader` 情境：

```bash
curl -sS -X POST "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=deep-agent-web" \
  -d "grant_type=password" \
  -d "username=alice" \
  -d "password=alice123"
```

建議把 `access_token` 存成 shell 變數：

```bash
ACCESS_TOKEN=$(
  curl -sS -X POST "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=alice" \
    -d "password=alice123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)
```

## 步驟 2：解 JWT payload，確認 `sub` 與 `groups`

```bash
python - <<'PY'
import base64
import json
import os

token = os.environ["ACCESS_TOKEN"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
decoded = json.loads(base64.urlsafe_b64decode(payload))
print(json.dumps(decoded, indent=2, ensure_ascii=False))
print("\nsub =", decoded.get("sub"))
print("groups =", decoded.get("groups"))
PY
```

成功時應至少看到：

```json
{
  "sub": "22493f0d-f917-4b38-979c-c93936e8ea79",
  "groups": ["/reader"]
}
```

若沒有 `groups`，代表 Keycloak import 未成功，或 `Group Membership` mapper 被修改。

## 步驟 3：呼叫 `GET /auth/context`

```bash
curl -sS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:18000/auth/context
```

預期結果：

```json
{
  "sub": "22493f0d-f917-4b38-979c-c93936e8ea79",
  "groups": ["/reader"],
  "authenticated": true
}
```

這表示：
- API 已成功驗證 JWT
- API 已成功解析 `sub`
- API 已成功解析 `groups`

## 步驟 3-1：驗證其他預設身份資料

### `bob` 應回傳 `maintainer`

```bash
BOB_ACCESS_TOKEN=$(
  curl -sS -X POST "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=bob" \
    -d "password=bob123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)

curl -sS \
  -H "Authorization: Bearer $BOB_ACCESS_TOKEN" \
  http://localhost:18000/auth/context
```

預期 `groups` 包含：

```json
["/maintainer"]
```

### `carol` 應回傳 `admin`

```bash
CAROL_ACCESS_TOKEN=$(
  curl -sS -X POST "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=carol" \
    -d "password=carol123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)

curl -sS \
  -H "Authorization: Bearer $CAROL_ACCESS_TOKEN" \
  http://localhost:18000/auth/context
```

預期 `groups` 包含：

```json
["/admin"]
```

### `dave` 應視為無群組

```bash
DAVE_ACCESS_TOKEN=$(
  curl -sS -X POST "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=dave" \
    -d "password=dave123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)

curl -sS \
  -H "Authorization: Bearer $DAVE_ACCESS_TOKEN" \
  http://localhost:18000/auth/context
```

預期 `groups` 是空陣列：

```json
[]
```

### `erin` 應同時帶有 `/reader` 與 `/maintainer`

```bash
ERIN_ACCESS_TOKEN=$(
  curl -sS -X POST "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=erin" \
    -d "password=erin123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)

curl -sS \
  -H "Authorization: Bearer $ERIN_ACCESS_TOKEN" \
  http://localhost:18000/auth/context
```

預期 `groups` 同時包含：

```json
["/reader", "/maintainer"]
```

## 步驟 4：建立最小測試資料

目前 `Phase 1` 尚未實作 area CRUD 與 access management API，  
因此需要先直接寫入測試資料。

建立測試 area：

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec -T postgres \
  psql -U app -d deep_agent_rag -c "
  insert into areas (id, name, description, created_at, updated_at)
  values (
    '11111111-1111-1111-1111-111111111111',
    'Demo Area',
    'Phase 1 access check demo',
    now(),
    now()
  )
  on conflict (id) do update
  set name = excluded.name,
      description = excluded.description,
      updated_at = now();
"
```

建立 `/reader -> reader` access mapping：

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec -T postgres \
  psql -U app -d deep_agent_rag -c "
  insert into area_group_roles (id, area_id, group_path, role, created_at)
  values (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    '/reader',
    'reader',
    now()
  )
  on conflict on constraint uq_area_group_roles_area_group_path do update
  set role = excluded.role;
"
```

## 步驟 5：呼叫 `GET /areas/{area_id}/access-check`

```bash
curl -sS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:18000/areas/11111111-1111-1111-1111-111111111111/access-check
```

預期結果：

```json
{
  "area_id": "11111111-1111-1111-1111-111111111111",
  "effective_role": "reader"
}
```

這表示：
- API 已從 JWT 取出 `groups`
- API 已從 SQL 取出 `area_group_roles`
- effective role 已正確計算
- deny-by-default 條件下，已授權路徑可正常通過

## 反向驗證

若 user 不在 `/reader`，或 `area_group_roles` 沒有對應關聯，再打同一支 API：

```bash
curl -i \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:18000/areas/11111111-1111-1111-1111-111111111111/access-check
```

應回 `404`，不是 `403`。  
這是刻意的 deny-by-default 設計，用來避免暴露受保護資源是否存在。

## 本文件驗證到的範圍

已驗證：
- Keycloak 可簽發 JWT
- JWT 包含 `sub`
- JWT 包含 `groups`
- API 可驗證 JWT
- API 可回傳 `/auth/context`
- API 可用 group-based role 回傳 `/areas/{area_id}/access-check`

尚未驗證：
- area CRUD 正式 API
- access management 正式 API
- upload / retrieval / chat
- worker ingestion flow

## 疑難排解

### `401 Unauthorized`

常見原因：
- token 的 `iss` 與 API `KEYCLOAK_ISSUER` 不一致
- token 已過期
- token 內沒有合法的 `sub`

請確認 token 是從主機位址 `http://localhost:18080` 取得，而不是從容器內 `http://localhost:8080` 取得。

### token 裡沒有 `groups`

請先確認：
- `keycloak-db` volume 是否為全新，或已經使用預設 import 初始化
- `deep-agent-dev-realm.json` 內的 `Group Membership` mapper 是否被修改
- `claim name = groups`
- `access token claim = true`
- `full path = true`

### `access-check` 回 `404`

請確認：
- user 確實在 `/reader`
- token payload 確實有 `"groups": ["/reader"]`
- `area_group_roles` 已寫入 `/reader -> reader`
- `area_id` 與測試資料一致
