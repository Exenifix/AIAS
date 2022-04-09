CREATE TABLE IF NOT EXISTS data (
    id SERIAL PRIMARY KEY,
    content TEXT UNIQUE,
    total_chars INT,
    unique_chars INT,
    total_words INT,
    unique_words INT,
    is_spam BOOLEAN,
    downvotes INT DEFAULT 0,
    upvotes INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guilds (
    id BIGINT UNIQUE NOT NULL,

    antispam_enabled BOOLEAN DEFAULT FALSE,
    antispam_ignored BIGINT[] DEFAULT ARRAY[]::BIGINT[],

    blacklist_enabled BOOLEAN DEFAULT FALSE,
    blacklist_ignored BIGINT[] DEFAULT ARRAY[]::BIGINT[],

    blacklist_common TEXT[] DEFAULT ARRAY[]::TEXT[] CHECK(ARRAY_LENGTH(blacklist_common, 1) <= 50),
    blacklist_wild TEXT[] DEFAULT ARRAY[]::TEXT[] CHECK(ARRAY_LENGTH(blacklist_wild, 1) <= 50),
    blacklist_super TEXT[] DEFAULT ARRAY[]::TEXT[] CHECK(ARRAY_LENGTH(blacklist_super, 1) <= 50),

    blacklist_filter_enabled BOOLEAN DEFAULT TRUE,

    automod_managers BIGINT[] DEFAULT ARRAY[]::BIGINT[]
);
