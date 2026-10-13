-- JARVAS database bootstrap.
-- Runs once on first Postgres container start (pgvector image).
--
-- NOTE: the application intentionally does NOT store plaintext biometric
-- templates in pgvector. Embeddings are encrypted at rest (Fernet) and gallery
-- search decrypts them in-process for an exact cosine scan. The vector extension
-- is enabled for future, opt-in use where templates are derived at rest under an
-- application-controlled key.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Uncomment to add an encrypted-embedding index table for experimentation.
-- The application manages its own schema via SQLAlchemy metadata at startup.
--
-- CREATE TABLE IF NOT EXISTS encrypted_embedding_index (
--     enrollment_id UUID PRIMARY KEY,
--     tenant_id     UUID NOT NULL,
--     ciphertext    BYTEA NOT NULL,   -- Fernet token, never plaintext
--     created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
-- );
