-- Enable Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pgroonga";

-- Enums
CREATE TYPE role_enum AS ENUM ('reader', 'maintainer', 'admin');
CREATE TYPE document_status_enum AS ENUM ('uploaded', 'processing', 'ready', 'failed');
CREATE TYPE ingest_job_status_enum AS ENUM ('queued', 'processing', 'succeeded', 'failed');
CREATE TYPE chunk_type_enum AS ENUM ('parent', 'child');
CREATE TYPE chunk_structure_kind_enum AS ENUM ('text', 'table');

-- Tables

-- Areas
CREATE TABLE IF NOT EXISTS areas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Area User Roles
CREATE TABLE IF NOT EXISTS area_user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    user_sub VARCHAR(255) NOT NULL,
    role role_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_area_user_roles_area_subject UNIQUE (area_id, user_sub)
);

-- Area Group Roles
CREATE TABLE IF NOT EXISTS area_group_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    group_path VARCHAR(255) NOT NULL,
    role role_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_area_group_roles_area_group_path UNIQUE (area_id, group_path)
);

-- Documents
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    content_type VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    storage_key VARCHAR(512) NOT NULL,
    status document_status_enum NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

-- Ingest Jobs
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status ingest_job_status_enum NOT NULL DEFAULT 'queued',
    stage VARCHAR(32) NOT NULL DEFAULT 'queued',
    parent_chunk_count INTEGER NOT NULL DEFAULT 0,
    child_chunk_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Document Chunks
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_chunk_id UUID REFERENCES document_chunks(id) ON DELETE CASCADE,
    chunk_type chunk_type_enum NOT NULL,
    structure_kind chunk_structure_kind_enum NOT NULL DEFAULT 'text',
    position INTEGER NOT NULL,
    section_index INTEGER NOT NULL,
    child_index INTEGER,
    heading VARCHAR(255),
    content TEXT NOT NULL,
    content_preview VARCHAR(255) NOT NULL,
    char_count INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_document_chunks_document_position UNIQUE (document_id, position),
    CONSTRAINT uq_document_chunks_document_section_child UNIQUE (document_id, section_index, child_index)
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;

-- PGroonga Full Text Search Index
CREATE INDEX IF NOT EXISTS ix_document_chunks_content_pgroonga
ON document_chunks
USING pgroonga (content)
WHERE chunk_type = 'child';

-- Triggers for updated_at (Optional but recommended for consistency)
-- For simplicity, skipped in this initial migration but should be added later.
