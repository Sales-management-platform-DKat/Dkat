-- Apply to a database initialized before PBI 74/75. Safe to run again.
USE dkat;

-- Append EXPORT so existing ENUM values retain their positions.
SET @movement_type = (
    SELECT COLUMN_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movements'
      AND COLUMN_NAME = 'movement_type'
);
SET @ddl = IF(
    LOCATE('''EXPORT''', UPPER(@movement_type)) = 0,
    CONCAT('ALTER TABLE inventory_movements MODIFY COLUMN movement_type ',
           LEFT(@movement_type, CHAR_LENGTH(@movement_type) - 1), ',''EXPORT'') NOT NULL'),
    'SELECT ''EXPORT movement type already present'' AS migration_status'
);
PREPARE inventory_ddl FROM @ddl;
EXECUTE inventory_ddl;
DEALLOCATE PREPARE inventory_ddl;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movements'
          AND COLUMN_NAME = 'export_reason'
    ),
    'SELECT ''export_reason already present'' AS migration_status',
    'ALTER TABLE inventory_movements ADD COLUMN export_reason ENUM(''HU_HONG'', ''MAU'', ''KHAC'') NULL'
);
PREPARE inventory_ddl FROM @ddl;
EXECUTE inventory_ddl;
DEALLOCATE PREPARE inventory_ddl;
