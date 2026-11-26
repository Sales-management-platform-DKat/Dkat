-- FR-09.5 / NFR-10: automatic retry and manual resend of notifications. Safe to run again.
-- retry_count     number of re-sends after the first attempt (automatic job + manual resend)
-- event_type      PREORDER_CREATED / PREORDER_READY / PREORDER_CANCELLED / PREORDER_EXPIRED (NULL for old rows)
-- last_attempt_at UTC time of the latest send attempt
USE dkat;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='notifications' AND COLUMN_NAME='retry_count'),
    'SELECT ''notifications.retry_count already present'' AS migration_status',
    'ALTER TABLE notifications ADD COLUMN retry_count INT NOT NULL DEFAULT 0'
);
PREPARE retry_ddl FROM @ddl;
EXECUTE retry_ddl;
DEALLOCATE PREPARE retry_ddl;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='notifications' AND COLUMN_NAME='event_type'),
    'SELECT ''notifications.event_type already present'' AS migration_status',
    'ALTER TABLE notifications ADD COLUMN event_type VARCHAR(40) NULL'
);
PREPARE retry_ddl FROM @ddl;
EXECUTE retry_ddl;
DEALLOCATE PREPARE retry_ddl;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='notifications' AND COLUMN_NAME='last_attempt_at'),
    'SELECT ''notifications.last_attempt_at already present'' AS migration_status',
    'ALTER TABLE notifications ADD COLUMN last_attempt_at DATETIME NULL'
);
PREPARE retry_ddl FROM @ddl;
EXECUTE retry_ddl;
DEALLOCATE PREPARE retry_ddl;

-- The retry job scans: WHERE status = 'FAILED' AND retry_count < 3 ORDER BY notification_id
SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='notifications' AND INDEX_NAME='ix_notifications_retry'),
    'SELECT ''ix_notifications_retry already present'' AS migration_status',
    'CREATE INDEX ix_notifications_retry ON notifications (status, retry_count, notification_id)'
);
PREPARE retry_ddl FROM @ddl;
EXECUTE retry_ddl;
DEALLOCATE PREPARE retry_ddl;
