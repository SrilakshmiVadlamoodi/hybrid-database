def get_all_customers(cur):
    cur.execute("SELECT customer_id, full_name FROM customers ORDER BY full_name")
    return cur.fetchall()


def parse_customer_id(value: str | None) -> int | None:
    """An empty '?customer_id=' (as opposed to an omitted one) still reaches
    routes as a string; treat both the same rather than 422ing on it."""
    if not value:
        return None
    return int(value)
