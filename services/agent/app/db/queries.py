"""
Database queries for agent tools.
Ported from huquqai/lib/ai/rag-search.ts
"""

import asyncio
from app.db.client import query

# Major Moroccan law codes: full name → DB abbreviation used in articles.loi_numero
# These are the foundational codes; amendments have separate numeros.
LAW_ABBREVIATIONS: dict[str, str] = {
    "قانون الالتزامات والعقود": "ق.ل.ع",
    "القانون الجنائي": "ق.ج",
    "قانون المسطرة المدنية": "ق.م.م",
    "قانون المسطرة الجنائية": "ق.م.ج",
    "مدونة الأسرة": "70.03",
    "مدونة التجارة": "15.95",
    "مدونة الشغل": "99.65",
}


def _get_law_abbreviation(name: str) -> str | None:
    """Try to resolve a full law name to its DB abbreviation."""
    for full_name, abbrev in LAW_ABBREVIATIONS.items():
        if full_name in name or name in full_name:
            return abbrev
    return None


# Arabic stop words — too common, match 70%+ of chunks, destroy query performance
ARABIC_STOP_WORDS = {
    "في", "من", "على", "إلى", "أن", "هو", "هي", "هذا", "هذه", "التي", "الذي",
    "ما", "لا", "أو", "و", "عن", "مع", "كان", "كل", "ذلك", "بين", "حتى",
    "ثم", "قد", "لم", "إذا", "بعد", "قبل", "غير", "عند", "له", "لها",
    "المغرب", "المغربي", "المغربية", "القانون", "القانونية", "القانوني",
}


async def search_document_chunks(search_query: str, limit: int = 5) -> list[dict]:
    """
    Full-text search on document_chunks using tsvector.
    Filters out Arabic stop words to keep the query selective.
    Uses AND matching for precision when multiple keywords remain,
    falls back to OR if AND returns nothing.
    """
    words = [w for w in search_query.strip().split() if w not in ARABIC_STOP_WORDS]

    if not words:
        # All words were stop words — use the two longest original words
        all_words = search_query.strip().split()
        words = sorted(all_words, key=len, reverse=True)[:2]

    # Take top 2 most specific words.
    keywords = sorted(words, key=len, reverse=True)[:2]

    sql = """
        SELECT
            source_table,
            source_id,
            chunk_text,
            chunk_index AS chunk_number,
            ts_rank(to_tsvector('simple', chunk_text), to_tsquery('simple', $1)) AS score
        FROM document_chunks
        WHERE to_tsvector('simple', chunk_text) @@ to_tsquery('simple', $1)
        ORDER BY score DESC, chunk_index ASC
        LIMIT $2
    """

    # Try AND (both words in same chunk)
    if len(keywords) >= 2:
        results = await query(sql, " & ".join(keywords), limit)
        if results:
            return results

    # AND returned 0 — search the single most specific keyword
    return await query(sql, keywords[0], limit)


async def search_lois(search_query: str, limit: int = 3) -> list[dict]:
    """
    Search laws by numero, titre, or resume.
    Port of rag-search.ts lines 81-99.
    Also tries resolved abbreviation if full name search fails.
    """
    sql = """
        SELECT id, source_table, source_id, numero, type, titre, resume,
               date_promulgation, date_publication, gazette_numero, gazette_page
        FROM lois
        WHERE numero ILIKE $1
           OR titre ILIKE $1
           OR resume ILIKE $1
        ORDER BY date_promulgation DESC NULLS LAST
        LIMIT $2
    """
    pattern = f"%{search_query}%"
    results = await query(sql, pattern, limit)

    # Try abbreviation if full name returned nothing
    if not results:
        abbrev = _get_law_abbreviation(search_query)
        if abbrev:
            results = await query(sql, f"%{abbrev}%", limit)

    return results


async def search_articles(
    search_query: str | None = None,
    loi_numero: str | None = None,
    article_numero: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """
    Search articles by content, law number, or article number.
    Port of rag-search.ts lines 104-121.
    """
    # Exact match if both loi_numero and article_numero provided
    if loi_numero and article_numero:
        # Try the original name first
        sql = """
            SELECT id, source_table, source_id, loi_id, loi_numero,
                   numero AS article_numero, contenu
            FROM articles
            WHERE loi_numero ILIKE $1
              AND numero ILIKE $2
            LIMIT $3
        """
        results = await query(sql, f"%{loi_numero}%", f"%{article_numero}%", limit)

        # Try with resolved abbreviation (e.g. "القانون الجنائي" → "ق.ج")
        if not results:
            abbrev = _get_law_abbreviation(loi_numero)
            if abbrev:
                results = await query(sql, f"%{abbrev}%", f"%{article_numero}%", limit)

        # Last fallback: search by article number only
        if not results:
            sql = """
                SELECT id, source_table, source_id, loi_id, loi_numero,
                       numero AS article_numero, contenu
                FROM articles
                WHERE numero = $1
                LIMIT $2
            """
            results = await query(sql, article_numero, limit)

        return results

    # Broad search
    term = search_query or loi_numero or article_numero or ""
    sql = """
        SELECT id, source_table, source_id, loi_id, loi_numero,
               numero AS article_numero, contenu
        FROM articles
        WHERE numero ILIKE $1
           OR contenu ILIKE $1
           OR loi_numero ILIKE $1
        LIMIT $2
    """
    pattern = f"%{term}%"
    return await query(sql, pattern, limit)


async def get_document_references(chunks: list[dict]) -> dict[str, dict]:
    """
    Resolve source_table + source_id from chunks to get PDF URLs and titles.
    Port of huquqai/lib/ai/rag-search.ts:211-288.
    Returns a dict keyed by "source_table:source_id" with pdf_url and title.
    """
    if not chunks:
        return {}

    # Group by source table
    by_table: dict[str, list[str]] = {}
    for chunk in chunks:
        table = chunk.get("source_table", "")
        sid = str(chunk.get("source_id", ""))
        if table and sid:
            by_table.setdefault(table, []).append(sid)

    refs: dict[str, dict] = {}

    for table, source_ids in by_table.items():
        unique_ids = list(set(source_ids))
        sql = f"""
            SELECT id, title, COALESCE(r2_pdf_url, pdf_url) AS pdf_url, url AS source_page_link
            FROM {table}
            WHERE id = ANY($1::int[])
        """
        try:
            rows = await query(sql, [int(sid) for sid in unique_ids])
            for r in rows:
                key = f"{table}:{r['id']}"
                refs[key] = {
                    "title": r.get("title", ""),
                    "pdf_url": r.get("pdf_url"),
                    "source_page_link": r.get("source_page_link"),
                }
        except Exception:
            continue

    return refs


async def search_all(search_query: str) -> dict:
    """
    Run all searches in parallel and return combined results.
    Mirrors huquqai/lib/ai/rag-search.ts:302-310 (Promise.all).
    Also resolves PDF URLs for chunks from source document tables.
    """
    chunks, lois, articles = await asyncio.gather(
        search_document_chunks(search_query),
        search_lois(search_query),
        search_articles(search_query=search_query),
    )

    # Resolve PDF URLs from source document tables
    refs = await get_document_references(chunks)
    for chunk in chunks:
        key = f"{chunk.get('source_table', '')}:{chunk.get('source_id', '')}"
        ref = refs.get(key, {})
        chunk["pdf_url"] = ref.get("pdf_url")
        chunk["doc_title"] = ref.get("title", "")

    return {
        "chunks": chunks,
        "lois": lois,
        "articles": articles,
        "total_results": len(chunks) + len(lois) + len(articles),
    }
