import asyncio
import os
import sys
from pickle import dump

import asyncpg
from dotenv import load_dotenv
from exencolorlogs import Logger
from numpy import array
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

log = Logger("TRAIN")

load_dotenv()
DATABASE = os.getenv("DATABASE")
HOST = os.getenv("HOST")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")

if DATABASE is None:
    log.critical(".env file not filled up properly")
    sys.exit(1)


async def main():
    log.info("Establishing connection to the database...")
    con: asyncpg.Connection = await asyncpg.connect(
        database=DATABASE, host=HOST, user=USER, password=PASSWORD
    )
    records = await con.fetch(
        "SELECT total_chars, unique_chars, total_words, unique_words, is_spam FROM data WHERE is_spam IS NOT NULL"
    )
    await con.close()
    log.info("Preparing data... Amount of records: %s", len(records))
    data = array([list(r.values()) for r in records])
    train_x = data[:, 0:4]
    train_y = data[:, 4]

    model = RandomForestClassifier()
    log.info(
        "Estimated accuracy: %.2f%%",
        cross_val_score(model, train_x, train_y).mean() * 100,
    )
    log.info("Training...")
    model.fit(train_x, train_y)

    if not os.path.exists("./ai/models"):
        log.warning("Directory ./ai/models did not exist so was autogenerated")
        os.mkdir("./ai/models")

    with open("./ai/models/model.ai", "wb") as f:
        dump(model, f)
        log.info("File saved successfully to ./ai/models/model.ai")


asyncio.run(main())
