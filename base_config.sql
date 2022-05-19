CREATE TABLE IF NOT EXISTS data
(
    id           SERIAL PRIMARY KEY,
    content      TEXT UNIQUE,
    total_chars  INT,
    unique_chars INT,
    total_words  INT,
    unique_words INT,
    is_spam      BOOLEAN,
    downvotes    INT DEFAULT 0,
    upvotes      INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guilds
(
    id                       BIGINT UNIQUE NOT NULL,
    warnings_threshold       INT      DEFAULT 3 CHECK (warnings_threshold > 0 AND warnings_threshold <= 10),
    timeout_duration         INT      DEFAULT 15 CHECK (timeout_duration > 0 AND timeout_duration < 80000),

    antispam_enabled         BOOLEAN  DEFAULT TRUE,
    antispam_ignored         BIGINT[] DEFAULT ARRAY []::BIGINT[],

    blacklist_enabled        BOOLEAN  DEFAULT TRUE,
    blacklist_ignored        BIGINT[] DEFAULT ARRAY []::BIGINT[],
    blacklist_common         TEXT[]   DEFAULT ARRAY []::TEXT[] CHECK (ARRAY_LENGTH(blacklist_common, 1) <= 50),
    blacklist_wild           TEXT[]   DEFAULT ARRAY []::TEXT[] CHECK (ARRAY_LENGTH(blacklist_wild, 1) <= 50),
    blacklist_super          TEXT[]   DEFAULT ARRAY []::TEXT[] CHECK (ARRAY_LENGTH(blacklist_super, 1) <= 50),
    blacklist_filter_enabled BOOLEAN  DEFAULT TRUE,

    whitelist_enabled        BOOLEAN  DEFAULT FALSE,
    whitelist_characters     TEXT     DEFAULT 'abcdefghijklmnopqrstuvwxyz!@#$%^&*(){}[]<>-_=+?~`:;''"/\|<>.,1234567890',
    whitelist_ignored        BIGINT[] DEFAULT ARRAY []::BIGINT[],

    nickfilter_enabled       BOOLEAN  DEFAULT TRUE,
    nickfilter_ignored       BIGINT[] DEFAULT ARRAY []::BIGINT[],

    antiraid_enabled         BOOLEAN  DEFAULT FALSE,
    antiraid_join_interval   INT      DEFAULT 30,
    antiraid_members_limit   INT      DEFAULT 5,
    antiraid_punishment      INT      DEFAULT 1, -- decodification in utils.enums.AntiraidPunishment

    log_channel              BIGINT,

    automod_managers         BIGINT[] DEFAULT ARRAY []::BIGINT[]
);

CREATE TABLE IF NOT EXISTS version_data
(
    id      INT UNIQUE,
    version INT NOT NULL
);

INSERT INTO version_data (id, version)
VALUES (0, 8)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS rules
(
    id        BIGINT NOT NULL,
    rule_key  TEXT,
    rule_text TEXT,
    UNIQUE (id, rule_key)
);

CREATE TABLE IF NOT EXISTS stats
(
    id              INT UNIQUE NOT NULL, -- decodification in utils.enums.Stat
    applied_totally INT DEFAULT 0,
    applied_daily   INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resets
(
    id    INT UNIQUE NOT NULL, -- 0 is daily
    value TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
