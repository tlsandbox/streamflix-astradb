#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "tv_shows_300.json"
TARGET_SIZE = 300
TVMAZE_BASE_URL = "https://api.tvmaze.com"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"
REQUEST_TIMEOUT_SECONDS = 20
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
TMDB_BEARER_TOKEN = os.getenv("TMDB_BEARER_TOKEN", "").strip()
TMDB_ENABLED = bool(TMDB_API_KEY or TMDB_BEARER_TOKEN)


def fetch_json(
    url: str,
    *,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    retries: int = 4,
    allow_404: bool = False,
    headers: dict[str, str] | None = None,
) -> dict | list[dict] | None:
    request_headers = {"User-Agent": "streamflix-workshop/1.0"}
    if headers:
        request_headers.update(headers)

    for attempt in range(retries + 1):
        request = Request(url, headers=request_headers)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            if exc.code not in RETRYABLE_STATUS_CODES or attempt == retries:
                raise
        except (TimeoutError, URLError, ConnectionResetError):
            if attempt == retries:
                raise
        sleep_seconds = 0.4 * (2**attempt) + random.uniform(0.0, 0.2)
        time.sleep(sleep_seconds)
    return None


TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    clean = TAG_RE.sub("", text)
    return " ".join(clean.split())


def unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = value.strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
    return output


def first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            clean = value.strip()
            if clean:
                return clean
            continue
        if isinstance(value, (list, tuple, dict, set)):
            if value:
                return value
            continue
        if isinstance(value, (int, float)):
            if value > 0:
                return value
            continue
        return value
    return None


def parse_year(value: str | None) -> int | None:
    if not value:
        return None
    value = str(value)
    if len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def network_name(show: dict) -> str | None:
    network = show.get("network") or {}
    web_channel = show.get("webChannel") or {}
    return network.get("name") or web_channel.get("name")


def metadata_tags(show: dict, row_tags: list[str]) -> list[str]:
    tags = list(row_tags)
    show_type = show.get("type")
    language = show.get("language")
    status = show.get("status")
    genres = show.get("genres") or []
    if isinstance(show_type, str) and show_type:
        tags.append(show_type.lower())
    if isinstance(language, str) and language:
        tags.append(language.lower())
    if isinstance(status, str) and status:
        tags.append(status.lower())
    for genre in genres:
        if isinstance(genre, str) and genre:
            tags.append(genre.lower())
    return unique_non_empty(tags)


def extract_tvmaze_credits(show_detail: dict) -> tuple[list[str], list[str], list[str]]:
    embedded = show_detail.get("_embedded") or {}
    crew = embedded.get("crew") or []
    cast = embedded.get("cast") or []

    creators = []
    directors = []
    cast_names = []

    for crew_item in crew:
        person = crew_item.get("person") or {}
        name = str(person.get("name") or "").strip()
        role_type = str(crew_item.get("type") or "").lower()
        if not name:
            continue
        if any(keyword in role_type for keyword in ("creator", "created", "showrunner", "developer", "writer")):
            creators.append(name)
        if "director" in role_type:
            directors.append(name)

    for cast_item in cast:
        person = cast_item.get("person") or {}
        name = str(person.get("name") or "").strip()
        if name:
            cast_names.append(name)
        if len(cast_names) >= 8:
            break

    return unique_non_empty(creators), unique_non_empty(directors), unique_non_empty(cast_names)


def tmdb_request(path: str, *, params: dict | None = None, allow_404: bool = False) -> dict | None:
    if not TMDB_ENABLED:
        return None

    query_params = dict(params or {})
    if TMDB_API_KEY:
        query_params["api_key"] = TMDB_API_KEY
    query_params.setdefault("language", "en-US")
    query_string = urlencode(query_params, doseq=True)
    url = f"{TMDB_BASE_URL}/{path.lstrip('/')}"
    if query_string:
        url = f"{url}?{query_string}"

    headers: dict[str, str] = {}
    if TMDB_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {TMDB_BEARER_TOKEN}"

    payload = fetch_json(url, headers=headers, allow_404=allow_404)
    if isinstance(payload, dict):
        return payload
    return None


def choose_tmdb_match(results: list[dict], *, title: str, year: int | None) -> dict | None:
    if not results:
        return None

    normalized_title = normalize_text(title)
    best_result: dict | None = None
    best_score = float("-inf")

    for result in results:
        candidate_title = str(result.get("name") or result.get("original_name") or "").strip()
        if not candidate_title:
            continue
        candidate_year = parse_year(result.get("first_air_date"))
        score = 0.0
        normalized_candidate = normalize_text(candidate_title)

        if normalized_candidate == normalized_title:
            score += 4.0
        elif normalized_candidate in normalized_title or normalized_title in normalized_candidate:
            score += 2.0

        if year and candidate_year:
            if candidate_year == year:
                score += 2.0
            elif abs(candidate_year - year) <= 1:
                score += 1.0

        popularity = float(result.get("popularity") or 0.0)
        score += min(popularity / 100.0, 1.0)

        if score > best_score:
            best_score = score
            best_result = result

    return best_result


