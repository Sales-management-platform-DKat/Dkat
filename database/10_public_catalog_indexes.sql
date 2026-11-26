-- FR-07 public catalog: the attribute filter (attr=Màu:Đen) looks attributes up by name.
-- Without this index the lookup scans the whole attributes table. Safe to run again.
USE dkat;

SET @ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='attributes' AND INDEX_NAME='ix_attributes_name_status'),
    'SELECT ''ix_attributes_name_status already present'' AS migration_status',
    'CREATE INDEX ix_attributes_name_status ON attributes (name, status)'
);
PREPARE catalog_ddl FROM @ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;
