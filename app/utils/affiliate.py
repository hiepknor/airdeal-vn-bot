from __future__ import annotations

from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

_REF_PARAMS: dict[str, str] = {
    "traveloka": "aff_ref",
    "trip": "Allianceid",
    "atadi": "ref",
    "abay": "utm_source",
}


def inject_affiliate(url: str | None, provider: str, affiliate_id: str | None) -> str | None:
    if not url or not affiliate_id:
        return url
    param = _REF_PARAMS.get(provider, "ref")
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs[param] = [affiliate_id]
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    return urlunparse(parsed._replace(query=new_query))
