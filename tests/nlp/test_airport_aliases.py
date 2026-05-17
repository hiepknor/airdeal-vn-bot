from app.nlp.airport_aliases import find_airports, resolve_airport


def test_resolve_basic():
    assert resolve_airport("hà nội") == "HAN"
    assert resolve_airport("HN") == "HAN"
    assert resolve_airport("sài gòn") == "SGN"
    assert resolve_airport("tphcm") == "SGN"


def test_find_airports_two():
    matches = find_airports("hà nội đi sài gòn")
    codes = [m[2] for m in matches]
    assert codes == ["HAN", "SGN"]


def test_find_airports_longest_wins():
    matches = find_airports("ho chi minh đi đà nẵng")
    codes = [m[2] for m in matches]
    assert codes == ["SGN", "DAD"]


def test_find_airports_no_dau():
    matches = find_airports("ha noi di da nang")
    codes = [m[2] for m in matches]
    assert codes == ["HAN", "DAD"]
