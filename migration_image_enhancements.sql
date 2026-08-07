-- Reversible catalog image enhancements and admin preferences.
ALTER TABLE items
    ADD COLUMN IF NOT EXISTS use_enhanced_image BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE item_images
    ADD COLUMN IF NOT EXISTS enhanced_url VARCHAR;

CREATE TABLE IF NOT EXISTS catalog_settings (
    id INTEGER PRIMARY KEY,
    use_enhanced_images BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO catalog_settings (id, use_enhanced_images)
VALUES (1, FALSE)
ON CONFLICT (id) DO NOTHING;
