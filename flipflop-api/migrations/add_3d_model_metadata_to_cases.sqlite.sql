-- Migration: Add 3D model metadata columns to cases table
-- Database: SQLite
-- Date: 2026-08-21
-- Purpose: Support detailed 3D model tracking for PC cases from Sketchfab and other sources

-- Add new columns to cases table (SQLite doesn't support IF NOT EXISTS in ALTER TABLE, so we use CREATE TABLE IF NOT EXISTS pattern)
-- Note: These columns should already exist in newer schema versions

-- Try to add columns - they might already exist
PRAGMA foreign_keys = OFF;

-- Create temporary backup
ALTER TABLE cases RENAME TO cases_backup;

-- Create new table with all columns
CREATE TABLE cases (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    source_site TEXT NOT NULL,
    source_url TEXT,
    image_url TEXT,
    price REAL,
    price_new REAL,
    rrp REAL,
    rating REAL,
    review_count INTEGER,
    sales_velocity TEXT,
    bestseller_rank INTEGER,
    form_factors JSON,
    keywords JSON,
    has_3d_model BOOLEAN DEFAULT 0,
    model_3d_url TEXT,
    model_3d_source TEXT,
    model_3d_creator TEXT,
    model_3d_license TEXT,
    model_3d_quality TEXT,
    model_3d_vertices INTEGER,
    model_3d_polygons INTEGER,
    model_3d_file_size INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Copy data from backup (only existing columns)
INSERT INTO cases
SELECT
    id, name, brand, model, source_site, source_url, image_url,
    price, price_new, rrp, rating, review_count, sales_velocity, bestseller_rank,
    form_factors, keywords,
    has_3d_model, model_3d_url, model_3d_source,
    model_3d_creator, model_3d_license, model_3d_quality,
    model_3d_vertices, model_3d_polygons, model_3d_file_size,
    status, created_at, updated_at
FROM cases_backup;

-- Drop backup
DROP TABLE cases_backup;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_cases_name ON cases(name);
CREATE INDEX IF NOT EXISTS idx_cases_source_site ON cases(source_site);
CREATE INDEX IF NOT EXISTS idx_cases_bestseller_rank ON cases(bestseller_rank);
CREATE INDEX IF NOT EXISTS idx_cases_has_3d_model ON cases(has_3d_model);
CREATE INDEX IF NOT EXISTS idx_cases_model_3d_source ON cases(model_3d_source) WHERE has_3d_model = 1;
CREATE INDEX IF NOT EXISTS idx_cases_model_3d_quality ON cases(model_3d_quality) WHERE has_3d_model = 1;
CREATE INDEX IF NOT EXISTS idx_cases_model_3d_creator ON cases(model_3d_creator) WHERE has_3d_model = 1;
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);

PRAGMA foreign_keys = ON;
