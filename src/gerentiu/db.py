import aiosqlite

DB_PATH = "gerentiu.sqlite3"

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS channel_message_counts (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS translation_routes (
    guild_id INTERGER NOT NULL,
    source_channel_id INTERGER NOT NULL,
    target_channel_id INTERGET NOT NULL,
    target_lang TEXT NOT NULL,
    PRIMARY KEY (guild_id, source_channel_id, target_channel_id)
);
"""
async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()

async def increment_channel_count(guild_id: int, channel_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO channel_message_counts (guild_id, channel_id, message_count)
            VALUES (?, ?, 1)
            ON CONFLICT(guild_id, channel_id)
            DO UPDATE SET message_count = message_count + 1
            """,
            (guild_id, channel_id),
        )
        await db.commit()

async def get_guild_totals(guild_id: int) -> tuple[int, list[tuple[int, int]]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT SUM(message_count) FROM channel_message_counts WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
            total = int(row[0] or 0)

        async with db.execute(
            """
            SELECT channel_id, message_count
            FROM channel_message_counts
            WHERE guild_id = ?
            ORDER BY message_count DESC
            """,
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()

    return total, [(int(ch), int(cnt)) for ch, cnt in rows]

async def get_translation_targets(guild_id: int, source_channel_id: int) -> list[tuple[int,str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT target_channel_id, target_lang
            FROM translation_routes
            WHERE guild_id = ? AND source_channel_id = ?
            """,
            (guild_id, source_channel_id),

        ) as cur:
            rows = await cur.fetchall()

    return [(int(ch_id), lang) for ch_id, lang in rows]

async def set_translation_route(
    guild_id: int,
    source_channel_id: int,
    target_channel_id: int,
    target_lang: str,
) -> None:

    target_lang = target_lang.strip().lower()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
	    """
	    INSERT INTO translation_routes (guild_id, source_channel_id, target_channel_id, target_lang)
	    VALUES (?, ?, ?, ?)
	    ON CONFLICT(guild_id, source_channel_id, target_channel_id)
	    DO UPDATE SET target_lang = excluded.target_lang
	    """,
            (guild_id, source_channel_id, target_channel_id, target_lang),
        )
        await db.commit()

async def remove_translation_route(
    guild_id: int,
    source_channel_id: int,
    target_channel_id: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
	    """
	    DELETE FROM translation_routes
	    WHERE guild_id = ? AND source_channel_id = ? AND target_channel_id = ?
	    """,
            (guild_id, source_channel_id, target_channel_id),
        )
        await db.commit()
        return cur.rowcount

async def get_translation_targets(guild_id: int, source_channel_id: int) -> list[tuple[int,str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT target_channel_id, target_lang
            FROM translation_routes
            WHERE guild_id = ? AND source_channel_id = ?
            """,
            (guild_id, source_channel_id),

        ) as cur:
            rows = await cur.fetchall()

    return [(int(ch_id), lang) for ch_id, lang in rows]


async def list_translation_routes(guild_id: int) -> list[tuple[int, int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
	    """
	    SELECT source_channel_id, target_channel_id, target_lang
	    FROM translation_routes
	    WHERE guild_id = ?
	    ORDER BY source_channel_id, target_channel_id
	    """,
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()

    return [(int(s), int(t), str(lang)) for s, t, lang in rows]
