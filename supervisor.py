
import re

def route_request(user_query: str):
    artist_pattern = r"(.+?)\s+노래\s+추천"
    
    match = re.search(artist_pattern, user_query)
    
    if match:
        artist_name = match.group(1).strip()
        return "recommend_by_artist", {"artist": artist_name}
    
    elif "노래 추천" in user_query:
        return "recommend_from_favorites", {}
        
    else:
        return "unknown", {}
