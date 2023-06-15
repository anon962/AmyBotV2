import sqlite3

from config import paths


def get_db() -> sqlite3.Connection:
    DB = sqlite3.connect(paths.DATA_DIR / "db.sqlite")
    DB.row_factory = sqlite3.Row
    return DB


def create_tables():
    DB = get_db()

    # Super
    with DB:
        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_auctions (
                id                          TEXT,

                title                       TEXT    NOT NULL,
                end_time                    REAL    NOT NULL,
                is_complete                 REAL,
                last_fetch_time             REAL,

                PRIMARY KEY (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_equips (
                id                  TEXT,
                id_auction          TEXT,

                name                TEXT        NOT NULL,
                eid                 INTEGER     NOT NULL,
                key                 TEXT        NOT NULL,
                is_isekai           INTEGER     NOT NULL,
                level               INTEGER,
                stats               TEXT        NOT NULL,       --json

                price               INTEGER,
                bid_link            TEXT,
                next_bid            INTEGER     NOT NULL,
                buyer               TEXT,
                seller              TEXT        NOT NULL,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES super_auctions (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_mats (
                id                  TEXT,
                id_auction          TEXT,

                name                TEXT        NOT NULL,
                quantity            INTEGER     NOT NULL,
                unit_price          REAL,

                price               INTEGER,
                bid_link            TEXT,
                next_bid            INTEGER     NOT NULL,
                buyer               TEXT,
                seller              TEXT        NOT NULL,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES super_auctions (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_fails (
                id              TEXT,
                id_auction      TEXT,
                                
                summary         TEXT,
                html            TEXT,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES super_auctions (id)
            ) STRICT;
            """
        )

    # Kedama
    with DB:
        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS kedama_auctions (
                id                          TEXT,

                title_short                 TEXT    NOT NULL,
                title                       TEXT    NOT NULL,
                start_time                  REAL    NOT NULL,
                is_complete                 REAL,
                last_fetch_time             REAL,

                PRIMARY KEY (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS kedama_equips (
                id                  TEXT,
                id_auction          TEXT,

                name                TEXT        NOT NULL,
                eid                 INTEGER     NOT NULL,
                key                 TEXT        NOT NULL,
                is_isekai           INTEGER     NOT NULL,
                level               INTEGER,
                stats               TEXT        NOT NULL,       --json

                price               INTEGER,
                start_bid           INTEGER,
                post_index          INTEGER,
                buyer               TEXT,
                seller              TEXT,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES kedama_auctions (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS kedama_mats (
                id                  TEXT,
                id_auction          TEXT,

                name                TEXT        NOT NULL,
                quantity            INTEGER     NOT NULL,
                unit_price          REAL,

                price               INTEGER,
                start_bid           INTEGER,
                post_index          INTEGER,
                buyer               TEXT,
                seller              TEXT,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES kedama_auctions (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS kedama_fails_item (
                id              TEXT,
                id_auction      TEXT,

                summary         TEXT,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES kedama_auctions (id)
            ) STRICT;
            """
        )

    # Discord
    with DB:
        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS discord_watch_more (
                id              INTEGER,

                channel         INTEGER      NOT NULL,
                user            INTEGER     NOT NULL,
                pages           TEXT        NOT NULL,
                last_visible    INTEGER     NOT NULL,

                PRIMARY KEY (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS discord_watch_change (
                id              INTEGER,

                channel         INTEGER      NOT NULL,
                user            INTEGER     NOT NULL,

                PRIMARY KEY (id)
            ) STRICT;
            """
        )

    # Lottery
    with DB:
        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS lottery_weapon (
                id          INTEGER,

                date        REAL        NOT NULL,
                tickets     INTEGER     NOT NULL,
                
                -- Grand prize (equip)
                "1_prize"     TEXT,
                "1_user"      TEXT        NOT NULL,

                -- Core prize (prize column isn't important)
                "1b_prize"    TEXT        NOT NULL,
                "1b_user"     TEXT,

                -- Prize column contains json: '[quantity, "item_name"]'
                "2_prize"     TEXT        NOT NULL,
                "2_user"      TEXT        NOT NULL,
                "3_prize"     TEXT        NOT NULL,
                "3_user"      TEXT        NOT NULL,
                "4_prize"     TEXT        NOT NULL,
                "4_user"      TEXT        NOT NULL,
                "5_prize"     TEXT        NOT NULL,
                "5_user"      TEXT        NOT NULL,

                PRIMARY KEY (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
                CREATE TABLE IF NOT EXISTS lottery_armor (
                    id          INTEGER,

                    date        REAL        NOT NULL,   --start time
                    tickets     INTEGER     NOT NULL,
                    
                    -- Grand prize (equip)
                    "1_prize"     TEXT,
                    "1_user"      TEXT        NOT NULL,

                    -- Core prize (prize column isn't important)
                    "1b_prize"    TEXT        NOT NULL,
                    "1b_user"     TEXT,

                    -- Prize column contains json: '[quantity, "item_name"]'
                    "2_prize"     TEXT        NOT NULL,
                    "2_user"      TEXT        NOT NULL,
                    "3_prize"     TEXT        NOT NULL,
                    "3_user"      TEXT        NOT NULL,
                    "4_prize"     TEXT        NOT NULL,
                    "4_user"      TEXT        NOT NULL,
                    "5_prize"     TEXT        NOT NULL,
                    "5_user"      TEXT        NOT NULL,

                    PRIMARY KEY (id)
                ) STRICT;
                """
        )
