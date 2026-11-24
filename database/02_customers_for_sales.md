# Customer and sales migration

Run `02_customers_for_sales.sql` against an existing MySQL database before starting the updated API. The migration is safe to run when `customers` or the `sales_orders.customer_id` column already exists.

Grant the runtime database account `SELECT, INSERT` on `customers`. Sales flows also read and write `sales_orders`, `sales_order_items`, `payments`, `inventory`, and `inventory_movements`.

The POS payment action records external payment confirmation. It does not verify bank or card transactions. Refunds require OWNER or MANAGER, a reason, and restore quantity to inventory with an ADJUSTMENT movement.
