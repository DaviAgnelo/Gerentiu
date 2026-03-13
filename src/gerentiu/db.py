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

CREATE TABLE IF NOT EXISTS translation_pairs (
    guild_id INTERGER NOT NULL,
    channel_1_id INTERGER NOT NULL,
    channel_2_id INTERGER NOT NULL,
    lang_1 TEXT NOT NULL,
    lang_2 TEXT NOT NULL,
    PRIMARY KEY (guild_id, channel_1_id, channel_2_id)
);
"""

def _normalize_pair(
    channel_1_id: int,
    channel_2_id: int,
    lang_1: str,
    lang_2: str,
) -> tuple[int, int, str, str]:
    if channel_1_id <= channel_2_id:
        return channel_1_id, channel_2_id, lang_1, lang_2
    return channel_2_id, channel_1_id, lang_2, lang_1

#Comandos SQL que criam as duas tabelas principais da base de dados, a de contagem de mensagens e as rotas de tradução

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()

#Aqui, os comandos SQL citados anteriormente são executados na base de dados

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

#Aqui, é incrementado quantas mensagens foram enviadas em cada canal de cada servidor,
#para telemetria e saber quais canais são mais ocupados

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

#Aqui é feita a consulta de quantas mensagens foram enviadas em cada canal de cada servidor,
#com o total sendo enviado para o administrador que as consultou

async def get_translation_pair_by_channel(guild_id: int, channel_id: int) -> tuple[int, int, str, str] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT channel_1_id, channel_2_id, lang_1, lang_2
            FROM translation_pairs
            WHERE guild_id = ? AND (channel_1_id = ? OR channel_2_id = ?)
            """,
            (guild_id, channel_id, channel_id),

        ) as cur:
            row = await cur.fetchone()

            if row is None:
                return None

    ch1, ch2, lang_1, lang_2 = row
    return int(ch1), int(ch2), lang_1, lang_2

#Aqui é feita a consulta de quais são os canais configurados para serem traduzidos

async def set_translation_pair(
    guild_id: int,
    channel_1_id: int,
    channel_2_id: int,
    lang_1: str,
    lang_2: str,
) -> None:

    lang_1 = lang_1.strip().lower()
    lang_2 = lang_2.strip().lower()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
	    """
	    INSERT INTO translation_pairs (guild_id, channel_1_id, channel_2_id, lang_1, lang_2)
	    VALUES (?, ?, ?, ?, ?)
	    ON CONFLICT(guild_id, channel_1_id, channel_2_id)
	    DO UPDATE SET
                lang_1 = excluded.lang_1,
                lang_2 = excluded.lang_2
	    """,
            (guild_id, channel_1_id, channel_2_id, lang_1, lang_2),
        )
        await db.commit()

#Aqui é configurado a rota de tradução a ser salva no banco de dados e que será utilizada para realizar
#a tradução automática entre os canais configurados

async def remove_translation_pair(
    guild_id: int,
    channel_1_id: int,
    channel_2_id: int,
) -> int:
    channel_1_id, channel_2_id, _, _ = _normalize_pair(
        channel_1_id,
        channel_2_id,
        "",
        "",
    )

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
	    """
	    DELETE FROM translation_pairs
	    WHERE guild_id = ? AND channel_1_id = ? AND channel_2_id = ?
	    """,
            (guild_id, channel_1_id, channel_2_id),
        )
        await db.commit()
        return cur.rowcount

#Aqui é onde as rotas de tradução são removidas da base de dados

async def list_translation_pairs(guild_id: int) -> list[tuple[int, int, str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
	    """
	    SELECT channel_1_id, channel_2_id, lang_1, lang_2
	    FROM translation_pairs
	    WHERE guild_id = ?
	    ORDER BY channel_1_id, channel_2_id
	    """,
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()

    return [(int(ch1), int(ch2), lang_1, lang_2) for ch1, ch2, lang_1, lang_2 in rows]

#Aqui é feita a consulta de quais rotas de tradução existem em uma servidor específico
#retornando os resultados para quem consultou
