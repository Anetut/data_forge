BEGIN;

CREATE TYPE payment_method_enum AS ENUM ('Cash', 'Card', 'Transfer');
CREATE TYPE payment_status_enum AS ENUM ('Pending', 'In Progress', 'Confirmed', 'Failed');
CREATE TYPE order_status_enum AS ENUM ('Pending', 'Shipped', 'Delivered', 'Cancelled', 'Returned');

CREATE TABLE manager(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    email VARCHAR(255) UNIQUE NOT NULL,
    hire_date DATE NOT NULL,
    contract_due_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE shipping_provider(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id UUID NOT NULL REFERENCES manager(id),
    name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    address VARCHAR(255),
    cost_per_shipment NUMERIC(10, 2),
    working_hours VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    favourite_shipping_provider_id UUID REFERENCES shipping_provider(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    address VARCHAR(255),
    billing_address VARCHAR(255),
    preferred_payment_method payment_method_enum,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE credit_card_information(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customer(id),
    card_token VARCHAR(255) NOT NULL,
    is_favourite BOOLEAN NOT NULL DEFAULT FALSE,
    card_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customer(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warehouse(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id UUID NOT NULL REFERENCES manager(id),
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    capacity INTEGER CHECK(capacity >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE seller(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE product(
    id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    weight NUMERIC(10,2),
    expiration_date DATE,
    size VARCHAR(50),
    colour VARCHAR(50),
    manufacturer VARCHAR(255),
    produced_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE category(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE product_item_junction(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES product(id),
    category_id UUID NOT NULL REFERENCES category(id),
    UNIQUE (product_id, category_id)
);

CREATE TABLE offer(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller(id),
    product_id UUID NOT NULL REFERENCES product(id),
    price NUMERIC (10,2) NOT NULL CHECK(price >0),
    discount_pct SMALLINT NOT NULL DEFAULT 0 CHECK(discount_pct >= 0 AND discount_pct < 100),
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE inventory(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warehouse_id UUID NOT NULL REFERENCES warehouse(id),
    offer_id UUID NOT NULL REFERENCES offer(id),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (warehouse_id, offer_id)
);

CREATE TABLE order_item(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    inventory_id UUID NOT NULL REFERENCES inventory(id),
    shipping_provider_id UUID NOT NULL REFERENCES shipping_provider(id),
    price_at_the_time NUMERIC(10,2) NOT NULL CHECK(price_at_the_time > 0),
    discount_pct_at_the_time SMALLINT NOT NULL DEFAULT 0 CHECK(discount_pct_at_the_time >= 0 AND discount_pct_at_the_time < 100),
    order_status order_status_enum NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    shipped_at TIMESTAMPTZ DEFAULT NULL,
    delivered_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_item_delivered_requires_shipped
    CHECK (delivered_at IS NULL OR shipped_at IS NOT NULL),
    CONSTRAINT order_item_delivered_after_shipped
    CHECK (delivered_at >= shipped_at)
);

CREATE TABLE rating(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_item_id UUID NOT NULL UNIQUE REFERENCES order_item(id),
    star_value SMALLINT NOT NULL CHECK(star_value >= 1 AND star_value <= 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_card_information_id UUID REFERENCES credit_card_information(id),
    order_id UUID NOT NULL UNIQUE REFERENCES orders(id),
    payment_method payment_method_enum NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment_attempt(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payment(id),
    status payment_status_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER manager_set_updated_at
    BEFORE UPDATE ON manager
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER shipping_provider_set_updated_at
    BEFORE UPDATE ON shipping_provider
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER customer_set_updated_at
    BEFORE UPDATE ON customer
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER credit_card_information_set_updated_at
    BEFORE UPDATE ON credit_card_information
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER orders_set_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER warehouse_set_updated_at
    BEFORE UPDATE ON warehouse
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER seller_set_updated_at
    BEFORE UPDATE ON seller
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER product_set_updated_at
    BEFORE UPDATE ON product
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER category_set_updated_at
    BEFORE UPDATE ON category
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER offer_set_updated_at
    BEFORE UPDATE ON offer
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER inventory_set_updated_at
    BEFORE UPDATE ON inventory
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER order_item_set_updated_at
    BEFORE UPDATE ON order_item
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER payment_set_updated_at
    BEFORE UPDATE ON payment
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER payment_attempt_set_updated_at
    BEFORE UPDATE ON payment_attempt
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMIT;
