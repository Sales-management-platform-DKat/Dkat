-- DKat database schema, based on DKat_CSDL v1.0.
-- Requires MySQL 8.0.16+ for enforced CHECK constraints.
-- Run once against a new schema. Existing tables and data are preserved.
CREATE DATABASE IF NOT EXISTS dkat CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE dkat;
SET SESSION time_zone = '+00:00';

CREATE TABLE stores (
    store_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    owner_user_id BIGINT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_stores_owner (owner_user_id)
) ENGINE=InnoDB;

CREATE TABLE branches (
    branch_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    branch_code VARCHAR(30) NOT NULL,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_branches_code (store_id, branch_code),
    CONSTRAINT fk_branches_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE users (
    user_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('OWNER', 'MANAGER', 'EMPLOYEE') NOT NULL,
    status ENUM('ACTIVE', 'LOCKED') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_store_user (store_id, user_id),
    CONSTRAINT fk_users_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- MySQL checks foreign keys immediately. Set the owner in the same
-- transaction that creates the store and its first OWNER user.
ALTER TABLE stores ADD CONSTRAINT fk_stores_owner
    FOREIGN KEY (store_id, owner_user_id) REFERENCES users (store_id, user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE user_branches (
    user_branch_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    branch_id BIGINT NOT NULL,
    assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_branches (user_id, branch_id),
    CONSTRAINT fk_user_branches_user_id FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_user_branches_branch_id FOREIGN KEY (branch_id) REFERENCES branches (branch_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE categories (
    category_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    parent_category_id BIGINT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL,
    UNIQUE KEY uq_categories_store_category (store_id, category_id),
    CONSTRAINT fk_categories_parent_category_id FOREIGN KEY (store_id, parent_category_id) REFERENCES categories (store_id, category_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_categories_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE products (
    product_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    category_id BIGINT NOT NULL,
    product_code VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    image_url VARCHAR(500),
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by BIGINT NOT NULL,
    UNIQUE KEY uq_products_code (store_id, product_code),
    KEY ix_products_category_status (store_id, category_id, status),
    CONSTRAINT fk_products_category_id FOREIGN KEY (store_id, category_id) REFERENCES categories (store_id, category_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_products_created_by FOREIGN KEY (store_id, created_by) REFERENCES users (store_id, user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_products_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE product_variants (
    variant_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_id BIGINT NOT NULL,
    sku VARCHAR(80) NOT NULL UNIQUE,
    barcode VARCHAR(100),
    variant_name VARCHAR(200) NOT NULL,
    price DECIMAL(12,2) NOT NULL,
    cost_price DECIMAL(12,2),
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_variants_product_status (product_id, status),
    CHECK (price >= 0 AND cost_price >= 0),
    CONSTRAINT fk_product_variants_product_id FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE attributes (
    attribute_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    data_type ENUM('TEXT', 'NUMBER', 'BOOLEAN') NOT NULL,
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL,
    CONSTRAINT fk_attributes_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE variant_attribute_values (
    variant_attribute_value_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    variant_id BIGINT NOT NULL,
    attribute_id BIGINT NOT NULL,
    `value` VARCHAR(255) NOT NULL,
    UNIQUE KEY uq_variant_attribute (variant_id, attribute_id),
    CONSTRAINT fk_variant_attribute_values_variant_id FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_variant_attribute_values_attribute_id FOREIGN KEY (attribute_id) REFERENCES attributes (attribute_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE inventory (
    inventory_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    branch_id BIGINT NOT NULL,
    variant_id BIGINT NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_inventory_branch_variant (branch_id, variant_id),
    CHECK (quantity >= 0),
    CONSTRAINT fk_inventory_branch_id FOREIGN KEY (branch_id) REFERENCES branches (branch_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_inventory_variant_id FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE inventory_movements (
    movement_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    inventory_id BIGINT NOT NULL,
    movement_type ENUM('IMPORT', 'SALE', 'PREORDER_FULFILLMENT', 'ADJUSTMENT', 'EXPORT') NOT NULL,
    quantity_change INT NOT NULL,
    reference_type VARCHAR(50),
    reference_id BIGINT,
    export_reason ENUM('HU_HONG', 'MAU', 'KHAC') NULL,
    note VARCHAR(255),
    created_by BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_movements_inventory_time (inventory_id, created_at),
    KEY ix_movements_created_at_id (created_at, movement_id),
    CONSTRAINT fk_inventory_movements_inventory_id FOREIGN KEY (inventory_id) REFERENCES inventory (inventory_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_inventory_movements_created_by FOREIGN KEY (created_by) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE customers (
    customer_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    address VARCHAR(255),
    note VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customers_store_phone (store_id, phone),
    CONSTRAINT fk_customers_store_id FOREIGN KEY (store_id) REFERENCES stores (store_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE sales_orders (
    sales_order_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_code VARCHAR(50) NOT NULL UNIQUE,
    branch_id BIGINT NOT NULL,
    customer_id BIGINT,
    created_by BIGINT NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    status ENUM('PENDING', 'PAID', 'CANCELLED') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at DATETIME,
    cancelled_at DATETIME,
    cancel_reason VARCHAR(255),
    KEY ix_sales_branch_time (branch_id, created_at),
    KEY ix_sales_status_time (status, created_at),
    CHECK (subtotal >= 0 AND discount_amount >= 0 AND total_amount = subtotal - discount_amount AND total_amount >= 0),
    CONSTRAINT fk_sales_orders_branch_id FOREIGN KEY (branch_id) REFERENCES branches (branch_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_sales_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT,
    CONSTRAINT fk_sales_orders_created_by FOREIGN KEY (created_by) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE sales_order_items (
    sales_order_item_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sales_order_id BIGINT NOT NULL,
    variant_id BIGINT NOT NULL,
    product_name_snapshot VARCHAR(200) NOT NULL,
    sku_snapshot VARCHAR(80) NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    quantity INT NOT NULL,
    line_total DECIMAL(12,2) NOT NULL,
    KEY ix_sales_items_order_variant (sales_order_id, variant_id),
    CHECK (quantity > 0 AND unit_price >= 0 AND line_total = unit_price * quantity),
    CONSTRAINT fk_sales_order_items_sales_order_id FOREIGN KEY (sales_order_id) REFERENCES sales_orders (sales_order_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_sales_order_items_variant_id FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE preorders (
    preorder_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    preorder_code VARCHAR(50) NOT NULL UNIQUE,
    branch_id BIGINT NOT NULL,
    customer_id BIGINT,
    customer_name VARCHAR(150) NOT NULL,
    customer_phone VARCHAR(20),
    customer_email VARCHAR(255),
    customer_address VARCHAR(255),
    note VARCHAR(255),
    total_amount DECIMAL(12,2) NOT NULL,
    payment_status ENUM('UNPAID', 'PAID', 'REFUNDED') NOT NULL,
    status ENUM('WAITING_STOCK', 'READY', 'NOTIFIED', 'FULFILLED', 'CANCELLED', 'EXPIRED') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ready_at DATETIME,
    expires_at DATETIME,
    fulfilled_at DATETIME,
    cancel_reason VARCHAR(255),
    cancelled_at DATETIME,
    KEY ix_preorders_branch_fifo (branch_id, status, created_at, preorder_id),
    KEY ix_preorders_expiry (status, expires_at, preorder_id),
    CHECK (total_amount >= 0),
    CHECK (COALESCE(CHAR_LENGTH(TRIM(customer_phone)), 0) > 0 OR COALESCE(CHAR_LENGTH(TRIM(customer_email)), 0) > 0),
    CONSTRAINT fk_preorders_branch_id FOREIGN KEY (branch_id) REFERENCES branches (branch_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_preorders_customer_id FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE preorder_request_limits (
    ip_key CHAR(64) NOT NULL PRIMARY KEY,
    request_times JSON NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_preorder_limits_updated (updated_at)
) ENGINE=InnoDB;

CREATE TABLE preorder_items (
    preorder_item_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    preorder_id BIGINT NOT NULL,
    variant_id BIGINT NOT NULL,
    product_name_snapshot VARCHAR(200) NOT NULL,
    sku_snapshot VARCHAR(80) NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    quantity INT NOT NULL,
    allocated_quantity INT NOT NULL DEFAULT 0,
    line_total DECIMAL(12,2) NOT NULL,
    KEY ix_preorder_items_variant_order (variant_id, preorder_id),
    CHECK (quantity > 0 AND allocated_quantity BETWEEN 0 AND quantity),
    CHECK (unit_price >= 0 AND line_total = unit_price * quantity),
    CONSTRAINT fk_preorder_items_preorder_id FOREIGN KEY (preorder_id) REFERENCES preorders (preorder_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_preorder_items_variant_id FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE payments (
    payment_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sales_order_id BIGINT,
    preorder_id BIGINT,
    payment_method ENUM('CASH', 'BANK_TRANSFER', 'CARD', 'OTHER') NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    status ENUM('PENDING', 'SUCCESS', 'FAILED', 'REFUNDED') NOT NULL,
    confirmed_by BIGINT NOT NULL,
    confirmed_at DATETIME,
    CHECK ((sales_order_id IS NULL) <> (preorder_id IS NULL)),
    CHECK (amount >= 0),
    CONSTRAINT fk_payments_sales_order_id FOREIGN KEY (sales_order_id) REFERENCES sales_orders (sales_order_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_payments_preorder_id FOREIGN KEY (preorder_id) REFERENCES preorders (preorder_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_payments_confirmed_by FOREIGN KEY (confirmed_by) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE preorder_fulfillments (
    fulfillment_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    preorder_id BIGINT NOT NULL UNIQUE,
    fulfillment_method ENUM('PICKUP', 'DELIVERY') NOT NULL,
    delivery_address VARCHAR(500),
    status ENUM('PENDING', 'PROCESSING', 'COMPLETED') NOT NULL,
    confirmed_by BIGINT,
    completed_at DATETIME,
    CHECK (fulfillment_method <> 'DELIVERY' OR COALESCE(CHAR_LENGTH(TRIM(delivery_address)), 0) > 0),
    CONSTRAINT fk_preorder_fulfillments_preorder_id FOREIGN KEY (preorder_id) REFERENCES preorders (preorder_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_preorder_fulfillments_confirmed_by FOREIGN KEY (confirmed_by) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE notifications (
    notification_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    preorder_id BIGINT NOT NULL,
    channel ENUM('SMS', 'EMAIL') NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status ENUM('PENDING', 'SENT', 'FAILED') NOT NULL,
    provider_message_id VARCHAR(255),
    error_message TEXT,
    sent_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_notifications_preorder_status (preorder_id, status),
    KEY ix_notifications_queue (status, created_at, notification_id),
    CONSTRAINT fk_notifications_preorder_id FOREIGN KEY (preorder_id) REFERENCES preorders (preorder_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

-- Authentication and store subscriptions
CREATE TABLE store_subscriptions (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT NOT NULL,
    plan VARCHAR(32) NOT NULL,
    status ENUM('ACTIVE', 'EXPIRED', 'CANCELLED') NOT NULL,
    subscription_expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    KEY ix_subscription_store (store_id),
    CONSTRAINT fk_subscription_store FOREIGN KEY (store_id)
        REFERENCES stores (store_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE auth_sessions (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_auth_session_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
