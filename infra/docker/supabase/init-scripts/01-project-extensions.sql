-- 在 Supabase 映像降權 postgres 前，先安裝本專案 retrieval 需要的 extension。

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;
