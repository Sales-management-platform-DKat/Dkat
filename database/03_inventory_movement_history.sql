-- Run on an existing schema to add the inventory history time index.
USE dkat;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movements'
          AND INDEX_NAME = 'ix_movements_created_at_id'
    ),
    'SELECT ''Inventory history index already present'' AS migration_status',
    'ALTER TABLE inventory_movements ADD INDEX ix_movements_created_at_id (created_at, movement_id)'
);
PREPARE inventory_history_ddl FROM @ddl;
EXECUTE inventory_history_ddl;
DEALLOCATE PREPARE inventory_history_ddl;
