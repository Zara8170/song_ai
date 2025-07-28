# 기존 tools.py는 이제 다른 모듈들의 함수를 re-export하는 역할만 합니다.
# 하위 호환성을 위해 기존 import 구조를 유지합니다.

from database_service import (
    get_candidate_songs,
    get_favorite_songs_info,
    get_all_active_users_with_favorites
)

from recommendation_service import recommend_songs

from ai_service import (
    _analyze_user_preference,
    _ai_recommend_songs,
    _make_tagline
)

from utils import _get_title_artist

# 기존 코드와의 호환성을 위해 모든 함수를 여기서 사용할 수 있도록 export
__all__ = [
    'get_candidate_songs',
    'get_favorite_songs_info', 
    'get_all_active_users_with_favorites',
    'recommend_songs',
    '_analyze_user_preference',
    '_ai_recommend_songs',
    '_make_tagline',
    '_get_title_artist'
]
