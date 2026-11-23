-- PBI 110: run after 04_sales_order_customers.sql on an existing database.
-- Adds nullable snapshots for legacy orders. Safe to run again; no business data is deleted.
USE dkat;

SET @customer_id_type = (
    SELECT COLUMN_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='customers' AND COLUMN_NAME='customer_id'
);
SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='customer_id'),
    'SELECT ''preorders.customer_id already present'' AS migration_status',
    CONCAT('ALTER TABLE preorders ADD COLUMN customer_id ', @customer_id_type, ' NULL')
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='customer_address'),
    'SELECT ''preorders.customer_address already present'' AS migration_status',
    'ALTER TABLE preorders ADD COLUMN customer_address VARCHAR(255) NULL'
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='note'),
    'SELECT ''preorders.note already present'' AS migration_status',
    'ALTER TABLE preorders ADD COLUMN note VARCHAR(255) NULL'
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preorders' AND COLUMN_NAME='customer_id'
              AND REFERENCED_TABLE_NAME='customers' AND REFERENCED_COLUMN_NAME='customer_id'),
    'SELECT ''Preorder customer foreign key already present'' AS migration_status',
    'ALTER TABLE preorders ADD CONSTRAINT fk_preorders_customer_id
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT'
);
PREPARE preorder_ddl FROM @ddl;
EXECUTE preorder_ddl;
DEALLOCATE PREPARE preorder_ddl;

CREATE TABLE IF NOT EXISTS preorder_request_limits (
    ip_key CHAR(64) NOT NULL PRIMARY KEY,
    request_times JSON NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_preorder_limits_updated (updated_at)
) ENGINE=InnoDB;
