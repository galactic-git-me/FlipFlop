-- Migration: Add 3D model metadata columns to cases table
-- Date: 2026-08-21
-- Purpose: Support detailed 3D model tracking for PC cases from Sketchfab and other sources

-- Add new columns to cases table
ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_creator VARCHAR(255);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_license VARCHAR(50);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_quality VARCHAR(20);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_vertices INTEGER;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_polygons INTEGER;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_file_size INTEGER;

-- Add comments for clarity
COMMENT ON COLUMN cases.model_3d_creator IS 'Artist/creator name (e.g., "SzaBa" from Sketchfab)';
COMMENT ON COLUMN cases.model_3d_license IS 'License type (e.g., "CC-BY-4.0")';
COMMENT ON COLUMN cases.model_3d_quality IS 'Quality estimate: low (< 10k polygons), medium (10k-100k), high (> 100k)';
COMMENT ON COLUMN cases.model_3d_vertices IS 'Vertex count extracted from GLB file';
COMMENT ON COLUMN cases.model_3d_polygons IS 'Triangle/polygon count extracted from GLB file';
COMMENT ON COLUMN cases.model_3d_file_size IS 'File size in bytes';

-- Create index for efficient queries on has_3d_model
CREATE INDEX IF NOT EXISTS idx_cases_has_3d_model ON cases(has_3d_model);

-- Create index for filtering by 3D model source
CREATE INDEX IF NOT EXISTS idx_cases_model_3d_source ON cases(model_3d_source) WHERE has_3d_model = true;

-- Create index for filtering by quality
CREATE INDEX IF NOT EXISTS idx_cases_model_3d_quality ON cases(model_3d_quality) WHERE has_3d_model = true;

-- Optional: Create index for searching by creator
CREATE INDEX IF NOT EXISTS idx_cases_model_3d_creator ON cases(model_3d_creator) WHERE has_3d_model = true;
