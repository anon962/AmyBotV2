import sqlite3

from config import paths


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(paths.DATA_DIR / "db.sqlite")
    db.row_factory = sqlite3.Row
    return db


def create_tables():
    db = get_db()

    # Super
    with db:
        db.execute(
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

        db.execute(
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

        db.execute(
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

        db.execute(
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
    with db:
        db.execute(
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

        db.execute(
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

        db.execute(
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

        db.execute(
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
    with db:
        db.execute(
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

        db.execute(
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
    with db:
        db.execute(
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

        db.execute(
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

        db.execute(
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

        db.execute(
            """
                CREATE TABLE IF NOT EXISTS equips (
                    id              INTEGER         PRIMARY KEY,
                    key             TEXT            NOT NULL,

                    data            TEXT            NOT NULL,       --json

                    is_deleted      INTEGER         NOT NULL,
                    updated_at      TEXT            NOT NULL
                ) STRICT;
            """
        )

        db.execute(
            """
                CREATE TABLE IF NOT EXISTS equip_html (
                    id              INTEGER,
                    created_at      TEXT            NOT NULL,

                    html            TEXT            NOT NULL,

                    FOREIGN KEY (id) REFERENCES equips (id)
                ) STRICT;
            """
        )
