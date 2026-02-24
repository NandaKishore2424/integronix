-- ============================================================
-- Migration 001: Enable required PostgreSQL extensions
-- Run this FIRST before any table creation
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector: enables VECTOR(384) columns
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- enables gen_random_uuid()
