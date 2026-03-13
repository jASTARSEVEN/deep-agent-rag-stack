# syntax=docker/dockerfile:1.5

# 提供未來 pg_jieba 固定版本掛勾的 Postgres 基底映像。
FROM pgvector/pgvector:pg16

# 預留給未來 pg_jieba 編譯與版本固定使用的 build arguments。
ARG PG_JIEBA_REPO_URL
ARG PG_JIEBA_REF

# 用來記錄未來 extension 建置輸入的預留執行期 metadata。
ENV PG_JIEBA_REPO_URL=${PG_JIEBA_REPO_URL}
ENV PG_JIEBA_REF=${PG_JIEBA_REF}
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone "${PG_JIEBA_REPO_URL}" /tmp/pg_jieba \
    && cd /tmp/pg_jieba \
    && git checkout "${PG_JIEBA_REF}" \
    && git submodule update --init --recursive \
    && mkdir build \
    && cd build \
    && cmake -DPostgreSQL_TYPE_INCLUDE_DIR=/usr/include/postgresql/16/server .. \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/pg_jieba

RUN mkdir -p /opt/pg_jieba/dicts

COPY infra/docker/postgres/assets/jieba_dict_zh_tw.txt /opt/pg_jieba/dicts/jieba_dict_zh_tw.txt
COPY infra/docker/postgres/assets/jieba_dict_zh_tw.txt /usr/share/postgresql/16/tsearch_data/jieba_base.dict
COPY infra/docker/postgres/initdb/010_pg_jieba.sql /docker-entrypoint-initdb.d/010_pg_jieba.sql
