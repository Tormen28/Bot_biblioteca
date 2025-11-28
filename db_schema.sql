-- Database schema for BiblioBot

-- Create enum for user roles
CREATE TYPE user_role AS ENUM ('admin', 'reader');

-- Users table for authorized access
CREATE TABLE users (
    user_id_telegram BIGINT PRIMARY KEY,
    role user_role NOT NULL,
    authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    authorized_by BIGINT REFERENCES users(user_id_telegram)
);

-- Books table for metadata
CREATE TABLE books (
    book_id SERIAL PRIMARY KEY,
    file_id_telegram VARCHAR(255) UNIQUE,
    file_hash_sha256 VARCHAR(64) UNIQUE,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    subject TEXT[],  -- Array of subjects/tags
    size_bytes BIGINT NOT NULL,
    url_external TEXT,
    ts_vector_search TSVECTOR
);

-- Index for full-text search
CREATE INDEX idx_books_fts ON books USING gin(ts_vector_search);

-- Trigger to update ts_vector_search on insert/update
CREATE OR REPLACE FUNCTION update_ts_vector_search() RETURNS TRIGGER AS $$
BEGIN
    NEW.ts_vector_search := to_tsvector('english', NEW.title || ' ' || NEW.author || ' ' || array_to_string(NEW.subject, ' '));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_ts_vector_search
    BEFORE INSERT OR UPDATE ON books
    FOR EACH ROW EXECUTE FUNCTION update_ts_vector_search();