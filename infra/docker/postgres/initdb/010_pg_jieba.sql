-- 建立 retrieval foundation 需要的 extensions 與 text search config。
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_jieba;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_ts_config
        WHERE cfgname = 'deep_agent_jieba'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION deep_agent_jieba (COPY = jiebacfg);
    END IF;
END
$$;
