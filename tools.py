
# tools.py

def recommend_from_favorites():
    """
    사용자의 즐겨찾기 목록을 기반으로 노래를 추천합니다.
    (기존 로직)
    """
    print("즐겨찾기 기반 추천 로직 실행")
    # 여기에 기존의 즐겨찾기 추천 코드를 넣으세요.
    return ["즐겨찾기 노래 1", "즐겨찾기 노래 2"]

def recommend_by_artist(artist_name: str):
    """
    특정 아티스트의 노래를 추천합니다.
    (신규 로직)
    """
    print(f"아티스트 '{artist_name}' 기반 추천 로직 실행")
    # 실제로는 여기서 외부 API를 호출하거나 DB를 조회해야 합니다.
    # 예시로 하드코딩된 데이터를 반환합니다.
    if artist_name == "요네즈 켄시":
        return ["Lemon", "KICK BACK", "orion"]
    elif artist_name == "아이유":
        return ["라일락", "밤편지", "Celebrity"]
    else:
        return [f"{artist_name}의 노래를 찾을 수 없습니다."]
