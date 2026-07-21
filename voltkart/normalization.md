# VoltKart — Functional Dependencies and BCNF Proof

## 1. Relations and Attributes

- **customers**(customer_id, full_name, email, phone, city, state, pincode, signup_date)
- **products**(product_id, product_name, category, brand, price, stock, warranty_months)
- **orders**(order_id, customer_id, order_date, status, total_amount, shipping_city)
- **order_items**(order_item_id, order_id, product_id, quantity, unit_price)
- **payments**(payment_id, order_id, payment_method, amount, payment_status, paid_at)
- **support_tickets**(ticket_id, customer_id, order_id, subject, category, status, created_at)

## 2. Functional Dependencies (FDs)

### customers
```
customer_id -> full_name, email, phone, city, state, pincode, signup_date
email -> customer_id   (email is a candidate key — UNIQUE constraint)
```
Candidate keys: {customer_id}, {email}

### products
```
product_id -> product_name, category, brand, price, stock, warranty_months
```
Candidate key: {product_id}

### orders
```
order_id -> customer_id, order_date, status, total_amount, shipping_city
```
Candidate key: {order_id}
Note: `total_amount` is functionally determined by the set of (order_item.quantity * unit_price)
rows for that order — it is a derived/denormalized value cached for read performance, not an
independent fact. This is a deliberate, documented denormalization (common in OLTP order
systems) and does not violate BCNF since it still depends only on order_id transitively through
order_items, not on any non-key attribute of `orders` itself.

### order_items
```
order_item_id -> order_id, product_id, quantity, unit_price
(order_id, product_id) -> order_item_id, quantity, unit_price   (UNIQUE constraint)
```
Candidate keys: {order_item_id}, {order_id, product_id}
Note: `unit_price` is the price *at the time of purchase*, intentionally copied from
products.price to preserve historical accuracy even if products.price later changes. It depends
on (order_id, product_id) — the specific purchase event — not on product_id alone, so this is
not a transitive dependency on products; it's a distinct fact about the purchase.

### payments
```
payment_id -> order_id, payment_method, amount, payment_status, paid_at
```
Candidate key: {payment_id}
(order_id is not a key here because, in principle, a schema could allow retries/multiple payment
attempts per order; the current seed data uses 1:1 but the schema does not enforce it.)

### support_tickets
```
ticket_id -> customer_id, order_id, subject, category, status, created_at
```
Candidate key: {ticket_id}

## 3. BCNF Proof

BCNF requires: for every non-trivial FD X -> Y in a relation, X must be a superkey.

| Relation | FDs | LHS is superkey? | BCNF? |
|---|---|---|---|
| customers | customer_id -> (rest); email -> customer_id | Yes (both LHS are candidate keys) | ✅ |
| products | product_id -> (rest) | Yes | ✅ |
| orders | order_id -> (rest) | Yes | ✅ |
| order_items | order_item_id -> (rest); (order_id,product_id) -> (rest) | Yes (both are candidate keys) | ✅ |
| payments | payment_id -> (rest) | Yes | ✅ |
| support_tickets | ticket_id -> (rest) | Yes | ✅ |

In every relation, the only non-trivial FDs have a candidate key on the left-hand side. There are
no partial dependencies (no composite key has an attribute depending on only part of it — the
only composite candidate key, (order_id, product_id) in order_items, determines every other
attribute together, and order_item_id is a synthetic key covering the same functional role).
There are no transitive dependencies (no non-key attribute determines another non-key attribute
within the same relation — e.g., city does not determine state uniquely across all customers, and
category does not determine brand in products, since multiple brands exist per category).

**Conclusion: all six relations are in BCNF.**

## 4. Why the schema was split this way (2NF/3NF reasoning that led here)

- Splitting `order_items` out of `orders` removes a repeating group (an order can contain
  multiple products) — this is what gets the schema past 1NF into a proper relational form, and
  avoids the partial dependency that would exist if product details were duplicated per order row.
- Keeping `products.price` separate from `order_items.unit_price` avoids a transitive dependency
  that would otherwise let a price change silently corrupt historical order totals.
- `payments` is kept separate from `orders` (rather than adding payment columns to `orders`)
  because payment attributes (method, status, paid_at) depend on the payment event, not on the
  order itself — folding them in would introduce nulls for unpaid orders and mix two different
  entities' attributes in one relation.
- `support_tickets` references both `customers` and `orders` independently (order_id nullable)
  since a ticket can be a general query unrelated to any specific order.
