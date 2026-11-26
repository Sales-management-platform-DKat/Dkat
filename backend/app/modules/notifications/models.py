"""Table `notifications`: one row per send attempt (SMS or EMAIL). Accessed with SQL in repository.py;
no ORM model, so create_all() never touches it (schema: database/01_schema.sql + 09_notification_retry.sql)."""
