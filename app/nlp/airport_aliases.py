from __future__ import annotations

import unicodedata

AIRPORT_ALIASES: dict[str, str] = {
    "hà nội": "HAN", "ha noi": "HAN", "hn": "HAN", "nội bài": "HAN", "noi bai": "HAN",
    "sài gòn": "SGN", "sai gon": "SGN", "saigon": "SGN", "sg": "SGN",
    "tphcm": "SGN", "tp hcm": "SGN", "hồ chí minh": "SGN", "ho chi minh": "SGN", "tsn": "SGN",
    "đà nẵng": "DAD", "da nang": "DAD", "danang": "DAD", "dn": "DAD", "đn": "DAD",
    "nha trang": "CXR", "cam ranh": "CXR",
    "phú quốc": "PQC", "phu quoc": "PQC", "pq": "PQC",
    "đà lạt": "DLI", "da lat": "DLI", "dalat": "DLI", "liên khương": "DLI", "lien khuong": "DLI",
    "huế": "HUI", "hue": "HUI", "phú bài": "HUI", "phu bai": "HUI",
    "vinh": "VII",
    "cần thơ": "VCA", "can tho": "VCA",
    "hải phòng": "HPH", "hai phong": "HPH", "cát bi": "HPH", "cat bi": "HPH",
    "quy nhơn": "UIH", "quy nhon": "UIH", "phù cát": "UIH", "phu cat": "UIH",
    "buôn ma thuột": "BMV", "buon ma thuot": "BMV", "ban mê": "BMV", "ban me": "BMV",
    "thanh hoá": "THD", "thanh hoa": "THD", "thọ xuân": "THD", "tho xuan": "THD",
    "đồng hới": "VDH", "dong hoi": "VDH", "quảng bình": "VDH", "quang binh": "VDH",
    "chu lai": "VCL", "tam kỳ": "VCL", "tam ky": "VCL",
    "tuy hoà": "TBB", "tuy hoa": "TBB", "phú yên": "TBB", "phu yen": "TBB",
    "pleiku": "PXU", "gia lai": "PXU",
    "côn đảo": "VCS", "con dao": "VCS", "côn sơn": "VCS", "con son": "VCS",
    "rạch giá": "VKG", "rach gia": "VKG",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.strip().lower())
    return " ".join(s.split())


_NORMALIZED = {_norm(k): v for k, v in AIRPORT_ALIASES.items()}
_SORTED_KEYS = sorted(_NORMALIZED.keys(), key=len, reverse=True)


def resolve_airport(text: str) -> str | None:
    return _NORMALIZED.get(_norm(text))


def find_airports(text: str) -> list[tuple[int, int, str]]:
    """Return [(start, end, IATA)] sorted by start, longest-match-first non-overlap."""
    n = _norm(text)
    matches: list[tuple[int, int, str]] = []
    taken = [False] * len(n)
    for key in _SORTED_KEYS:
        start = 0
        while True:
            idx = n.find(key, start)
            if idx == -1:
                break
            end = idx + len(key)
            if not any(taken[idx:end]):
                # word boundary check
                left_ok = idx == 0 or not n[idx - 1].isalnum()
                right_ok = end == len(n) or not n[end].isalnum()
                if left_ok and right_ok:
                    matches.append((idx, end, _NORMALIZED[key]))
                    for i in range(idx, end):
                        taken[i] = True
            start = idx + 1
    matches.sort(key=lambda m: m[0])
    return matches
