-- Add optional customer records to an existing DKat database. Safe to run again.
USE dkat;

SET @store_id_type = (
    SELECT COLUMN_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'stores' AND COLUMN_NAME = 'store_id'
);
SET @ddl = CONCAT(
    'CREATE TABLE IF NOT EXISTS customers (',
    'customer_id ', @store_id_type, ' NOT NULL AUTO_INCREMENT PRIMARY KEY, ',
    'store_id ', @store_id_type, ' NOT NULL, ',
    'full_name VARCHAR(150) NOT NULL, phone VARCHAR(20), email VARCHAR(255), ',
    'address VARCHAR(255), note VARCHAR(255), ',
    'created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, ',
    'updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, ',
    'UNIQUE KEY uq_customers_store_phone (store_id, phone), ',
    'CONSTRAINT fk_customers_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT',
    ') ENGINE=InnoDB'
);
PREPARE sales_ddl FROM @ddl;
EXECUTE sales_ddl;
DEALLOCATE PREPARE sales_ddl;

SET @customer_id_type = (
    SELECT COLUMN_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'customers' AND COLUMN_NAME = 'customer_id'
);
SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sales_orders' AND COLUMN_NAME = 'customer_id'
    ),
    'SELECT ''sales_orders.customer_id already present'' AS migration_status',
    CONCAT('ALTER TABLE sales_orders ADD COLUMN customer_id ', @customer_id_type, ' NULL')
);
PREPARE sales_ddl FROM @ddl;
EXECUTE sales_ddl;
DEALLOCATE PREPARE sales_ddl;

SET @ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sales_orders' AND COLUMN_NAME = 'customer_id'
          AND REFERENCED_TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME = 'customers'
          AND REFERENCED_COLUMN_NAME = 'customer_id'
    ),
    'SELECT ''Sales customer foreign key already present'' AS migration_status',
    'ALTER TABLE sales_orders ADD CONSTRAINT fk_sales_orders_customer_id
         FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT'
);
PREPARE sales_ddl FROM @ddl;
EXECUTE sales_ddl;
DEALLOCATE PREPARE sales_ddl;
