import psycopg2

conn = psycopg2.connect(
    "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper",
    connect_timeout=8,
)
cur = conn.cursor()

for table in ("cases", "parts"):
    print(f"\n=== {table} ===")
    if table == "parts":
        where = "WHERE category = 'case'"
    else:
        where = ""
    cur.execute(f"SELECT COUNT(*) FROM {table} {where}")
    print("total", cur.fetchone()[0])
    for col in (
        "price",
        "price_new",
        "rrp",
        "rating",
        "review_count",
        "sales_velocity",
        "bestseller_rank",
        "source_url",
        "image_url",
    ):
        try:
            cur.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE {col} IS NOT NULL) AS filled,
                  COUNT(*) FILTER (WHERE {col} IS NULL) AS empty
                FROM {table} {where}
                """
            )
            filled, empty = cur.fetchone()
            print(f"  {col}: filled={filled} empty={empty}")
        except Exception as e:
            conn.rollback()
            print(f"  {col}: ERR {e}")

    if table == "parts":
        cur.execute(
            f"""
            SELECT COUNT(*) FILTER (WHERE source_site = 'Amazon') AS amazon,
                   COUNT(*) FILTER (WHERE source_site = 'Amazon' AND bestseller_rank IS NOT NULL) AS ranked
            FROM parts WHERE category = 'case'
            """
        )
        print("  amazon / ranked", cur.fetchone())

conn.close()
