def get_all_customers(cur):
    cur.execute("SELECT customer_id, full_name FROM customers ORDER BY full_name")
    return cur.fetchall()
