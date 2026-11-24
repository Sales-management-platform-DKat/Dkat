-- PBI 129: add the pickup deadline without changing existing orders. Safe to run again.
USE dkat;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='expires_at'
    ),
    'SELECT ''preorders.expires_at already present'' AS migration_status',
    'ALTER TABLE preorders ADD COLUMN expires_at DATETIME NULL AFTER ready_at'
);
PREPARE fifo_ddl FROM @ddl;
EXECUTE fifo_ddl;
DEALLOCATE PREPARE fifo_ddl;
