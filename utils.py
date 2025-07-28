def _get_title_artist(song: dict) -> tuple[str, str, str, str]:
    """노래 딕셔너리에서 제목과 아티스트를 추출합니다."""
    title_jp = song.get("title_jp", "")
    title_kr = song.get("title_kr") or song.get("title", "") or ""
    artist = song.get("artist", "")
    artist_kr = song.get("artist_kr", "")
    return title_jp.strip(), title_kr.strip(), artist.strip(), artist_kr.strip() 