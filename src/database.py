import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "nexusai_history.db"


def _safe_json_loads(data: str) -> List[dict]:
    if not data:
        return []
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON from database: {e}")
        return []


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            answer TEXT,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_research(query: str, answer: str, sources: List[dict]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    sources_json = json.dumps(sources)
    cursor.execute(
        "INSERT INTO research_history (query, answer, sources) VALUES (?, ?, ?)",
        (query, answer, sources_json),
    )
    conn.commit()
    research_id = cursor.lastrowid
    conn.close()
    return research_id


def get_all_research(limit: int = 50) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, query, answer, sources, created_at FROM research_history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "query": row[1],
                "answer": row[2],
                "sources": _safe_json_loads(row[3]),
                "created_at": row[4],
            }
        )
    return results


def get_research_by_id(research_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, query, answer, sources, created_at FROM research_history WHERE id = ?",
        (research_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "query": row[1],
            "answer": row[2],
            "sources": _safe_json_loads(row[3]),
            "created_at": row[4],
        }
    return None


def delete_research(research_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM research_history WHERE id = ?", (research_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def search_history(search_term: str, limit: int = 20) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, query, answer, sources, created_at FROM research_history WHERE query LIKE ? ORDER BY created_at DESC LIMIT ?",
        (f"%{search_term}%", limit),
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "query": row[1],
                "answer": row[2],
                "sources": _safe_json_loads(row[3]),
                "created_at": row[4],
            }
        )
    return results

init_db()
