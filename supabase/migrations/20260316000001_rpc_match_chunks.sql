-- Candidate-generation RPC for hybrid retrieval
-- Returns vector/FTS ranking inputs; final RRF stays in Python.

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1536),
    query_text TEXT,
    match_area_id UUID,
    vector_top_k INT DEFAULT 12,
    fts_top_k INT DEFAULT 12
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    content_preview VARCHAR(255),
    structure_kind chunk_structure_kind_enum,
    heading VARCHAR(255),
    vector_rank INT,
    fts_rank INT,
    fts_score FLOAT
)
LANGUAGE sql
AS $$
WITH vector_matches AS (
    SELECT
        dc.id,
        ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding, dc.id) :: INT AS rank
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE d.area_id = match_area_id
      AND d.status = 'ready'
      AND dc.chunk_type = 'child'
      AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> query_embedding, dc.id
    LIMIT vector_top_k
),
fts_matches AS (
    SELECT
        dc.id,
        ROW_NUMBER() OVER (
            ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
        ) :: INT AS rank,
        pgroonga_score(dc.tableoid, dc.ctid) :: FLOAT AS score
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE d.area_id = match_area_id
      AND d.status = 'ready'
      AND dc.chunk_type = 'child'
      AND dc.content &@~ query_text
    ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
    LIMIT fts_top_k
),
candidate_ids AS (
    SELECT id FROM vector_matches
    UNION
    SELECT id FROM fts_matches
)
SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.content_preview,
    dc.structure_kind,
    dc.heading,
    vm.rank AS vector_rank,
    fm.rank AS fts_rank,
    fm.score AS fts_score
FROM candidate_ids c
JOIN document_chunks dc ON dc.id = c.id
LEFT JOIN vector_matches vm ON vm.id = dc.id
LEFT JOIN fts_matches fm ON fm.id = dc.id
ORDER BY
    COALESCE(vm.rank, 2147483647),
    COALESCE(fm.rank, 2147483647),
    dc.id;
$$;
