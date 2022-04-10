from utils.enums import FetchMode

version = 1


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
            match v:
                case 1:
                    await db.execute(
                        "ALTER TABLE guilds ALTER COLUMN antispam_enabled SET DEFAULT TRUE"
                    )
                    await db.execute(
                        "ALTER TABLE guilds ALTER COLUMN blacklist_enabled SET DEFAULT TRUE"
                    )

        await db.execute("UPDATE version_data SET version = $1 WHERE id = 0", version)
        db.log.info("Database is at latest version now!")

    await db.close()
