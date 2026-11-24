USE dkat;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sales_orders' AND COLUMN_NAME='cancelled_at'
    ),
    'SELECT ''cancelled_at already present'' AS migration_status',
    'ALTER TABLE sales_orders ADD COLUMN cancelled_at DATETIME NULL'
);
PREPARE cancel_ddl FROM @ddl;
EXECUTE cancel_ddl;
DEALLOCATE PREPARE cancel_ddl;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sales_orders' AND COLUMN_NAME='cancel_reason'
    ),
    'SELECT ''cancel_reason already present'' AS migration_status',
    'ALTER TABLE sales_orders ADD COLUMN cancel_reason VARCHAR(255) NULL'
);
PREPARE cancel_ddl FROM @ddl;
EXECUTE cancel_ddl;
DEALLOCATE PREPARE cancel_ddl;
