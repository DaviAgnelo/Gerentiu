import aiosqlite

#Importa o módulo aiosqlite para que possam ser usados comandos de base de dados em SQLite

DB_PATH = "gerentiu.sqlite3"

#Cria o arquivo da base de dados

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS channel_message_counts (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS translation_hubs (
    hub_id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS translation_hub_channels (
    hub_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    PRIMARY KEY (hub_id, channel_id),
    UNIQUE(channel_id),
    FOREIGN KEY (hub_id) REFERENCES translation_hubs(hub_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS antispam_config (
    guild_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    max_messages INTEGER NOT NULL DEFAULT 5,
    max_punishment TEXT NOT NULL DEFAULT 'timeout',
    interval_seconds INTEGER NOT NULL DEFAULT 8
);

CREATE TABLE IF NOT EXISTS antispam_punishments (
    guild_id INTEGER NOT NULL,
    strike_count INTEGER NOT NULL,
    action TEXT NOT NULL,
    timeout_seconds INTEGER,
    PRIMARY KEY (guild_id, strike_count)
);

CREATE TABLE IF NOT EXISTS antispam_violations (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    strikes INTEGER NOT NULL DEFAULT 0,
    last_violation_at INTEGER,
    PRIMARY KEY (guild_id, user_id)
);
"""

#Comandos SQL que criam as duas tabelas principais da base de dados, a de contagem de mensagens e as rotas de tradução

def _connect():
    return aiosqlite.connect(DB_PATH)

async def init_db() -> None:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(CREATE_TABLES_SQL)

        try:
            await db.execute("""
                ALTER TABLE antispam_config
                ADD COLUMN max_punishment TEXT NOT NULL DEFAULT 'timeout'
            """)
        except aiosqlite.OperationalError:
            pass

        await db.commit()

#Aqui, os comandos SQL citados anteriormente são executados na base de dados

async def increment_channel_count(guild_id: int, channel_id: int) -> None:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
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

#Aqui, é incrementado quantas mensagens foram enviadas em cada canal de cada servidor,
#para telemetria e saber quais canais são mais ocupados

async def get_guild_totals(guild_id: int) -> tuple[int, list[tuple[int, int]]]:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
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

#Aqui é feita a consulta de quantas mensagens foram enviadas em cada canal de cada servidor,
#com o total sendo enviado para o administrador que as consultou

async def get_translation_hub_by_channel(guild_id: int, channel_id: int) -> dict | None:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        async with db.execute(
            """
            SELECT h.hub_id, h.name, thc.language
            FROM translation_hub_channels thc
            JOIN translation_hubs h
                ON h.hub_id = thc.hub_id
            WHERE h.guild_id = ? AND thc.channel_id = ?
            """,
            (guild_id, channel_id),

        ) as cur:
            source_row = await cur.fetchone()

        if source_row is None:
            return None

        hub_id, hub_name, source_language = source_row

        async with db.execute(
            """
            SELECT channel_id, language
            FROM translation_hub_channels
            WHERE hub_id = ? AND channel_id != ?
            ORDER BY channel_id
            """,
            (hub_id, channel_id),
        ) as cur:
            rows = await cur.fetchall()

    return {
        "hub_id": int(hub_id),
        "hub_name": hub_name,
        "source_channel_id": int(channel_id),
        "source_language": source_language,
        "targets": [
            {
                "channel_id": int(target_channel_id),
                "language": target_language,
            }
            for target_channel_id, target_language in rows
        ],
    }


#Aqui é feita a consulta de quais são os canais configurados para serem traduzidos

async def create_translation_hub(guild_id: int, name: str) -> int:
    name = name.strip()

    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        cur = await db.execute(
            """
            INSERT INTO translation_hubs (guild_id, name)
            VALUES (?, ?)
            """,
            (guild_id, name)
        )
        await db.commit()
        return int(cur.lastrowid)

async def delete_translation_hub(guild_id: int, hub_id: int) -> int:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        cur = await db.execute(
            """
            DELETE FROM translation_hubs
            WHERE guild_id = ? AND hub_id = ?
            """,
            (guild_id, hub_id),
        )
        await db.commit()
        return cur.rowcount

async def add_channel_to_hub(
    guild_id: int,
    hub_id: int,
    channel_id: int,
    language: str,
):

    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        # Garante que o hub pertence ao servidor
        async with db.execute(
            """
            SELECT 1
            FROM translation_hubs
            WHERE guild_id = ? AND hub_id = ?
            """,
            (guild_id, hub_id),
        ) as cur:
            hub_exists = await cur.fetchone()

        if hub_exists is None:
            raise ValueError("Hub não encontrado nesse servidor.")

        await db.execute(
            """
            INSERT INTO translation_hub_channels (hub_id, channel_id, language)
            VALUES (?, ?, ?)
            ON CONFLICT(hub_id, channel_id)
            DO UPDATE SET language = excluded.language
            """,
            (hub_id, channel_id, language),
        )
        await db.commit()

#Aqui é configurado a rota de tradução a ser salva no banco de dados e que será utilizada para realizar
#a tradução automática entre os canais configurados

async def remove_channel_from_hub(
    guild_id: int,
    hub_id: int,
    channel_id: int,
) -> int:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        cur = await db.execute(
            """
            DELETE FROM translation_hub_channels
            WHERE hub_id = ?
              AND channel_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM translation_hubs h
                  WHERE h.hub_id = translation_hub_channels.hub_id
                    AND h.guild_id = ?
              )
            """,
            (hub_id, channel_id, guild_id),
        )
        await db.commit()
        return cur.rowcount

#Aqui é onde as rotas de tradução são removidas da base de dados

async def list_translation_hubs(guild_id: int) -> list[dict]:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        async with db.execute(
	    """
	    SELECT h.hub_id, h.name, thc.channel_id, thc.language
        FROM translation_hubs h
        LEFT JOIN translation_hub_channels thc
            ON thc.hub_id = h.hub_id
        WHERE h.guild_id = ?
        ORDER BY h.hub_id, thc.channel_id
	    """,
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    hubs_map: dict[int, dict] = {}

    for hub_id, hub_name, channel_id, language in rows:
        hub_id = int(hub_id)

        if hub_id not in hubs_map:
            hubs_map[hub_id] = {
                "hub_id": hub_id,
                "hub_name": hub_name,
                "channels": [],
            }

        if channel_id is not None:
            hubs_map[hub_id]["channels"].append(
                {
                    "channel_id": int(channel_id),
                    "language": language,
                }
            )

    return list(hubs_map.values())


#Aqui é feita a consulta de quais rotas de tradução existem em uma servidor específico
#retornando os resultados para quem consultou

async def set_antispam_enabled(guild_id: int, enabled: bool):
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("""
            INSERT INTO antispam_config (guild_id, enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                enabled = excluded.enabled
        """, (guild_id, int(enabled)))
        await db.commit()

async def get_antispam_config(guild_id: int) -> dict:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        cursor = await db.execute("""
            SELECT enabled, max_messages, interval_seconds, max_punishment
            FROM antispam_config
            WHERE guild_id = ?
        """, (guild_id,))
        row = await cursor.fetchone()

    if row is None:
        return {
            "enabled": False,
            "max_messages": 5,
            "interval_seconds": 8,
            "max_punishment": "timeout"
        }
    return {
        "enabled": bool(row[0]),
        "max_messages": row[1],
        "interval_seconds": row[2],
        "max_punishment": row[3]
    }

async def set_antispam_max_messages(guild_id, value):
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("""
        INSERT INTO antispam_config (guild_id, max_messages)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            max_messages = excluded.max_messages
        """, (guild_id, value))
        await db.commit()

async def set_antispam_interval_seconds(guild_id: int, value: int):
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("""
            INSERT INTO antispam_config (guild_id, interval_seconds)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                interval_seconds = excluded.interval_seconds
            """, (guild_id, value))
        await db.commit()

async def set_antispam_max_punishment(guild_id: int, action: str):
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("""
            INSERT INTO antispam_config (guild_id, max_punishment)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                max_punishment = excluded.max_punishment
            """, (guild_id, action))
        await db.commit()

async def get_antispam_strikes(guild_id: int, user_id: int) -> int:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        async with db.execute("""
            SELECT strikes
            FROM antispam_violations
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def set_antispam_strikes(guild_id: int, user_id: int, strikes: int):
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("""
            INSERT INTO antispam_violations (guild_id, user_id, strikes)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                strikes = excluded.strikes
        """, (guild_id, user_id, strikes))
        await db.commit()

async def increment_antispam_strikes(guild_id: int, user_id: int) -> int:
    current = await get_antispam_strikes(guild_id, user_id)
    new_value = current + 1
    await set_antispam_strikes(guild_id, user_id, new_value)
    return new_value

