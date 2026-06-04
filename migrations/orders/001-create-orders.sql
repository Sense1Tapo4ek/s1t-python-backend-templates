CREATE SCHEMA IF NOT EXISTS orders;

CREATE TABLE orders.orders (
    id           UUID PRIMARY KEY,
    customer_ref TEXT NOT NULL,
    currency     TEXT NOT NULL,
    total        NUMERIC(18, 2) NOT NULL,
    status       TEXT NOT NULL,
    placed_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE orders.order_lines (
    id          BIGSERIAL PRIMARY KEY,
    order_id    UUID NOT NULL REFERENCES orders.orders (id) ON DELETE CASCADE,
    product_ref TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    unit_price  NUMERIC(18, 2) NOT NULL
);

CREATE INDEX ix_orders_placed_at ON orders.orders (placed_at DESC);
CREATE INDEX ix_order_lines_order_id ON orders.order_lines (order_id);
