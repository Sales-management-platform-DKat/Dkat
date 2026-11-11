-- Run using a database administrator after 01_schema.sql.
-- Inherit existing signed/unsigned ID types from the installed schema.
USE dkat;
SET @store_id_type = (
    SELECT COLUMN_TYPE FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'stores' AND column_name = 'store_id'
);
SET @user_id_type = (
    SELECT COLUMN_TYPE FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'user_id'
);
SET @ddl = CONCAT(
    'CREATE TABLE IF NOT EXISTS store_subscriptions (',
    'id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, ',
    'store_id ', @store_id_type, ' NOT NULL, ',
    'plan VARCHAR(32) NOT NULL, ',
    'status ENUM(''ACTIVE'',''EXPIRED'',''CANCELLED'') NOT NULL, ',
    'subscription_expires_at DATETIME NOT NULL, created_at DATETIME NOT NULL, ',
    'KEY ix_subscription_store (store_id), ',
    'CONSTRAINT fk_subscription_store FOREIGN KEY (store_id) ',
    'REFERENCES stores(store_id) ON DELETE RESTRICT) ENGINE=InnoDB'
);
PREPARE auth_ddl FROM @ddl;
EXECUTE auth_ddl;
DEALLOCATE PREPARE auth_ddl;
SET @ddl = CONCAT(
    'CREATE TABLE IF NOT EXISTS auth_sessions (',
    'id VARCHAR(36) NOT NULL PRIMARY KEY, ',
    'user_id ', @user_id_type, ' NOT NULL, ',
    'token_hash VARCHAR(64) NOT NULL UNIQUE, ',
    'expires_at DATETIME NOT NULL, revoked BOOLEAN NOT NULL DEFAULT FALSE, ',
    'CONSTRAINT fk_auth_session_user FOREIGN KEY (user_id) ',
    'REFERENCES users(user_id) ON DELETE CASCADE) ENGINE=InnoDB'
);
PREPARE auth_ddl FROM @ddl;
EXECUTE auth_ddl;
DEALLOCATE PREPARE auth_ddl;

GRANT SELECT, INSERT, UPDATE ON dkat.auth_sessions TO 'dkat_app'@'127.0.0.1';
GRANT SELECT, INSERT ON dkat.store_subscriptions TO 'dkat_app'@'127.0.0.1';
GRANT INSERT, UPDATE ON dkat.stores TO 'dkat_app'@'127.0.0.1';
GRANT INSERT ON dkat.users TO 'dkat_app'@'127.0.0.1';

