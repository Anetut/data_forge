-- Inserts no longer accept a client-supplied updated_at, see reason in findings, extraction test.

CREATE OR REPLACE TRIGGER manager_set_updated_at
    BEFORE INSERT OR UPDATE ON manager
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER shipping_provider_set_updated_at
    BEFORE INSERT OR UPDATE ON shipping_provider
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER customer_set_updated_at
    BEFORE INSERT OR UPDATE ON customer
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER credit_card_information_set_updated_at
    BEFORE INSERT OR UPDATE ON credit_card_information
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER orders_set_updated_at
    BEFORE INSERT OR UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER warehouse_set_updated_at
    BEFORE INSERT OR UPDATE ON warehouse
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER seller_set_updated_at
    BEFORE INSERT OR UPDATE ON seller
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER product_set_updated_at
    BEFORE INSERT OR UPDATE ON product
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER category_set_updated_at
    BEFORE INSERT OR UPDATE ON category
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER offer_set_updated_at
    BEFORE INSERT OR UPDATE ON offer
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER inventory_set_updated_at
    BEFORE INSERT OR UPDATE ON inventory
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER order_item_set_updated_at
    BEFORE INSERT OR UPDATE ON order_item
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER payment_set_updated_at
    BEFORE INSERT OR UPDATE ON payment
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER payment_attempt_set_updated_at
    BEFORE INSERT OR UPDATE ON payment_attempt
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

