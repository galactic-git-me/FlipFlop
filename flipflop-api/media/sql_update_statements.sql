-- SQL UPDATE statements for 3D model integration
-- Run these after downloading models and extracting metadata

-- Corsair 4000D
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/corsair_4000d.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'SzaBa',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = 'high',
    model_3d_vertices = <EXTRACT_FROM_MODEL>,
    model_3d_polygons = <EXTRACT_FROM_MODEL>,
    updated_at = NOW()
WHERE
    LOWER(name) LIKE '%corsair%4000d%'
    AND source_site IN ('Amazon', 'eBay', 'Overclockers');

-- be quiet! Pure Base 600
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/be_quiet_pure_base_600.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'JackZeta',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = 'high',
    model_3d_vertices = <EXTRACT_FROM_MODEL>,
    model_3d_polygons = <EXTRACT_FROM_MODEL>,
    updated_at = NOW()
WHERE
    LOWER(name) LIKE '%pure base 600%'
    AND source_site IN ('Amazon', 'eBay', 'Overclockers');

-- Corsair 5000D
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/corsair_5000d.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'lukeboxfx',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = 'high',
    model_3d_vertices = <EXTRACT_FROM_MODEL>,
    model_3d_polygons = <EXTRACT_FROM_MODEL>,
    updated_at = NOW()
WHERE
    LOWER(name) LIKE '%corsair%5000d%'
    AND source_site IN ('Amazon', 'eBay', 'Overclockers');

-- Verify updates
SELECT id, name, model_3d_url, model_3d_creator, model_3d_license
FROM cases
WHERE has_3d_model = true
ORDER BY updated_at DESC
LIMIT 3;
