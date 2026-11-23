# Sơ đồ ERD - DKat

Sinh tự động từ CSDL đang chạy ngày 24/11/2026 (`information_schema`), khớp với `database/00_schema_full.sql`: 20 bảng, 34 khoá ngoại.
Bản ảnh / PDF: [erd.png](erd.png), [erd.pdf](erd.pdf). GitHub hiển thị trực tiếp sơ đồ Mermaid bên dưới.

Ký hiệu: `PK` khoá chính, `FK` khoá ngoại, `UK` duy nhất. `||--o{` một - nhiều; `|o--o{` khoá ngoại có thể NULL (vd. đơn của khách vãng lai không có `customer_id`).

| Nhóm | Bảng |
|---|---|
| Cửa hàng, chi nhánh, tài khoản | `stores`, `branches`, `users`, `user_branches` |
| Sản phẩm, tồn kho | `categories`, `products`, `product_variants`, `attributes`, `variant_attribute_values`, `inventory`, `inventory_movements` |
| Khách hàng, bán hàng | `customers`, `sales_orders`, `sales_order_items`, `payments` |
| Đặt trước, thông báo | `preorders`, `preorder_items`, `preorder_fulfillments`, `notifications`, `preorder_request_limits` |

```mermaid
erDiagram
    stores ||--o{ attributes : "store_id"
    stores ||--o{ branches : "store_id"
    categories |o--o{ categories : "parent_category_id"
    stores ||--o{ categories : "store_id"
    stores ||--o{ customers : "store_id"
    branches ||--o{ inventory : "branch_id"
    product_variants ||--o{ inventory : "variant_id"
    inventory ||--o{ inventory_movements : "inventory_id"
    users ||--o{ inventory_movements : "created_by"
    preorders ||--o{ notifications : "preorder_id"
    preorders |o--o{ payments : "preorder_id"
    sales_orders |o--o{ payments : "sales_order_id"
    users ||--o{ payments : "confirmed_by"
    preorders ||--o| preorder_fulfillments : "preorder_id"
    users |o--o{ preorder_fulfillments : "confirmed_by"
    preorders ||--o{ preorder_items : "preorder_id"
    product_variants ||--o{ preorder_items : "variant_id"
    customers |o--o{ preorders : "customer_id"
    branches ||--o{ preorders : "branch_id"
    products ||--o{ product_variants : "product_id"
    categories ||--o{ products : "category_id"
    users ||--o{ products : "created_by"
    stores ||--o{ products : "store_id"
    sales_orders ||--o{ sales_order_items : "sales_order_id"
    product_variants ||--o{ sales_order_items : "variant_id"
    customers |o--o{ sales_orders : "customer_id"
    branches ||--o{ sales_orders : "branch_id"
    users ||--o{ sales_orders : "created_by"
    users ||--o{ stores : "owner_user_id"
    branches ||--o{ user_branches : "branch_id"
    users ||--o{ user_branches : "user_id"
    stores ||--o{ users : "store_id"
    attributes ||--o{ variant_attribute_values : "attribute_id"
    product_variants ||--o{ variant_attribute_values : "variant_id"
    attributes {
        bigint attribute_id PK
        bigint store_id FK
        varchar name
        enum data_type
        enum status
    }
    branches {
        bigint branch_id PK
        bigint store_id FK
        varchar branch_code
        varchar name
        varchar address
        varchar phone
        enum status
        datetime created_at
    }
    categories {
        bigint category_id PK
        bigint store_id FK
        bigint parent_category_id FK
        varchar name
        text description
        enum status
    }
    customers {
        bigint customer_id PK
        bigint store_id FK
        varchar full_name
        varchar phone
        varchar email
        varchar address
        varchar note
        datetime created_at
        datetime updated_at
    }
    inventory {
        bigint inventory_id PK
        bigint branch_id FK
        bigint variant_id FK
        int quantity
        datetime updated_at
    }
    inventory_movements {
        bigint movement_id PK
        bigint inventory_id FK
        enum movement_type
        int quantity_change
        varchar reference_type
        bigint reference_id
        varchar note
        bigint created_by FK
        datetime created_at
    }
    notifications {
        bigint notification_id PK
        bigint preorder_id FK
        enum channel
        varchar recipient
        text message
        enum status
        varchar provider_message_id
        text error_message
        datetime sent_at
        datetime created_at
        int retry_count
        varchar event_type
        datetime last_attempt_at
    }
    payments {
        bigint payment_id PK
        bigint sales_order_id FK
        bigint preorder_id FK
        enum payment_method
        decimal amount
        enum status
        bigint confirmed_by FK
        datetime confirmed_at
    }
    preorder_fulfillments {
        bigint fulfillment_id PK
        bigint preorder_id FK,UK
        enum fulfillment_method
        varchar delivery_address
        enum status
        bigint confirmed_by FK
        datetime completed_at
    }
    preorder_items {
        bigint preorder_item_id PK
        bigint preorder_id FK
        bigint variant_id FK
        varchar product_name_snapshot
        varchar sku_snapshot
        decimal unit_price
        int quantity
        int allocated_quantity
        decimal line_total
    }
    preorder_request_limits {
        char ip_key PK
        json request_times
        datetime updated_at
    }
    preorders {
        bigint preorder_id PK
        varchar preorder_code UK
        bigint branch_id FK
        varchar customer_name
        varchar customer_phone
        varchar customer_email
        decimal total_amount
        enum payment_status
        enum status
        datetime created_at
        datetime ready_at
        datetime expires_at
        datetime fulfilled_at
        bigint customer_id FK
        varchar customer_address
        varchar note
    }
    product_variants {
        bigint variant_id PK
        bigint product_id FK
        varchar sku UK
        varchar barcode
        varchar variant_name
        decimal price
        decimal cost_price
        enum status
        datetime created_at
    }
    products {
        bigint product_id PK
        bigint store_id FK
        bigint category_id FK
        varchar product_code
        varchar name
        text description
        varchar image_url
        enum status
        datetime created_at
        bigint created_by FK
    }
    sales_order_items {
        bigint sales_order_item_id PK
        bigint sales_order_id FK
        bigint variant_id FK
        varchar product_name_snapshot
        varchar sku_snapshot
        decimal unit_price
        int quantity
        decimal line_total
    }
    sales_orders {
        bigint sales_order_id PK
        varchar order_code UK
        bigint branch_id FK
        bigint created_by FK
        decimal subtotal
        decimal discount_amount
        decimal total_amount
        enum status
        datetime created_at
        datetime paid_at
        bigint customer_id FK
    }
    stores {
        bigint store_id PK
        varchar name
        bigint owner_user_id FK
        datetime created_at
        datetime updated_at
    }
    user_branches {
        bigint user_branch_id PK
        bigint user_id FK
        bigint branch_id FK
        datetime assigned_at
    }
    users {
        bigint user_id PK
        bigint store_id FK
        varchar full_name
        varchar username UK
        varchar email
        varchar phone
        varchar password_hash
        enum role
        enum status
        datetime created_at
    }
    variant_attribute_values {
        bigint variant_attribute_value_id PK
        bigint variant_id FK
        bigint attribute_id FK
        varchar value
    }
```
