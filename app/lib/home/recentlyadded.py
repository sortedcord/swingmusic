import os

from flask import g
from app.models.track import Track
from app.store.tracks import TrackStore
from app.store.albums import AlbumStore
from app.store.artists import ArtistStore

from app.serializers.track import serialize_track
from app.serializers.album import album_serializer
from app.serializers.artist import serialize_for_card

from itertools import groupby

from app.utils.dates import timestamp_from_days_ago, timestamp_to_time_passed

older_albums = set()
older_artists = set()


def calc_based_on_percent(items: list[str], total: int):
    """
    Checks if items is more than 85% of total items. Returns a boolean and the most common item.
    """
    most_common = max(items, key=items.count)
    most_common_count = items.count(most_common)

    return most_common_count / total >= 0.7, most_common, most_common_count


def check_is_album_folder(tracks: list[Track]):
    albumhashes = [t.albumhash for t in tracks]
    return calc_based_on_percent(albumhashes, len(tracks))


def check_is_artist_folder(tracks: list[Track]):
    # INFO: flatten artist hashes using "-" as a separator
    artisthashes = "-".join(t.artist_hashes for t in tracks).split("-")
    return calc_based_on_percent(artisthashes, len(tracks))


def check_is_track_folder(tracks: list[Track]):
    # INFO: is more of a playlist
    if len(tracks) >= 3:
        return False

    return [create_track(t) for t in tracks]


def check_is_new_artist(artisthash: str, timestamp: int):
    """
    Checks if an artist already exists in the library.
    """
    tracks = filter(
        lambda t: t.last_mod < timestamp and artisthash in t.artist_hashes,
        TrackStore.tracks,
    )

    return next(tracks, None) is None


def check_is_new_album(albumhash: str, timestamp: int):
    """
    Checks if an album already exists in the library.
    """
    tracks = filter(
        lambda t: t.last_mod < timestamp and t.albumhash == albumhash, TrackStore.tracks
    )

    return next(tracks, None) is None


def create_track(t: Track):
    """
    Creates a recently added track entry.
    """
    track = serialize_track(t, to_remove={"created_date"})
    track["help_text"] = "NEW TRACK"

    return {
        "type": "track",
        "item": track,
    }


# INFO: Keys: folder, tracks, time (timestamp)
group_type = dict[str, list[Track], float]


def check_folder_type(group_: group_type) -> str:
    # check if all tracks in group have the same albumhash
    # if so, return "album"
    key = group_["folder"]
    tracks = group_["tracks"]
    time = group_["time"]

    if len(tracks) == 1:
        entry = create_track(tracks[0])
        entry["item"]["time"] = timestamp_to_time_passed(time)
        return entry

    is_album, albumhash, _ = check_is_album_folder(tracks)
    if is_album:
        album = AlbumStore.get_album_by_hash(albumhash)

        if album is None:
            return None

        album = album_serializer(
            album,
            to_remove={
                "genres",
                "og_title",
                "date",
                "duration",
                "count",
                "albumartists_hashes",
                "base_title",
            },
        )
        album["help_text"] = (
            "NEW ALBUM" if check_is_new_album(albumhash, time) else "NEW TRACKS"
        )
        album["time"] = timestamp_to_time_passed(time)

        return {
            "type": "album",
            "item": album,
        }

    is_artist, artisthash, trackcount = check_is_artist_folder(tracks)
    if is_artist:
        artist = ArtistStore.get_artist_by_hash(artisthash)

        if artist is None:
            return None

        artist = serialize_for_card(artist)
        artist["trackcount"] = trackcount
        artist["help_text"] = (
            "NEW ARTIST" if check_is_new_artist(artisthash, time) else "NEW MUSIC"
        )
        artist["time"] = timestamp_to_time_passed(time)

        return {
            "type": "artist",
            "item": artist,
        }

    is_track_folder = check_is_track_folder(tracks)

    return (
        is_track_folder
        if is_track_folder
        else {
            "type": "folder",
            "item": {
                "path": key,
                "count": len(tracks),
                "help_text": "NEW MUSIC",
                "time": timestamp_to_time_passed(time),
            },
        }
    )


def group_track_by_folders(tracks: Track):
    """
    Groups tracks by folder and returns a list of groups sorted by last modified date.

    Uses generator expressions to avoid creating intermediate lists.
    """

    # INFO: sort tracks by folder name, then group by folder name
    tracks = sorted(tracks, key=lambda t: t.folder)
    groups = groupby(tracks, lambda t: t.folder)

    # INFO: sort tracks by last modified date in descending order to get the most recent last modified date
    groups = (
        (folder, sorted(tracks, key=lambda t: t.last_mod, reverse=True))
        for folder, tracks in groups
    )

    # INFO: Return a generator of the groups
    groups = (
        {"folder": folder, "tracks": list(tracks), "time": tracks[0].last_mod}
        for folder, tracks in groups
    )

    # sort groups by last modified date
    return sorted(groups, key=lambda group: group["time"], reverse=True)


def get_recent_items(limit: int = 7):
    tracks = sorted(TrackStore.tracks, key=lambda t: t.created_date)
    groups = group_track_by_folders(tracks)

    recent_items = []

    for group in groups:
        item = check_folder_type(group)

        if item not in recent_items:
            if not item:
                continue

            (
                recent_items.append(item)
                if type(item) == dict
                else recent_items.extend(item)
            )

        if len(recent_items) >= limit:
            break

    return recent_items


def get_recent_tracks(cutoff_days: int):
    tracks = sorted(TrackStore.tracks, key=lambda t: t.created_date, reverse=True)
    timestamp = timestamp_from_days_ago(cutoff_days)

    return [t for t in tracks if t.created_date > timestamp]
