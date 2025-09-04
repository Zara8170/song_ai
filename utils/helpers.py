def _get_title_artist(song: dict) -> tuple[str, str, str, str, str, str]:
    """노래 딕셔너리에서 제목과 아티스트를 추출합니다."""
    title_jp = song.get("title_jp") or ""
    title_kr = song.get("title_kr") or song.get("title") or ""
    title_en = song.get("title_en") or ""
    title_yomi = song.get("title_yomi") or ""
    artist = song.get("artist") or ""
    artist_kr = song.get("artist_kr") or ""
    return title_jp.strip(), title_kr.strip(), title_en.strip(), title_yomi.strip(), artist.strip(), artist_kr.strip()
