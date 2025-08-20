import os
import pymysql
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()

def get_db_connection():
    """DB 연결을 생성하고 반환합니다."""
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_NAME"),
        charset="utf8",
        cursorclass=pymysql.cursors.DictCursor,
    )

# --- 컬럼 존재 체크 → is_active 옵션 처리 ---
def _has_column(cur, table: str, column: str) -> bool:
    cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE %s", (column,))
    return cur.fetchone() is not None

def _active_clause(cur, table: str = "song") -> str:
    return " AND is_active = TRUE" if _has_column(cur, table, "is_active") else ""

# --- 스코어 계산 ---
def _score_candidate(song: dict,
                     preferred_genres: Optional[list[str]],
                     preferred_moods: Optional[list[str]],
                     like_genres: list[str],
                     like_artists: list[str]) -> int:
    score = 0
    g = (song.get("genre") or "").strip()
    m = (song.get("mood") or "").strip()
    a = (song.get("artist_kr") or "").strip()
    if preferred_genres and g in preferred_genres:
        score += 2
    if like_genres and g in like_genres:
        score += 2
    if preferred_moods and m in preferred_moods:
        score += 1
    if like_artists and a in like_artists:
        score += 2
    return score

def get_candidate_songs(
    favorite_song_ids: list[int],
    limit: int = 100,
    preferred_genres: Optional[list[str]] = None,
    preferred_moods: Optional[list[str]] = None
) -> list[dict]:
    """
    추천 후보 노래:
    - 좋아요 기반 장르/아티스트 & LLM의 preferred_genres/moods를 반영
    - 전체 풀에서 가중치(match_score) 계산 후 상위 정렬 + 부족분 랜덤 보충
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        like_genres, like_artists = [], []

        # 좋아요 곡 정보
        if favorite_song_ids:
            placeholders = ",".join(["%s"] * len(favorite_song_ids))
            cur.execute(
                f"SELECT * FROM song WHERE song_id IN ({placeholders}){_active_clause(cur)}",
                tuple(favorite_song_ids),
            )
            fav_info = cur.fetchall()
            like_genres = [s["genre"] for s in fav_info if s.get("genre")]
            like_artists = [s["artist_kr"] for s in fav_info if s.get("artist_kr")]

        # 전체 풀 조회
        if favorite_song_ids:
            placeholders = ",".join(["%s"] * len(favorite_song_ids))
            cur.execute(
                f"SELECT * FROM song WHERE 1=1{_active_clause(cur)} AND song_id NOT IN ({placeholders})",
                tuple(favorite_song_ids),
            )
        else:
            cur.execute(f"SELECT * FROM song WHERE 1=1{_active_clause(cur)}")
        pool = cur.fetchall()

        # 스코어 및 근거 기록
        from random import shuffle
        shuffle(pool)
        for s in pool:
            s["recommendation_type"] = "pool"
            s["matched_criteria"] = []
            s["match_score"] = _score_candidate(s, preferred_genres, preferred_moods, like_genres, like_artists)
            if preferred_genres and s.get("genre") in preferred_genres:
                s["matched_criteria"].append("preferred_genre")
            if preferred_moods and s.get("mood") in preferred_moods:
                s["matched_criteria"].append("preferred_mood")
            if like_genres and s.get("genre") in like_genres:
                s["matched_criteria"].append("like_genre")
            if like_artists and s.get("artist_kr") in like_artists:
                s["matched_criteria"].append("like_artist")

        pool.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        # 상위 limit + 부족분 보충
        top = pool[:limit]
        if len(top) < limit:
            remain = [s for s in pool if s not in top]
            shuffle(remain)
            top.extend(remain[: max(0, limit - len(top))])

        for s in top:
            if s.get("recommendation_type") == "pool":
                s["recommendation_type"] = "scored" if s.get("match_score", 0) > 0 else "random"

        return top[:limit]

    finally:
        cur.close()
        conn.close()

def get_favorite_songs_info(favorite_song_ids: list[int]) -> list[dict]:
    """사용자가 좋아하는 노래들의 상세 정보."""
    if not favorite_song_ids:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(favorite_song_ids))
        cur.execute(
            f"SELECT * FROM song WHERE song_id IN ({placeholders}){_active_clause(cur)}",
            tuple(favorite_song_ids),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_all_active_users_with_favorites() -> dict[str, list[int]]:
    """
    USER 역할의 모든 활성 사용자와 좋아요 곡 IDs 반환: {member_id: [song_id, ...]}
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT m.member_id
            FROM member m
            JOIN member_role_list mrl ON m.member_id = mrl.id
            WHERE mrl.role = 'USER'
        """)
        users = cur.fetchall()

        user_favs: dict[str, list[int]] = {}
        for u in users:
            mid = str(u["member_id"])
            cur.execute("SELECT sl.song_id FROM song_like sl WHERE sl.member_id = %s", (u["member_id"],))
            favs = cur.fetchall()
            user_favs[mid] = [r["song_id"] for r in favs]
        return user_favs
    except Exception as e:
        print(f"[DB] 사용자 조회 실패: {e}")
        return {}
    finally:
        cur.close()
        conn.close()

def get_songs_by_artists(artists: List[str], limit_per_artist: int = 5, exclude_song_ids: Optional[List[int]] = None) -> Dict[str, List[dict]]:
    """
    artists에 들어있는 가수명(한글/원문)을 기준으로 각 가수별로 곡을 최대 limit_per_artist개씩 반환.
    - artist_kr, artist 둘 다 매칭 시도 (OR)
    - exclude_song_ids에 있는 곡은 제외
    반환: { "아티스트명": [ {song row dict...}, ... ] }
    """
    if not artists:
        return {}

    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    try:
        results: Dict[str, List[dict]] = {}
        exclude_song_ids = exclude_song_ids or []

        for name in artists:
            rows: List[dict] = []

            cur.execute(
                """
                SELECT s.song_id, s.title_kr, s.title_en, s.title_jp, s.title_yomi,
                       s.artist_kr, s.artist, s.genre, s.mood,
                       s.tj_number, s.ky_number
                FROM song s
                WHERE (s.artist_kr = %s OR s.artist = %s)
                {ex}
                ORDER BY s.popularity DESC, s.song_id DESC
                LIMIT %s
                """.format(
                    ex="AND s.song_id NOT IN ({})".format(
                        ",".join(["%s"] * len(exclude_song_ids))
                    ) if exclude_song_ids else ""
                ),
                tuple(([name, name] + exclude_song_ids + [limit_per_artist]) if exclude_song_ids else (name, name, limit_per_artist)),
            )
            rows = cur.fetchall()

            if len(rows) < limit_per_artist:
                remain = limit_per_artist - len(rows)
                like_pat = f"%{name}%"
                cur.execute(
                    """
                    SELECT s.song_id, s.title_kr, s.title_en, s.title_jp, s.title_yomi,
                           s.artist_kr, s.artist, s.genre, s.mood,
                           s.tj_number, s.ky_number
                    FROM song s
                    WHERE (s.artist_kr LIKE %s OR s.artist LIKE %s)
                    {ex}
                    ORDER BY s.popularity DESC, s.song_id DESC
                    LIMIT %s
                    """.format(
                        ex="AND s.song_id NOT IN ({})".format(
                            ",".join(["%s"] * len(exclude_song_ids))
                        ) if exclude_song_ids else ""
                    ),
                    tuple(([like_pat, like_pat] + exclude_song_ids + [remain]) if exclude_song_ids else (like_pat, like_pat, remain)),
                )
                like_rows = cur.fetchall()

                seen = {r["song_id"] for r in rows}
                for r in like_rows:
                    if r["song_id"] not in seen:
                        rows.append(r)
                        seen.add(r["song_id"])

            results[name] = rows
        return results
    except Exception as e:
        print(f"[DB] get_songs_by_artists error: {e}")
        return {}
    finally:
        cur.close()
        conn.close()