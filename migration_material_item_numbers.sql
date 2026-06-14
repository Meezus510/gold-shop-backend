-- Material-scoped item numbers.
-- Gold/Oro keeps its current numbers. Other prefixes are resequenced from 1.

ALTER TABLE items
ADD COLUMN IF NOT EXISTS item_number_prefix VARCHAR(8);

ALTER TABLE purchase_requests
ADD COLUMN IF NOT EXISTS item_number_prefix_snapshot VARCHAR(8);

DROP INDEX IF EXISTS ix_items_item_number_unique;
DROP INDEX IF EXISTS ix_items_item_number;
ALTER TABLE items DROP CONSTRAINT IF EXISTS items_item_number_key;

UPDATE items AS i
SET item_number_prefix = CASE
    WHEN lower(regexp_replace(coalesce(i.category, ''), '^cat\.', '')) = 'broqueles' THEN 'B'
    WHEN lower(m.name) = 'gold' THEN 'O'
    WHEN lower(m.name) = 'silver' THEN 'P'
    WHEN lower(m.name) = 'platinum' THEN 'PT'
    WHEN i.pricing_mode = 'MANUAL' THEN 'B'
    ELSE 'X'
END
FROM metals AS m
WHERE i.metal_id = m.id
  AND i.item_number_prefix IS NULL;

UPDATE items AS i
SET item_number_prefix = CASE
    WHEN lower(regexp_replace(coalesce(i.category, ''), '^cat\.', '')) = 'broqueles' THEN 'B'
    WHEN i.pricing_mode = 'MANUAL' THEN 'B'
    ELSE 'X'
END
WHERE i.metal_id IS NULL
  AND i.item_number_prefix IS NULL;

-- Keep current gold numbers because customers/admins may already reference them.
-- Restart every other material group from 1.
WITH numbered AS (
    SELECT
        item_id,
        row_number() OVER (
            PARTITION BY item_number_prefix
            ORDER BY created_at ASC NULLS LAST, item_id ASC
        ) AS new_number
    FROM items
    WHERE item_number_prefix IS NOT NULL
      AND item_number_prefix <> 'O'
)
UPDATE items AS i
SET item_number = numbered.new_number
FROM numbered
WHERE i.item_id = numbered.item_id;

-- Fill missing gold numbers after the existing gold max, if any older rows were missing one.
WITH gold_missing AS (
    SELECT
        item_id,
        (SELECT coalesce(max(item_number), 0) FROM items WHERE item_number_prefix = 'O')
        + row_number() OVER (ORDER BY created_at ASC NULLS LAST, item_id ASC) AS new_number
    FROM items
    WHERE item_number_prefix = 'O'
      AND item_number IS NULL
)
UPDATE items AS i
SET item_number = gold_missing.new_number
FROM gold_missing
WHERE i.item_id = gold_missing.item_id;

CREATE UNIQUE INDEX IF NOT EXISTS ix_items_item_number_prefix_number_unique
ON items(item_number_prefix, item_number)
WHERE item_number_prefix IS NOT NULL
  AND item_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_items_item_number_prefix
ON items(item_number_prefix);

UPDATE purchase_requests AS pr
SET item_number_prefix_snapshot = i.item_number_prefix
FROM items AS i
WHERE pr.item_id = i.item_id
  AND pr.item_number_prefix_snapshot IS NULL;
