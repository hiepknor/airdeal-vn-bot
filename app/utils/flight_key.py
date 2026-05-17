from hashlib import sha1


def make_flight_key(
    airline: str,
    flight_number: str | None,
    departure_date: str,
    depart_time: str | None,
) -> str:
    parts = [
        airline.strip().upper(),
        (flight_number or "").strip().upper().replace(" ", ""),
        departure_date,
        (depart_time or "").strip(),
    ]
    return sha1("|".join(parts).encode("utf-8"), usedforsecurity=False).hexdigest()
