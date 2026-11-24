-- Idempotent migration for existing DKAT databases.
USE dkat;

CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    address VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customers_store_phone (store_id, phone),
    CONSTRAINT fk_customers_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

SET @has_customer_id = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'sales_orders' AND column_name = 'customer_id'
);
SET @customer_id_ddl = IF(@has_customer_id = 0,
    'ALTER TABLE sales_orders ADD COLUMN customer_id BIGINT NULL AFTER branch_id',
    'SELECT 1');
PREPARE customer_id_stmt FROM @customer_id_ddl;
EXECUTE customer_id_stmt;
DEALLOCATE PREPARE customer_id_stmt;

SET @has_customer_fk = (
    SELECT COUNT(*) FROM information_schema.table_constraints
    WHERE constraint_schema = DATABASE() AND table_name = 'sales_orders' AND constraint_name = 'fk_sales_orders_customer_id'
);
SET @customer_fk_ddl = IF(@has_customer_fk = 0,
    'ALTER TABLE sales_orders ADD CONSTRAINT fk_sales_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT ON UPDATE RESTRICT',
    'SELECT 1');
PREPARE customer_fk_stmt FROM @customer_fk_ddl;
EXECUTE customer_fk_stmt;
DEALLOCATE PREPARE customer_fk_stmt;
