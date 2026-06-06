-- =============================================================================
-- Migration: Add item numbers and preserve existing name prefixes
-- =============================================================================
-- Run once against existing databases after deploying the code that includes
-- items.item_number.
-- =============================================================================

BEGIN;

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS item_number INTEGER;

-- Extract leading item numbers already stored in translated names.
-- Supported examples:
--   27. Heart ring size 7  -> 27
--   76 -Coquettes 3 gold  -> 76
--   43 Square chain 28"   -> 43
WITH extracted AS (
    SELECT
        item_id,
        MIN((regexp_match(name, '^[[:space:]]*([0-9]+)(?:[[:space:]]*[-.]|[[:space:]]+).+'))[1]::INTEGER) AS parsed_number
    FROM item_translations
    WHERE name ~ '^[[:space:]]*[0-9]+(?:[[:space:]]*[-.]|[[:space:]]+).+'
    GROUP BY item_id
),
unique_numbers AS (
    SELECT item_id, parsed_number
    FROM (
        SELECT
            item_id,
            parsed_number,
            COUNT(*) OVER (PARTITION BY parsed_number) AS number_count
        FROM extracted
    ) numbered
    WHERE number_count = 1
)
UPDATE items
SET item_number = unique_numbers.parsed_number
FROM unique_numbers
WHERE items.item_id = unique_numbers.item_id
  AND items.item_number IS NULL;

-- Remove the old number prefix from names after storing it separately.
UPDATE item_translations
SET name = trim(regexp_replace(name, '^[[:space:]]*[0-9]+(?:[[:space:]]*[-.]|[[:space:]]+)[[:space:]]*', ''))
WHERE name ~ '^[[:space:]]*[0-9]+(?:[[:space:]]*[-.]|[[:space:]]+).+'
  AND item_id IN (SELECT item_id FROM items WHERE item_number IS NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS ix_items_item_number_unique
    ON items (item_number)
    WHERE item_number IS NOT NULL;

COMMIT;
