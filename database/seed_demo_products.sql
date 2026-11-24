-- Development data for the DKat product API.
USE dkat;
SET SESSION time_zone = '+00:00';

DELIMITER //
CREATE PROCEDURE dkat_seed_demo_products()
BEGIN
    DECLARE demo_number INT DEFAULT 1;
    DECLARE demo_suffix CHAR(1);
    DECLARE demo_username VARCHAR(100);
    DECLARE demo_store BIGINT;
    DECLARE demo_owner BIGINT;
    DECLARE demo_category BIGINT;
    DECLARE demo_product BIGINT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    WHILE demo_number <= 2 DO
        SET demo_suffix = IF(demo_number = 1, 'A', 'B');
        SET demo_username = CONCAT('dkat_seed_owner_', LOWER(demo_suffix));

        IF NOT EXISTS (SELECT 1 FROM users WHERE username = demo_username) THEN
            INSERT INTO stores (name)
            VALUES (CONCAT('DKat Demo ', demo_suffix));
            SET demo_store = LAST_INSERT_ID();

            INSERT INTO users (store_id, full_name, username, password_hash, role, status)
            VALUES (demo_store, 'DKat Seed Owner', demo_username, '!', 'OWNER', 'LOCKED');
            SET demo_owner = LAST_INSERT_ID();

            UPDATE stores SET owner_user_id = demo_owner WHERE store_id = demo_store;

            INSERT INTO categories (store_id, name, status)
            VALUES (demo_store, 'Demo', 'ACTIVE');
            SET demo_category = LAST_INSERT_ID();

            INSERT INTO products (store_id, category_id, product_code, name, status, created_by)
            VALUES (demo_store, demo_category, 'DEMO-01',
                    CONCAT('Sản phẩm Demo ', demo_suffix), 'ACTIVE', demo_owner);
            SET demo_product = LAST_INSERT_ID();

            INSERT INTO product_variants (product_id, sku, variant_name, price, status)
            VALUES (demo_product, CONCAT('DKAT-DEMO-', demo_suffix),
                    'Tiêu chuẩn', 99000.00, 'ACTIVE');
        END IF;

        SET demo_number = demo_number + 1;
    END WHILE;
    COMMIT;
END//
DELIMITER ;

CALL dkat_seed_demo_products();
DROP PROCEDURE dkat_seed_demo_products;

SELECT s.store_id, s.name, v.sku
FROM stores AS s
JOIN users AS u ON u.user_id = s.owner_user_id
JOIN products AS p ON p.store_id = s.store_id AND p.product_code = 'DEMO-01'
JOIN product_variants AS v ON v.product_id = p.product_id
WHERE u.username IN ('dkat_seed_owner_a', 'dkat_seed_owner_b')
  AND v.sku IN ('DKAT-DEMO-A', 'DKAT-DEMO-B')
ORDER BY v.sku;
