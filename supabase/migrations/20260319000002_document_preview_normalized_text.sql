ALTER TABLE documents
ADD COLUMN IF NOT EXISTS normalized_text TEXT;
