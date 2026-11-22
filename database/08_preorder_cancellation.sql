-- PBI 140: apply after 07_preorder_fifo_expiry.sql. Safe to run again.
USE dkat;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='cancel_reason'
    ),
    'SELECT ''preorders.cancel_reason already present'' AS migration_status',
    'ALTER TABLE preorders ADD COLUMN cancel_reason VARCHAR(255) NULL'
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='cancelled_at'
    ),
    'SELECT ''preorders.cancelled_at already present'' AS migration_status',
    'ALTER TABLE preorders ADD COLUMN cancelled_at DATETIME NULL'
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND INDEX_NAME='ix_preorders_expiry'
    ),
    'SELECT ''ix_preorders_expiry already present'' AS migration_status',
    'CREATE INDEX ix_preorders_expiry ON preorders (status, expires_at, preorder_id)'
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;
