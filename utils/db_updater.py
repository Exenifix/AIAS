from utils.enums import FetchMode

version = 3


async def update_db(db):
    db_version: int = await db.execute(
        "SELECT version FROM version_data WHERE id = 0", fetch_mode=FetchMode.VAL
    )
    if db_version == version:
        db.log.info("Database is at latest version, no actions required.")
        return
    elif db_version < version:
        db.log.warning(
            "Incomatibilities detected. Database version: %s || Required version: %s. Executing compatibility scripts...",
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
            for sql in sqls:
                async with db._pool.acquire() as con:
                    async with con.transaction():
                        await con.execute(sql)

        await db.execute("UPDATE version_data SET version = $1 WHERE id = 0", version)
        db.log.info("Database is at latest version now!")
