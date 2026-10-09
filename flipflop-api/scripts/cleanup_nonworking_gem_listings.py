"""Remove Gem Radar listings explicitly advertised as non-working or parts only."""

from sqlalchemy import create_engine, text


DATABASE_URL = "postgresql://flipper:flipper@127.0.0.1:5432/pcflipper"
TITLE_PATTERN = r"\m(broken|not[-[:space:]]+working|parts?[[:space:]]+only)\M"


def main() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TEMP TABLE gem_radar_reject_targets "
                "(listing_id varchar(255) PRIMARY KEY) ON COMMIT DROP"
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO gem_radar_reject_targets
                SELECT DISTINCT listing_id
                FROM (
                    SELECT listing_id FROM gem_radar_scored_listings WHERE title ~* :pattern
                    UNION
                    SELECT listing_id FROM gem_radar_listing_observations WHERE title ~* :pattern
                ) AS matches
                """
            ),
            {"pattern": TITLE_PATTERN},
        )
        connection.execute(
            text(
                "CREATE TEMP TABLE gem_radar_reject_cpks "
                "(cpk varchar(64) PRIMARY KEY) ON COMMIT DROP"
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO gem_radar_reject_cpks
                SELECT DISTINCT cpk
                FROM (
                    SELECT scored.cpk
                    FROM gem_radar_scored_listings AS scored
                    JOIN gem_radar_reject_targets AS target USING (listing_id)
                    UNION
                    SELECT listing_cpk.cpk
                    FROM gem_radar_listing_cpk AS listing_cpk
                    JOIN gem_radar_reject_targets AS target USING (listing_id)
                    UNION
                    SELECT listing_price.cpk
                    FROM gem_radar_cpk_listing_price AS listing_price
                    JOIN gem_radar_reject_targets AS target USING (listing_id)
                ) AS cpks
                WHERE cpk IS NOT NULL
                """
            )
        )

        statements = {
            "market_price_caches": """
                DELETE FROM gem_radar_cpk_market_price AS market_price
                USING gem_radar_reject_cpks AS target
                WHERE market_price.cpk = target.cpk
            """,
            "cpk_listing_prices": """
                DELETE FROM gem_radar_cpk_listing_price AS listing_price
                USING gem_radar_reject_targets AS target
                WHERE listing_price.listing_id = target.listing_id
            """,
            "listing_cpks": """
                DELETE FROM gem_radar_listing_cpk AS listing_cpk
                USING gem_radar_reject_targets AS target
                WHERE listing_cpk.listing_id = target.listing_id
            """,
            "observations": """
                DELETE FROM gem_radar_listing_observations AS observation
                USING gem_radar_reject_targets AS target
                WHERE observation.listing_id = target.listing_id
            """,
            "scored_listings": """
                DELETE FROM gem_radar_scored_listings AS scored
                USING gem_radar_reject_targets AS target
                WHERE scored.listing_id = target.listing_id
            """,
        }
        for name, statement in statements.items():
            print(f"{name}: {connection.execute(text(statement)).rowcount}")


if __name__ == "__main__":
    main()
