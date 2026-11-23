-- DKat: full schema of the backend on the tuan/* branches (20 tables).
-- Generated from the working database on 24/11/2026 (SHOW CREATE TABLE).
-- Already contains the migrations 04 (customers), 06 (preorders.customer_id), 07 (expires_at)
-- and 09 (notification retry): running those files afterwards is harmless (they are idempotent).
-- Usage: python -m scripts.init_db (creates DB_NAME from .env), or run this file in MySQL Workbench
-- after `CREATE DATABASE dkat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; USE dkat;`.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;  -- stores.owner_user_id -> users and users.store_id -> stores reference each other

CREATE TABLE IF NOT EXISTS `users` (
  `user_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `store_id` bigint unsigned NOT NULL,
  `full_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` enum('OWNER','MANAGER','EMPLOYEE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('ACTIVE','LOCKED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_users_username` (`username`),
  KEY `idx_users_store` (`store_id`),
  CONSTRAINT `fk_users_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tài khoản nội bộ';

CREATE TABLE IF NOT EXISTS `stores` (
  `store_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_user_id` bigint unsigned NOT NULL COMMENT 'Chủ cửa hàng',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`store_id`),
  KEY `idx_stores_owner` (`owner_user_id`),
  CONSTRAINT `fk_stores_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Cửa hàng';

CREATE TABLE IF NOT EXISTS `attributes` (
  `attribute_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `store_id` bigint unsigned NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data_type` enum('TEXT','NUMBER','BOOLEAN') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'TEXT',
  `status` enum('ACTIVE','INACTIVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  PRIMARY KEY (`attribute_id`),
  KEY `idx_attr_store` (`store_id`),
  CONSTRAINT `fk_attr_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Định nghĩa thuộc tính';

CREATE TABLE IF NOT EXISTS `branches` (
  `branch_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `store_id` bigint unsigned NOT NULL,
  `branch_code` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('ACTIVE','INACTIVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`branch_id`),
  UNIQUE KEY `uq_branches_store_code` (`store_id`,`branch_code`),
  CONSTRAINT `fk_branches_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Chi nhánh';

CREATE TABLE IF NOT EXISTS `categories` (
  `category_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `store_id` bigint unsigned NOT NULL,
  `parent_category_id` bigint unsigned DEFAULT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `status` enum('ACTIVE','INACTIVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  PRIMARY KEY (`category_id`),
  KEY `idx_cat_store` (`store_id`),
  KEY `idx_cat_parent` (`parent_category_id`),
  CONSTRAINT `fk_cat_parent` FOREIGN KEY (`parent_category_id`) REFERENCES `categories` (`category_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_cat_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Danh mục';

CREATE TABLE IF NOT EXISTS `customers` (
  `customer_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `store_id` bigint unsigned NOT NULL,
  `full_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `address` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`customer_id`),
  UNIQUE KEY `uq_customers_store_phone` (`store_id`,`phone`),
  CONSTRAINT `fk_customers_store_id` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `products` (
  `product_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `store_id` bigint unsigned NOT NULL,
  `category_id` bigint unsigned NOT NULL,
  `product_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `image_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('ACTIVE','INACTIVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` bigint unsigned NOT NULL COMMENT 'Chủ cửa hàng tạo',
  PRIMARY KEY (`product_id`),
  UNIQUE KEY `uq_products_store_code` (`store_id`,`product_code`),
  KEY `idx_products_store_cat_status` (`store_id`,`category_id`,`status`),
  KEY `idx_products_category` (`category_id`),
  KEY `idx_products_created_by` (`created_by`),
  CONSTRAINT `fk_products_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_products_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_products_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Sản phẩm';

CREATE TABLE IF NOT EXISTS `product_variants` (
  `variant_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `product_id` bigint unsigned NOT NULL,
  `sku` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `barcode` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `variant_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `price` decimal(12,2) NOT NULL,
  `cost_price` decimal(12,2) DEFAULT NULL,
  `status` enum('ACTIVE','INACTIVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`variant_id`),
  UNIQUE KEY `uq_variants_sku` (`sku`),
  KEY `idx_variants_product_status` (`product_id`,`status`),
  KEY `idx_variants_barcode` (`barcode`),
  CONSTRAINT `fk_variants_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_variants_cost` CHECK (((`cost_price` is null) or (`cost_price` >= 0))),
  CONSTRAINT `chk_variants_price` CHECK ((`price` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Biến thể sản phẩm';

CREATE TABLE IF NOT EXISTS `inventory` (
  `inventory_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `branch_id` bigint unsigned NOT NULL,
  `variant_id` bigint unsigned NOT NULL,
  `quantity` int NOT NULL DEFAULT '0',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`inventory_id`),
  UNIQUE KEY `uq_inventory_branch_variant` (`branch_id`,`variant_id`),
  KEY `idx_inventory_variant` (`variant_id`),
  CONSTRAINT `fk_inventory_branch` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`branch_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_inventory_variant` FOREIGN KEY (`variant_id`) REFERENCES `product_variants` (`variant_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_inventory_qty` CHECK ((`quantity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tồn kho';

CREATE TABLE IF NOT EXISTS `inventory_movements` (
  `movement_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `inventory_id` bigint unsigned NOT NULL,
  `movement_type` enum('IMPORT','SALE','PREORDER_FULFILLMENT','ADJUSTMENT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `quantity_change` int NOT NULL COMMENT 'Số lượng có dấu (+/-)',
  `reference_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Loại chứng từ',
  `reference_id` bigint unsigned DEFAULT NULL COMMENT 'ID chứng từ',
  `note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_by` bigint unsigned NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`movement_id`),
  KEY `idx_mov_inventory_created` (`inventory_id`,`created_at`),
  KEY `idx_mov_reference` (`reference_type`,`reference_id`),
  KEY `idx_mov_created_by` (`created_by`),
  CONSTRAINT `fk_mov_inventory` FOREIGN KEY (`inventory_id`) REFERENCES `inventory` (`inventory_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_mov_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_mov_nonzero` CHECK ((`quantity_change` <> 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Biến động kho';

CREATE TABLE IF NOT EXISTS `preorders` (
  `preorder_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `preorder_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `branch_id` bigint unsigned NOT NULL,
  `customer_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer_phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `customer_email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `total_amount` decimal(12,2) NOT NULL,
  `payment_status` enum('UNPAID','PAID','REFUNDED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UNPAID',
  `status` enum('WAITING_STOCK','READY','NOTIFIED','FULFILLED','CANCELLED','EXPIRED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'WAITING_STOCK',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ready_at` datetime DEFAULT NULL COMMENT 'Thời điểm đủ hàng',
  `expires_at` datetime DEFAULT NULL,
  `fulfilled_at` datetime DEFAULT NULL COMMENT 'Thời điểm nhận hàng',
  `customer_id` bigint unsigned DEFAULT NULL,
  `customer_address` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`preorder_id`),
  UNIQUE KEY `uq_preorder_code` (`preorder_code`),
  KEY `idx_pre_branch_status_created` (`branch_id`,`status`,`created_at`),
  KEY `fk_preorders_customer_id` (`customer_id`),
  CONSTRAINT `fk_pre_branch` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`branch_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_preorders_customer_id` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_pre_contact` CHECK (((`customer_phone` is not null) or (`customer_email` is not null))),
  CONSTRAINT `chk_pre_total` CHECK ((`total_amount` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Đơn đặt trước';

CREATE TABLE IF NOT EXISTS `notifications` (
  `notification_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `preorder_id` bigint unsigned NOT NULL,
  `channel` enum('SMS','EMAIL') COLLATE utf8mb4_unicode_ci NOT NULL,
  `recipient` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('PENDING','SENT','FAILED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `provider_message_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `sent_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `retry_count` int NOT NULL DEFAULT '0',
  `event_type` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_attempt_at` datetime DEFAULT NULL,
  PRIMARY KEY (`notification_id`),
  KEY `idx_noti_preorder_status` (`preorder_id`,`status`),
  KEY `ix_notifications_retry` (`status`,`retry_count`,`notification_id`),
  CONSTRAINT `fk_noti_preorder` FOREIGN KEY (`preorder_id`) REFERENCES `preorders` (`preorder_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Thông báo';

CREATE TABLE IF NOT EXISTS `sales_orders` (
  `sales_order_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `order_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `branch_id` bigint unsigned NOT NULL,
  `created_by` bigint unsigned NOT NULL,
  `subtotal` decimal(12,2) NOT NULL,
  `discount_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
  `total_amount` decimal(12,2) NOT NULL,
  `status` enum('PENDING','PAID','CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `paid_at` datetime DEFAULT NULL,
  `customer_id` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`sales_order_id`),
  UNIQUE KEY `uq_sales_order_code` (`order_code`),
  KEY `idx_so_branch_created` (`branch_id`,`created_at`),
  KEY `idx_so_status_created` (`status`,`created_at`),
  KEY `idx_so_created_by` (`created_by`),
  KEY `fk_sales_orders_customer_id` (`customer_id`),
  CONSTRAINT `fk_sales_orders_customer_id` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_so_branch` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`branch_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_so_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_so_amounts` CHECK (((`subtotal` >= 0) and (`discount_amount` >= 0) and (`total_amount` >= 0)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Đơn bán tại quầy';

CREATE TABLE IF NOT EXISTS `payments` (
  `payment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `sales_order_id` bigint unsigned DEFAULT NULL,
  `preorder_id` bigint unsigned DEFAULT NULL,
  `payment_method` enum('CASH','BANK_TRANSFER','CARD','OTHER') COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `status` enum('PENDING','SUCCESS','FAILED','REFUNDED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `confirmed_by` bigint unsigned NOT NULL,
  `confirmed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`payment_id`),
  KEY `idx_pay_sales_order` (`sales_order_id`),
  KEY `idx_pay_preorder` (`preorder_id`),
  KEY `idx_pay_confirmed_by` (`confirmed_by`),
  CONSTRAINT `fk_pay_preorder` FOREIGN KEY (`preorder_id`) REFERENCES `preorders` (`preorder_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_pay_sales_order` FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders` (`sales_order_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_pay_user` FOREIGN KEY (`confirmed_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_pay_amount` CHECK ((`amount` > 0)),
  CONSTRAINT `chk_pay_one_target` CHECK (((`sales_order_id` is null) <> (`preorder_id` is null)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Thanh toán';

CREATE TABLE IF NOT EXISTS `preorder_fulfillments` (
  `fulfillment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `preorder_id` bigint unsigned NOT NULL,
  `fulfillment_method` enum('PICKUP','DELIVERY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `delivery_address` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('PENDING','PROCESSING','COMPLETED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `confirmed_by` bigint unsigned DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`fulfillment_id`),
  UNIQUE KEY `uq_fulfillment_preorder` (`preorder_id`),
  KEY `idx_ful_confirmed_by` (`confirmed_by`),
  CONSTRAINT `fk_ful_preorder` FOREIGN KEY (`preorder_id`) REFERENCES `preorders` (`preorder_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_ful_user` FOREIGN KEY (`confirmed_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_ful_address` CHECK (((`fulfillment_method` <> _utf8mb4'DELIVERY') or (`delivery_address` is not null)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Nhận hàng đặt trước';

CREATE TABLE IF NOT EXISTS `preorder_items` (
  `preorder_item_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `preorder_id` bigint unsigned NOT NULL,
  `variant_id` bigint unsigned NOT NULL,
  `product_name_snapshot` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sku_snapshot` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `unit_price` decimal(12,2) NOT NULL,
  `quantity` int NOT NULL COMMENT 'Số lượng yêu cầu',
  `allocated_quantity` int NOT NULL DEFAULT '0' COMMENT 'Số lượng đã phân bổ',
  `line_total` decimal(12,2) NOT NULL,
  PRIMARY KEY (`preorder_item_id`),
  KEY `idx_pi_variant_preorder` (`variant_id`,`preorder_id`),
  KEY `idx_pi_preorder` (`preorder_id`),
  CONSTRAINT `fk_pi_preorder` FOREIGN KEY (`preorder_id`) REFERENCES `preorders` (`preorder_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_pi_variant` FOREIGN KEY (`variant_id`) REFERENCES `product_variants` (`variant_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_pi_alloc` CHECK (((`allocated_quantity` >= 0) and (`allocated_quantity` <= `quantity`))),
  CONSTRAINT `chk_pi_price` CHECK (((`unit_price` >= 0) and (`line_total` >= 0))),
  CONSTRAINT `chk_pi_qty` CHECK ((`quantity` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Chi tiết đặt trước';

CREATE TABLE IF NOT EXISTS `preorder_request_limits` (
  `ip_key` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `request_times` json NOT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ip_key`),
  KEY `ix_preorder_limits_updated` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sales_order_items` (
  `sales_order_item_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `sales_order_id` bigint unsigned NOT NULL,
  `variant_id` bigint unsigned NOT NULL,
  `product_name_snapshot` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sku_snapshot` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `unit_price` decimal(12,2) NOT NULL,
  `quantity` int NOT NULL,
  `line_total` decimal(12,2) NOT NULL,
  PRIMARY KEY (`sales_order_item_id`),
  KEY `idx_soi_order_variant` (`sales_order_id`,`variant_id`),
  KEY `idx_soi_variant` (`variant_id`),
  CONSTRAINT `fk_soi_order` FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders` (`sales_order_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_soi_variant` FOREIGN KEY (`variant_id`) REFERENCES `product_variants` (`variant_id`) ON DELETE RESTRICT,
  CONSTRAINT `chk_soi_price` CHECK (((`unit_price` >= 0) and (`line_total` >= 0))),
  CONSTRAINT `chk_soi_qty` CHECK ((`quantity` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Chi tiết đơn bán';

CREATE TABLE IF NOT EXISTS `user_branches` (
  `user_branch_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `branch_id` bigint unsigned NOT NULL,
  `assigned_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_branch_id`),
  UNIQUE KEY `uq_user_branch` (`user_id`,`branch_id`),
  KEY `idx_ub_branch` (`branch_id`),
  CONSTRAINT `fk_ub_branch` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`branch_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_ub_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Phân công chi nhánh';

CREATE TABLE IF NOT EXISTS `variant_attribute_values` (
  `variant_attribute_value_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `variant_id` bigint unsigned NOT NULL,
  `attribute_id` bigint unsigned NOT NULL,
  `value` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`variant_attribute_value_id`),
  UNIQUE KEY `uq_variant_attribute` (`variant_id`,`attribute_id`),
  KEY `idx_vav_attribute` (`attribute_id`),
  CONSTRAINT `fk_vav_attribute` FOREIGN KEY (`attribute_id`) REFERENCES `attributes` (`attribute_id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_vav_variant` FOREIGN KEY (`variant_id`) REFERENCES `product_variants` (`variant_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Giá trị thuộc tính của biến thể';

SET FOREIGN_KEY_CHECKS = 1;
