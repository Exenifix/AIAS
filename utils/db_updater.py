from ai.analyser import analyse_sample

from utils.enums import FetchMode

version = 7


async def update_db(db):
    db.log.info("Checking database version incompatibilities...")
    db_version: int = await db.execute(
        "SELECT version FROM version_data WHERE id = 0", fetch_mode=FetchMode.VAL
    )
    if db_version == version:
        db.log.ok("Database is at latest version, no actions required.")
        return
    elif db_version < version:
        db.log.warning(
            "Incompatibilities detected. Database version: %s || Required version: %s. Executing compatibility scripts...",
            db_version,
            version,
        )
        for v in range(db_version + 1, version + 1):
            db.log.info("Executing compatibility script #%s", v)
            sqls = []
            match v:
                case 1:
                    sqls = [
                        "ALTER TABLE guilds ALTER COLUMN antispam_enabled SET DEFAULT TRUE",
                        "ALTER TABLE guilds ALTER COLUMN blacklist_enabled SET DEFAULT TRUE",
                    ]
                case 2:
                    sqls = [
                        "ALTER TABLE guilds ADD COLUMN warnings_threshold INT DEFAULT 3 CHECK(warnings_threshold > 0 AND warnings_threshold <= 10)",
                        "ALTER TABLE guilds ADD COLUMN timeout_duration INT DEFAULT 15 CHECK(timeout_duration > 0 AND timeout_duration < 80000)",
                        "ALTER TABLE guilds ADD COLUMN whitelist_enabled BOOLEAN DEFAULT FALSE",
                        "ALTER TABLE guilds ADD COLUMN whitelist_characters TEXT DEFAULT 'abcdefghijklmnopqrstuvwxyz!@#$%^&*(){}[]<>-_=+?~`:;''\"/\\|<>.,'",
                        "ALTER TABLE guilds ADD COLUMN nickfilter_enabled BOOLEAN DEFAULT TRUE",
                        "ALTER TABLE guilds ADD COLUMN nickfilter_ignored BIGINT[] DEFAULT ARRAY[]::BIGINT[]",
                        "ALTER TABLE guilds ADD COLUMN log_channel BIGINT",
                    ]
                case 3:
                    sqls = [
                        "ALTER TABLE guilds ADD COLUMN whitelist_ignored BIGINT[] DEFAULT ARRAY[]::BIGINT[]"
                    ]
                case 4:
                    sqls = [
                        "ALTER TABLE guilds ALTER COLUMN whitelist_characters SET DEFAULT 'abcdefghijklmnopqrstuvwxyz!@#$%^&*(){}[]<>-_=+?~`:;''\"/\\|<>.,1234567890'",
                        "UPDATE guilds \
                            SET whitelist_characters = 'abcdefghijklmnopqrstuvwxyz!@#$%^&*(){}[]<>-_=+?~`:;''\"/\\|<>.,1234567890' \
                            WHERE whitelist_characters = 'abcdefghijklmnopqrstuvwxyz!@#$%^&*(){}[]<>-_=+?~`:;''\"/\\|<>.,'",
                    ]
                case 5:
                    db.log.info("Compatibility script #5 was moved to #7")
                case 6:
                    sqls = [
                        "ALTER TABLE guilds ADD COLUMN antiraid_enabled BOOLEAN DEFAULT FALSE",
                        "ALTER TABLE guilds ADD COLUMN antiraid_join_interval INT DEFAULT 30",
                        "ALTER TABLE guilds ADD COLUMN antiraid_members_limit INT DEFAULT 5",
                        "ALTER TABLE guilds ADD COLUMN antiraid_punishment INT DEFAULT 1",
                    ]
                case 7:
                    db.log.info("Executing data correction algorithm (DB version 7)...")
                    records = await db.execute(
                        "SELECT id, content FROM data WHERE content LIKE '%<%>%'",
                        fetch_mode=FetchMode.ALL,
                    )
                    db.log.info("Got %s invalid records", len(records))
                    for r in records:
                        tc, uc, tw, uw, content = analyse_sample(r["content"])
                        await db.execute(
                            "UPDATE data SET total_chars = $1, unique_chars = $2, total_words = $3, unique_words = $4, content = $5 WHERE id = $6",
                            tc,
                            uc,
                            tw,
                            uw,
                            content,
                            r["id"],
                        )

                    db.log.warning(
                        "Data correction successful, please retrain the model!"
                    )
            for sql in sqls:
                async with db._pool.acquire() as con:
                    async with con.transaction():
                        await con.execute(sql)

        await db.execute("UPDATE version_data SET version = $1 WHERE id = 0", version)
        db.log.ok("Database is at latest version now!")