def tmdb_show_metadata(title: str, year: int | None) -> dict:
    if not TMDB_ENABLED:
        return {}

    search_params = {"query": title, "include_adult": "false"}
    if year:
        search_params["first_air_date_year"] = year

    search_payload = tmdb_request("/search/tv", params=search_params)
    if not search_payload:
        return {}

    results = search_payload.get("results") or []
    match = choose_tmdb_match(results, title=title, year=year)
    if not match or not match.get("id"):
        return {}

    detail_payload = tmdb_request(
        f"/tv/{match['id']}",
        params={"append_to_response": "credits,keywords"},
        allow_404=True,
    ) or {}

    credits = detail_payload.get("credits") or {}
    crew = credits.get("crew") or []
    cast = credits.get("cast") or []

    creators = [str(item.get("name") or "").strip() for item in detail_payload.get("created_by") or []]
    directors: list[str] = []
    for member in crew:
        name = str(member.get("name") or "").strip()
        if not name:
            continue
        job = str(member.get("job") or "").lower()
        department = str(member.get("department") or "").lower()
        if "director" in job or department == "directing":
            directors.append(name)

    tmdb_cast = [str(member.get("name") or "").strip() for member in cast]
    runtime_values: list[int] = []
    for raw_runtime in detail_payload.get("episode_run_time") or []:
        try:
            parsed_runtime = int(raw_runtime)
        except (TypeError, ValueError):
            continue
        if parsed_runtime > 0:
            runtime_values.append(parsed_runtime)
    keywords = detail_payload.get("keywords") or {}
    keyword_items = keywords.get("results") or keywords.get("keywords") or []
    keyword_names = [str(item.get("name") or "").strip() for item in keyword_items if item.get("name")]
    genres = [str(item.get("name") or "").strip() for item in detail_payload.get("genres") or []]
    networks = detail_payload.get("networks") or []

    poster_path = str(detail_payload.get("poster_path") or "").strip()
    poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None

    return {
        "tmdb_id": match["id"],
        "synopsis": str(detail_payload.get("overview") or "").strip(),
        "poster_url": poster_url,
        "status": str(detail_payload.get("status") or "").strip() or None,
        "premiered_date": str(detail_payload.get("first_air_date") or "").strip() or None,
        "network": str((networks[0] or {}).get("name") or "").strip() if networks else None,
        "runtime": runtime_values[0] if runtime_values else None,
        "language": (
            str((detail_payload.get("spoken_languages") or [{}])[0].get("english_name") or "").strip()
            or str(detail_payload.get("original_language") or "").strip()
            or None
        ),
        "rating": float(detail_payload.get("vote_average")) if detail_payload.get("vote_average") is not None else None,
        "genres": unique_non_empty(genres),
        "tags": unique_non_empty(keyword_names),
        "creator_names": unique_non_empty(creators),
        "director_names": unique_non_empty(directors),
        "cast_names": unique_non_empty(tmdb_cast)[:8],
    }



def build_row_tags(show: dict) -> list[str]:
    tags: list[str] = []
    genres = set(show.get("genres") or [])
    rating = show.get("rating") or 0
    year = show.get("year") or 0

    if rating >= 8.0:
        tags.append("trending")
    if year >= 2020:
        tags.append("new_release")
    if {"Science-Fiction", "Fantasy", "Sci-Fi"} & genres:
        tags.append("sci_fi")
    if "Drama" in genres:
        tags.append("drama")
    if show.get("runtime", 0) >= 45:
        tags.append("binge")

    if not tags:
        tags.append("trending")
    return sorted(set(tags))


