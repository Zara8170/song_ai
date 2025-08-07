import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """DB 연결을 생성하고 반환합니다."""
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_NAME"),
        charset="utf8"
    )

def get_candidate_songs(favorite_song_ids: list[int], limit: int = 100) -> list[dict]:
    """
    추천을 위한 후보 노래들을 가져옵니다.
    사용자의 선호 노래를 기반으로 유사한 노래들과 랜덤 노래들을 조합합니다.
    """
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    try:
        if favorite_song_ids:
            fav_ids_str = ",".join(map(str, favorite_song_ids))
            
            cur.execute(f"SELECT * FROM song WHERE song_id IN ({fav_ids_str})")
            fav_info = cur.fetchall()

            genres = [s['genre'] for s in fav_info if s.get('genre')]
            artists = [s['artist_kr'] for s in fav_info if s.get('artist_kr')]
            
            similar_songs = []
            if genres or artists:
                genre_list = "','".join(set(genres)) if genres else ""
                artist_list = "','".join(set(artists)) if artists else ""
                genre_clause = f"genre IN ('{genre_list}')" if genres else "1=0"
                artist_clause = f"artist_kr IN ('{artist_list}')" if artists else "1=0"
                
                sql = (f"SELECT * FROM song WHERE ({genre_clause} OR {artist_clause}) "
                       f"AND song_id NOT IN ({fav_ids_str}) ORDER BY RAND() LIMIT {limit//2}")
                cur.execute(sql)
                similar_songs = cur.fetchall()
                
                # 취향 기반 노래에 표시 추가
                for song in similar_songs:
                    song['recommendation_type'] = 'preference'
                    # 추가로 매칭된 기준도 표시
                    song['matched_criteria'] = []
                    if song.get('genre') and song['genre'] in genres:
                        song['matched_criteria'].append('genre')
                    if song.get('artist_kr') and song['artist_kr'] in artists:
                        song['matched_criteria'].append('artist')
            
            remaining_limit = limit - len(similar_songs)
            if remaining_limit > 0:
                sql = (f"SELECT * FROM song WHERE song_id NOT IN ({fav_ids_str}) "
                       f"ORDER BY RAND() LIMIT {remaining_limit}")
                cur.execute(sql)
                random_songs = cur.fetchall()
                
                # 랜덤 노래에 표시 추가
                for song in random_songs:
                    song['recommendation_type'] = 'random'
                    song['matched_criteria'] = []
                    
                similar_songs.extend(random_songs)
            
            candidates = similar_songs
        else:
            cur.execute(f"SELECT * FROM song ORDER BY RAND() LIMIT {limit}")
            candidates = cur.fetchall()
            # 선호도가 없는 경우 모두 랜덤으로 표시
            for song in candidates:
                song['recommendation_type'] = 'random'
                song['matched_criteria'] = []

        return candidates
    finally:
        cur.close()
        conn.close()

def get_favorite_songs_info(favorite_song_ids: list[int]) -> list[dict]:
    """사용자가 좋아하는 노래들의 상세 정보를 가져옵니다."""
    if not favorite_song_ids:
        return []
        
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    try:
        fav_ids_str = ",".join(map(str, favorite_song_ids))
        cur.execute(f"SELECT * FROM song WHERE song_id IN ({fav_ids_str})")
        favorites = cur.fetchall()
        return favorites
    finally:
        cur.close()
        conn.close()

def get_all_active_users_with_favorites() -> dict[str, list[int]]:
    """
    DB에서 USER 역할을 가진 모든 활성 사용자와 그들의 좋아하는 노래 ID를 가져옵니다.
    Returns: {member_id: [favorite_song_ids]}
    """
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # USER 역할을 가진 사용자들 조회
        user_query = """
        SELECT DISTINCT m.member_id 
        FROM member m 
        JOIN member_role_list mrl ON m.member_id = mrl.id 
        WHERE mrl.role = 'USER'
        """
        cur.execute(user_query)
        users = cur.fetchall()
        
        user_favorites = {}
        
        for user in users:
            member_id = str(user['member_id'])
            
            # 각 사용자의 좋아하는 노래 조회
            favorites_query = """
            SELECT sl.song_id 
            FROM song_like sl 
            WHERE sl.member_id = %s
            """
            cur.execute(favorites_query, (user['member_id'],))
            favorite_songs = cur.fetchall()
            
            # song_id 리스트로 변환
            favorite_song_ids = [song['song_id'] for song in favorite_songs]
            user_favorites[member_id] = favorite_song_ids
        
        return user_favorites
        
    except Exception as e:
        print(f"DB에서 사용자 정보 가져오기 실패: {e}")
        return {}
    finally:
        cur.close()
        conn.close() 