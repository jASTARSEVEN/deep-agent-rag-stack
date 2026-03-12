# syntax=docker/dockerfile:1.5

# 提供未來 pg_jieba 固定版本掛勾的 Postgres 基底映像。
FROM pgvector/pgvector:pg16

# 預留給未來 pg_jieba 編譯與版本固定使用的 build arguments。
ARG PG_JIEBA_REPO_URL
ARG PG_JIEBA_REF

# 用來記錄未來 extension 建置輸入的預留執行期 metadata。
ENV PG_JIEBA_REPO_URL=${PG_JIEBA_REPO_URL}
ENV PG_JIEBA_REF=${PG_JIEBA_REF}

# 本輪只需要可啟動的 Postgres 映像；pg_jieba 編譯刻意延後。
