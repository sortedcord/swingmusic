import re
import os

from app.utils.filesystem import get_path_depth
from app.db.sqlite.tracks import SQLiteTrackMethods
 
def parse_tracks(m3u_file_string):

    """
    Parses m3u files for tracks.
    Takes in raw m3u file string as a parameter.
    """

    tracks = []
    for line in m3u_file_string.split("\n#EXTINF:"):
        
        # Line checks
        if "#EXTM3U" in line:
            continue

        # A typical song is stored as: 
        #         419,Alice in Chains - Rotten Apple
        #         Alice in Chains_Jar of Flies_01_Rotten Apple.mp3

        default_patterns = [
            r'(?P<duration>\d+),(?P<artist>.+?) - (?P<title>.+)\n(?P<file_path>.+)',
            r'(?P<duration>\d+),(?P<artist>.+?) - (?P<title>.+)', # In case file path isn't mentioned.. (Useful for importing from online streaming services)
            ]
        
        for pattern in default_patterns:
            match =  re.match(pattern, line)

            if not match:
                continue

            track = {}
            

            # Might not be the best way to deal with improper formatting. Needs Improvement
            # NOTE: Certain tags like: Duration, Artist and Title are necessary. Track will not be processed in any of these are missing.

            try:track['duration'] = match.group('duration')
            except: continue
            try:track['artist'] = match.group('artist')
            except: continue
            try:track['title'] = match.group('title')
            except: continue
            try:track['file_path'] = match.group('file_path')
            except: pass

            track['file_exists'] = False

            tracks.append(track)
            break

    return tracks if tracks else None


def match_track_filename(track):
    if 'file_path' not in track.keys():
        return False, None
    
    file_path = track['file_path']
    file_name = os.path.splitext(get_path_depth(file_path)[-1])[0]

    filter_results = []

    for result in SQLiteTrackMethods.get_tracks_by_filename(file_name):
        if track['artist'].lower() in [artist.name.lower() for artist in result.artists]:
            # Artist matches up
                
            if abs(int(track['duration']) - int(result.duration)) <= 10:
                # Duration matches up
                return True, result
        
            filter_results.append(result)
    
    return False, filter_results


def match_track(track):
    """
    Takes in the track following the structure in the parse_tracks function.
    """

    # Try matching via filenames
    matched, result_track = match_track_filename(track)
    if matched:
        return result_track
    
            
    # Compare by Track > Artist
    for result in SQLiteTrackMethods.get_tracks_by_title(track['title']):

        if track['artist'].lower() in [artist.name.lower() for artist in result.artists]:

            duration_delta = abs(int(track['duration']) - int(result.duration)) <= 10
            
            return result_track if duration_delta else None
    
    # Some other patterns that can be added in the future
    return None