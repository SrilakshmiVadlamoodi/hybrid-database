-- VoltKart D2C Electronics Store — PostgreSQL schema
-- Run as: psql -U postgres -d voltkart -f schema.sql

DROP TABLE IF EXISTS support_tickets CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id     SERIAL PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(20)  NOT NULL,
    city            VARCHAR(80)  NOT NULL,
    state           VARCHAR(80)  NOT NULL,
    pincode         VARCHAR(10)  NOT NULL,
    signup_date     DATE         NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE products (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(150) NOT NULL,
    category        VARCHAR(60)  NOT NULL,
    brand           VARCHAR(60)  NOT NULL,
    price           NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    stock           INTEGER      NOT NULL CHECK (stock >= 0),
    warranty_months INTEGER      NOT NULL DEFAULT 12
);

CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(20) NOT NULL DEFAULT 'PLACED'
                        CHECK (status IN ('PLACED','SHIPPED','DELIVERED','CANCELLED')),
    total_amount    NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    shipping_city   VARCHAR(80) NOT NULL
);

-- order_items is the associative entity resolving the M:N between orders and products
CREATE TABLE order_items (
    order_item_id   SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id      INTEGER NOT NULL REFERENCES products(product_id),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0), -- price at time of purchase
    UNIQUE (order_id, product_id)
);

CREATE TABLE payments (
    payment_id      SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_method  VARCHAR(20) NOT NULL
                        CHECK (payment_method IN ('CARD','UPI','NETBANKING','COD','WALLET')),
    amount          NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    payment_status  VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                        CHECK (payment_status IN ('PENDING','SUCCESS','FAILED','REFUNDED')),
    paid_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE support_tickets (
    ticket_id       SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    order_id        INTEGER REFERENCES orders(order_id),
    subject         VARCHAR(150) NOT NULL,
    category        VARCHAR(40) NOT NULL
                        CHECK (category IN ('DELIVERY','PRODUCT_DEFECT','PAYMENT','RETURN','GENERAL')),
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED')),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- NOTE: no secondary indexes on customer_id columns here on purpose —
-- indexing_demo.py creates/drops them itself to show EXPLAIN ANALYZE before/after.