def enrich_show(show_raw: dict) -> dict | None:
    detail_url = f"{TVMAZE_BASE_URL}/shows/{show_raw['id']}?embed[]=cast&embed[]=crew"
    try:
        detail = fetch_json(detail_url, timeout=REQUEST_TIMEOUT_SECONDS)
        if not isinstance(detail, dict):
            detail = show_raw
    except Exception:  # noqa: BLE001
        # Fallback to base payload when enrichment endpoint is unavailable.
        detail = show_raw

    title = str(detail.get("name") or show_raw.get("name") or "Untitled Show")
    tvmaze_premiered = str(detail.get("premiered") or show_raw.get("premiered") or "")
    tvmaze_year = parse_year(tvmaze_premiered)
    tmdb = tmdb_show_metadata(title, tvmaze_year)

    image = (detail.get("image") or show_raw.get("image") or {})
    poster_url = first_non_empty(image.get("original"), image.get("medium"), tmdb.get("poster_url"))
    summary = first_non_empty(
        strip_html(detail.get("summary") or show_raw.get("summary")),
        strip_html(tmdb.get("synopsis")),
    )
    if not poster_url or not summary:
        return None

    premiered = first_non_empty(detail.get("premiered"), show_raw.get("premiered"), tmdb.get("premiered_date"))
    year = parse_year(premiered)
    rating = first_non_empty(
        ((detail.get("rating") or show_raw.get("rating") or {}).get("average")),
        tmdb.get("rating"),
    )
    genres = unique_non_empty(
        [str(item) for item in (detail.get("genres") or [])]
        + [str(item) for item in (show_raw.get("genres") or [])]
        + [str(item) for item in (tmdb.get("genres") or [])]
    )
    network = first_non_empty(network_name(detail), network_name(show_raw), tmdb.get("network"))
    language = first_non_empty(detail.get("language"), show_raw.get("language"), tmdb.get("language"), "English")
    runtime = first_non_empty(detail.get("runtime"), show_raw.get("runtime"), tmdb.get("runtime")) or 0
    status = first_non_empty(detail.get("status"), show_raw.get("status"), tmdb.get("status"))
    tvmaze_creators, tvmaze_directors, tvmaze_cast = extract_tvmaze_credits(detail)
    creators = unique_non_empty(tvmaze_creators + list(tmdb.get("creator_names") or []))
    directors = unique_non_empty(list(tmdb.get("director_names") or []) + tvmaze_directors)
    cast_names = unique_non_empty(tvmaze_cast + list(tmdb.get("cast_names") or []))[:8]

    show = {
        "_id": f"show_{show_raw['id']}",
        "tvmaze_id": show_raw["id"],
        "title": title,
        "genres": genres,
        "year": year,
        "premiered_date": premiered or None,
        "status": status,
        "synopsis": summary,
        "poster_url": str(poster_url),
        "rating": float(rating) if rating is not None else None,
        "network": network,
        "language": str(language),
        "runtime": int(runtime) if runtime else 0,
        "row_tags": [],
        "tags": [],
        "creator_names": creators,
        "director_names": directors,
        "cast_names": cast_names,
        "_tmdb_match": bool(tmdb),
    }

    show["row_tags"] = build_row_tags(show)
    show["tags"] = unique_non_empty(metadata_tags(detail, show["row_tags"]) + list(tmdb.get("tags") or []))

    cast_preview = ", ".join(show["cast_names"][:4]) if show["cast_names"] else "unknown cast"
    creator_preview = ", ".join(show["creator_names"][:3]) if show["creator_names"] else "unknown creator"
    show["vectorize_text"] = " ".join(
        [
            show["title"],
            " ".join(show["genres"]),
            show["synopsis"],
            f"network {show['network'] or 'unknown'}",
            f"status {show['status'] or 'unknown'}",
            f"creators {creator_preview}",
            f"cast {cast_preview}",
            f"tags {' '.join(show['tags'])}",
        ]
    )
    return show


def print_fill_rate_report(rows: list[dict]) -> None:
    if not rows:
        return

    def present(value) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return bool(value)
        if isinstance(value, (int, float)):
            return value > 0
        return True

    total = len(rows)
    fields = [
        "network",
        "runtime",
        "language",
        "status",
        "premiered_date",
        "creator_names",
        "director_names",
        "cast_names",
    ]
    print("\nMetadata fill-rate report:")
    for field in fields:
        filled = sum(1 for row in rows if present(row.get(field)))
        percent = (filled / total) * 100
        print(f"  {field:16} {filled:3d}/{total} ({percent:5.1f}%)")


def main() -> None:
    random.seed(42)
    if TMDB_ENABLED:
        print("TMDB enrichment enabled (using TMDB_API_KEY or TMDB_BEARER_TOKEN).")
    else:
        print("TMDB enrichment disabled. Set TMDB_API_KEY (or TMDB_BEARER_TOKEN) for richer metadata coverage.")

    collected: list[dict] = []
    page = 0

    while len(collected) < TARGET_SIZE and page < 20:
        payload = fetch_json(f"{TVMAZE_BASE_URL}/shows?page={page}", timeout=REQUEST_TIMEOUT_SECONDS)
        if not isinstance(payload, list):
            raise SystemExit(f"Unexpected TVMaze response type on page {page}")
        for raw in payload:
            image = raw.get("image") or {}
            poster_url = image.get("original") or image.get("medium")
            summary = strip_html(raw.get("summary"))
            if not poster_url or not summary:
                continue
            collected.append(raw)
            if len(collected) >= TARGET_SIZE:
                break
        page += 1

    if len(collected) < TARGET_SIZE:
        raise SystemExit(f"Only collected {len(collected)} shows; expected {TARGET_SIZE}.")

    random.shuffle(collected)
    selected_raw = sorted(collected[:TARGET_SIZE], key=lambda item: int(item["id"]))

    selected: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(enrich_show, raw_show): raw_show["id"] for raw_show in selected_raw}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            enriched = future.result()
            if enriched:
                selected.append(enriched)
            if completed % 25 == 0:
                print(f"Enriched {completed}/{len(selected_raw)} shows")

    selected.sort(key=lambda item: item["_id"])
    if len(selected) < TARGET_SIZE:
        raise SystemExit(f"Only enriched {len(selected)} shows; expected {TARGET_SIZE}.")

    tmdb_matches = sum(1 for item in selected if item.get("_tmdb_match"))
    for item in selected:
        item.pop("_tmdb_match", None)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(f"TMDB matched shows: {tmdb_matches}/{len(selected)}")
    print_fill_rate_report(selected)
    print(f"Wrote {OUT_PATH} with {len(selected)} shows")


if __name__ == "__main__":
    main()
