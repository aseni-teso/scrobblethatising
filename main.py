import os
import sys
import signal
import argparse
import requests
import configparser
import time
import hashlib
import pylast
import json
import random
import threading
import urllib.parse
import unicodedata
import pydoc

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from collections import OrderedDict
from transliterate import translit

load_dotenv()
api_key = os.getenv("LASTFM_API_KEY")
api_secret = os.getenv("LASTFM_API_SECRET")
username = os.getenv("username")
password = os.getenv("password")

parser = argparse.ArgumentParser(description='Last.fm audio player')
parser.add_argument('-n', '--track', metavar='TRACK', help='Search by track')
# parser.add_argument('-b', '--album', metavar='ALBUM', help='Search by album')
# parser.add_argument('-a', '--artist', metavar='ARTIST', help='Search by artist')
# parser.add_argument('-g', '--tag', metavar='TAG', help='Search by tag')
# parser.add_argument('-u', '--user', metavar='USER', help='Search by user')
args = parser.parse_args()

played_tracks = OrderedDict()
aborted_artists = OrderedDict()
track_finished = False
track_passed = False
artist_aborted = False
next_searched = False
new_track = False
chords_modified = False
tonality = 0

def signal_handler(sig, frame):
    print("\nExiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_network():
    session_key = get_or_generate_session_key()
    network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret, session_key=session_key)
    return network

def search_track(query):
    global new_track, next_searched
    total_tracks = []
    current_page = 1
    current_index = 0
    while True:
        url = "http://ws.audioscrobbler.com/2.0/?method=track.search"
        params = {
                "api_key": api_key,
                "track": query,
                "limit": 5,
                "page": current_page,
                "format": "json"
                }
        print("\nSearching track... ")
        response = requests.get(url, params=params).json()
        tracks = response['results']['trackmatches']['track']
        if not tracks:
            print("No more tracks found.")
            artistname = input("Enter artist name: ")
            trackname = input("Enter track name: ")
            albumname = input("Enter album name: ")
            data = {
                    'track': {
                        'name': trackname,
                        'artist': artistname,
                        'album': albumname
                        }
                    }
            new_track = True
            next_searched = True
            return data['track']

        total_tracks += tracks
        for i, track in enumerate(tracks, start=1):
            print(f"{i + current_index}.{track['name']} by {track['artist']}")

        choice = input("Enter the number of the track you want to play or 'n' for the next page... ")
        if choice.lower() == 'n':
            current_page += 1
            current_index += 5
            continue

        try:
            choice_index = int(choice) - 1
            selected_track = total_tracks[choice_index]
            print(f"Your choice is {selected_track['name']} by {selected_track['artist']}")
            return selected_track
        except (ValueError, IndexError):
            print("Invalid input. Please try again")

    return None

# def search_album(query):
#     url = "http://ws.audioscrobbler.com/2.0/?method=album.search"
#     params = {
#             "api_key": api_key,
#             "album": query,
#             "format": "json"
#             }
#     print("\nSearching album... ")
#     response = requests.get(url, params=params).json()
#     album = response['results']['albummatches']['album'][0]
#     print("OK")
#     return album

# def search_artist(query):
#     url = "http://ws.audioscrobbler.com/2.0/?method=artist.search"
#     params = {
#             "api_key": api_key,
#             "artist": query,
#             "format": "json"
#             }
#     print("\nSearching artist... ")
#     response = requests.get(url, params=params).json()
#     artist = response['results']['artistmatches']['artist'][0]
#     print("OK")
#     return artist

# def search_tag(query):
#     url = "http://ws.audioscrobbler.com/2.0/?method=tag.search"
#     params = {
#             "api_key": api_key,
#             "tag": query,
#             "format": "json"
#             }
#     print("\nSearching tag... ")
#     response = requests.get(url, params=params).json()
#     tag = response['results']['tagmatches']['tag'][0]
#     print("OK")
#     return tag

def add_to_played_tracks(artist, track, scrobbled):
    key = f"{artist} - {track}"
    if artist and track:
        key = key.lower()
    # print("before: ", played_tracks)
    if len(played_tracks) < 1:
        played_tracks[key] = 1
        return
    if key in played_tracks:
        played_tracks.pop(key)
        played_tracks[key] = 1
    else:
        played_tracks[key] = 1
    if not scrobbled:
        played_tracks.move_to_end(key, last=False)
    # print("after: ", played_tracks)

def get_previous_track():
    if len(played_tracks):
        keys = list(played_tracks.keys())
        previous_key = keys[-1]
        previous_value = played_tracks[previous_key]
        artist, track = previous_key.split(" - ", 1)

        data = {
                'name': track,
                'artist': artist
                }
        json_data = json.dumps(data)
        return json_data
    else:
        return None

def scrobble_track(artist, track, album):
    network = get_network()
    try:
        network.scrobble(artist=artist, title=track, album=album, timestamp=int(time.time()))
    except pylast.WSError as e:
        print(f"Ошибка: {e}")
        return None
    return "Success"

def update_now_playing(artist, track, album):
    network = get_network()
    try:
        network.update_now_playing(artist=artist, title=track, album=album) 
    except pylast.WSError as e:
        print(f"Ошибка: {e}")
        return None
    return "Success"

# def add_to_loved_tracks(artist, track):
#     network = get_network()
#     try:
#         track_object = network.get_track(artist=artist, title=track) 
#         track_object.love()
#     except pylast.WSError as e:
#         print(f"Ошибка: {e}")
#         return None
#     return "Success"

def users_track_info(artist, track):
    network = get_network()
    track = pylast.Track(artist=artist, title=track, network=network, username=username)

    loved = track.get_userloved()
    assert loved is not None
    assert isinstance(loved, bool)
    assert not isinstance(loved, str)

    count = track.get_userplaycount()

    print(f"You listen this track {count} times.")
    if loved:
        print("You LOVE this track.")
        return
    return

def get_track_album(artist, track):
    url = "http://ws.audioscrobbler.com/2.0/?method=track.getInfo"
    params = {
            "api_key": api_key,
            "artist": artist,
            "track": track,
            "format": "json"
            }
    response = requests.get(url, params=params).json()
    if response['track'].get('album'):
        album = response['track']['album']['title']
    else:
        album = None
    return album

def get_text_and_chords(artist, track, site):
    track_href = ""
    artist = artist.lower().replace("ё", "е")
    track = track.lower().replace("ё", "е")
    print(f"Find by {site}")
    artist_link = get_artist_link(artist, site)
    if not artist_link:
        artist_words = artist.split()
        if len(artist_words) > 1:
            artist_reversed = ' '.join(reversed(artist_words))
            artist_link = get_artist_link(artist_reversed, site)
            if not artist_link:
                return None
        else:
            return None

    artist_url = f"https://www.muzbar.ru{artist_link}"
    if site == "oduvanchik":
        artist_url = f"https://www.oduvanchik.net/{artist_link}"
    elif site == "mytabs":
        artist_url = f"https://mytabs.ru{artist_link}"

    print("Artist's url is found: ",artist_url)
    response = requests.get(artist_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        if site == "oduvanchik":
            table = soup.find('div', class_='text')
            links = table.find_all('a', href=lambda href: href and 'view_song' in href)
        elif site == "mytabs":
            table = soup.find('div', class_='table-responsive')
            links = table.find_all('a', class_='songtitle')
        else:
            table = soup.find('table', class_='tabs_table')
            links = table.find_all('a')
        for link in links:
            link_text = link.get_text(strip=True)
            link_text = link_text.lower().replace("ё", "е")
            if track in link_text:
                track_link = link
                if track_link:
                    track_href = track_link.get('href')
    if track_href:
        track_url = f"https://www.muzbar.ru{track_href}"
        if site == "oduvanchik":
            track_url = f"https://www.oduvanchik.net/{track_href}"
        elif site == "mytabs":
            track_url = f"https://mytabs.ru{track_href}"
        print("Track's url is found: ",track_url)
        response = requests.get(track_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            text_and_chords_div = soup.find('div', class_='chords')
            if text_and_chords_div:
                pre_tags = text_and_chords_div.find_all('pre')
            if site == "oduvanchik" or "mytabs":
                pre_tags = soup.find_all('pre')
                for pre_tag in pre_tags:
                    text = pre_tag.get_text().replace('\n', '\n')
                    return text
            text_and_chords = '\n\n'.join(pre_tag.get_text(strip=True) for pre_tag in pre_tags)
            return text_and_chords
    else:
        return None

def is_cyrillic(char):
    return unicodedata.name(char).find('CYRILLIC') >= 0

def transliterate_letter(letter):
    if letter.isalpha():
        return translit(letter, 'ru', reversed=True).lower()
    else:
        return letter

def get_artist_link(artist, site):
    first_word = artist.split()[0]
    letter = first_word[0]
    if site == "oduvanchik":
        letter = letter.upper()
        letter_bytes = letter.encode('cp1251')
        letter_hex = letter_bytes.hex().upper()
        letter = urllib.parse.quote_plus('{}'.format(letter_hex))
    elif site == "mytabs":
        if is_cyrillic(letter):
            letter = transliterate_letter(letter)
            if len(letter) == 1:
                letter = f"{letter}-r"
    if letter.isdigit():
        letter = "other"
        if site == "oduvanchik" or "mytabs":
            letter = "0-9"

    letter_url = f"https://www.muzbar.ru/tabs/?letter={letter}"
    if site == "oduvanchik":
        letter_url = f"https://www.oduvanchik.net/art_ltr.php?id=%{letter}"
    elif site == "mytabs":
        letter_url = f"https://mytabs.ru/akkordy/{letter}"
    if letter_url:
        print(f"{letter}-letter's url is found: ", letter_url)
    else:
        print(f"{letter}-letter's is not found.")

    response = requests.get(letter_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        media_bodies = soup.find_all('div', class_='media-body')
        for media_body in media_bodies:
            link = media_body.find('a')
            if link:
                link_text = link.get_text(strip=True)
                link_text = link_text.lower().replace("ё", "е")
                if link_text == artist:
                    artist_link = link
                    if artist_link:
                        artist_href = artist_link.get('href')
                        return artist_href
        if site == "oduvanchik":
            artists_table_div = soup.find('div', class_='text')
            if artists_table_div:
                artists_table = artists_table_div.find('table')
                if artists_table:
                    links = artists_table.find_all('a')
                    for link in links:
                        link_text = link.get_text(strip=True)
                        link_text = link_text.lower().replace("ё", "е")
                        if link_text == artist:
                            artist_link = link
                            if artist_link:
                                artist_href = artist_link.get('href')
                                return artist_href

        elif site == "mytabs":
            current_page = 1
            while True:
                if current_page > 1:
                    letter_url = f"https://mytabs.ru/akkordy/{letter}?page={current_page}"
                    response = requests.get(letter_url)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                artists_table_div = soup.find('div', class_='table-responsive')
                if artists_table_div:
                    links = artists_table_div.find_all('a')
                    for link in links:
                        link_text = link.get_text(strip=True)
                        link_text = link_text.lower().replace("ё", "е")
                        if link_text == artist:
                            artist_link = link
                            if artist_link:
                                artist_href = artist_link.get('href')
                                # print("Artist's href is", artist_href)
                                return artist_href
                pagenavi = soup.find('div', class_='wp-pagenavi')
                if pagenavi:
                    last_page_link = pagenavi.find_all('a')[-2]
                    max_page = 0
                    if last_page_link and last_page_link.get_text().isdigit():
                        max_page = int(last_page_link.get_text())
                    else:
                        break
                    print(f"Find artist: page {current_page} of {max_page}")
                    if current_page >= max_page:
                        break
                current_page += 1

def play_track(track):
    global track_finished, track_passed, artist_aborted, next_searched, new_track, chords_modified, tonality
    while True:
        if isinstance(track.get('artist'), dict):
            artist_name = track['artist'].get('name', '')
        else:
            artist_name = track.get('artist', '')
        print("Artist: ", artist_name)
        print("Track: ", track['name'])
        if not new_track:
            album = get_track_album(artist_name, track['name'])
        else:
            album = track['album']
        print("Album: ", album)

        scrobbled = False
        if not new_track:
            users_track_info(artist_name, track['name'])

        text_and_chords = get_text_and_chords(artist_name, track['name'], "mytabs")
        if not text_and_chords:
            text_and_chords = get_text_and_chords(artist_name, track['name'], "muzbar")
            if not text_and_chords:
                text_and_chords = get_text_and_chords(artist_name, track['name'], "oduvanchik")

        input_thread = None
        if text_and_chords:
            pydoc.pager(text_and_chords)
        else:
            print("Text and chords are not found.")
        if input_thread:
            input_thread.join()
        input_thread = threading.Thread(target=input_listener)
        input_thread.start()

        modified_chords_displayed = False
        while not track_finished:
            if chords_modified and not modified_chords_displayed:
               text_and_chords = modify_chords(text_and_chords, tonality)
               print(text_and_chords)
               modified_chords_displayed = True

            update_now_playing(artist_name, track['name'], album)
            if track_finished:
                break
            time.sleep(1)

        if track_finished:
            print("Track is finishing...")
            if artist_aborted:
                print("Artist is aborting...")
                key = artist_name
                if key in played_tracks:
                    aborted_artists[key] += 1
                else:
                    aborted_artists[key] = 1
                add_to_played_tracks(artist_name, track['name'], scrobbled)
                previous_track = get_previous_track()
                similar_track = search_similar_track(previous_track)
                if isinstance(previous_track, str):
                    previous_track = json.loads(previous_track)
                artist_name = previous_track['artist']
                artist_aborted = False
                track_finished = False
                track = get_similar_artist_track(artist_name)
            elif next_searched:
                print("Searching of next track...")
                if not track_passed:
                    print("\nScrobbling... ")
                    scrobble_track(artist_name, track['name'], album)
                    scrobbled = True
                    print("OK")
                add_to_played_tracks(artist_name, track['name'], scrobbled)
                query = input("Input your search query: ")
                next_searched = False
                track_finished = False
                track_passed = False
                new_track = False
                track = search_track(query)
            else:
                if not track_passed:
                    print("\nScrobbling... ")
                    scrobble_track(artist_name, track['name'], album)
                    scrobbled = True
                    print("OK")
                    add_to_played_tracks(artist_name, track['name'], scrobbled)
                    similar_track = search_similar_track(track)
                else:
                    print("Track is passing...")
                    add_to_played_tracks(artist_name, track['name'], scrobbled)
                    previous_track = get_previous_track()
                    similar_track = search_similar_track(previous_track)
                    track_passed = False
                track_finished = False
                track = similar_track
        else:
            break

def input_listener():
    global track_finished, track_passed, artist_aborted, next_searched, chords_modified, tonality
    user_input = input()
    print("Your input is", user_input)
    while not track_finished:

        if user_input.lower() == 'q':
            track_finished = True

        elif user_input.lower() == 'p':
            track_passed = True
            track_finished = True

        elif user_input.lower() == 'n':
           artist_aborted = True
           track_finished = True

        elif user_input.lower() == 'qs':
            track_finished = True
            next_searched = True

        elif user_input.lower() == 'ps':
            track_passed = True
            track_finished = True
            next_searched = True
        elif user_input.startswith('m '):
            try:
                tonality = int(user_input.split()[1])
                chords_modified = True
            except (IndexError, ValueError):
                print("Invalid input. Please use 'm <number>' format.")
        else:
            print("Invalid input. Please try again.")
        user_input = input()

def modify_chords(text_and_chords, tonality):
    chord_mapping = {
        "A": 0, "B": 1, "H": 2, "C": 3, "C#": 4, "D": 5, "D#": 6, "E": 7, "F": 8, "F#": 9, "G": 10, "G#": 11
    }

    soup = BeautifulSoup(text_and_chords, 'html.parser')
    text = soup.get_text(strip=True)
    chords = soup.find_all('span', class_='chords')

    modified_chords = []

    for chord in chords:
        chord_name = chord.text
        root_note = chord_name[0]
        if root_note not in chord_mapping:
            continue
        note_index = chord_mapping[root_note]
        modified_index = (note_index + tonality) % 12

        for note, index in chord_mapping.items():
            if index == modified_index:
                modified_name = note + chord_name[1:]
                break
        modified_chord = f"<span class=\"chord\"data-chid=\"{chord['data-chid']}\">{modified_name}</span>"
        modified_chords.append(modified_chord)
    modified_text = text + "\n\n" + "\n".join(modified_chords)
    return modified_text

# def play_album(album):
#     track_list = get_album_tracks(album)
#     for track in track_list:
#         track_url = get_track_url(track)
#         if isinstance(track.get('artist'), dict):
#             artist_name = track['artist'].get('name', '')
#         else:
#             artist_name = track.get('artist', '')
#         print("Artist: ", artist_name)
#         print("Track: ", track['name'])
#         album_name = get_track_album(artist_name, track['name'])
#         subprocess.run(['mpv', '--no-video', '--no-sub', track_url])
#         scrobble_track(artist_name, track['name'], album_name)

# def get_album_tracks(album):
#     album_search_url = "http://ws.audioscrobbler.com/2.0/?method=album.search"
#     params = {
#             "api_key": api_key,
#             "artist": album['artist'],
#             "album": album['name'],
#             "format": "json"
#             }
#     search_response = requests.get(album_search_url, params=params).json()
#     album_matches = search_response.get('results', {}).get('albummatches', {}).get('album', [])
#     if album_matches:
#         album_info = album_matches[0]
#         album_info_url = "http://ws.audioscrobbler.com/2.0/?method=album.getInfo"
#         album_params = {
#                 "api_key": api_key,
#                 "artist": album_info['artist'],
#                 "album": album_info['name'],
#                 "format": "json"
#                 }
#         info_response = requests.get(album_info_url, params=album_params).json()
#         track_list = info_response['album']['tracks']['track']

#         return track_list
#     else:
#         return None

# def play_artist_tracks(artist):
#     track_list = get_artist_tracks(artist)
#     for track in track_list:
#         track_url = get_track_url(track)
#         if isinstance(track.get('artist'), dict):
#             artist_name = track['artist'].get('name', '')
#         else:
#             artist_name = track.get('artist', '')
#         print("Artist: ", artist_name)
#         print("Track: ", track['name'])
#         album_name = get_track_album(artist_name, track['name'])
#         subprocess.run(['mpv', '--no-video', '--no-sub', track_url])
#         scrobble_track(artist_name, track['name'], album_name)

# def play_artist_albums(artist):
#     album_list = get_artist_albums(artist)
#     for album in album_list:
#             play_album(album)

# def get_artist_tracks(artist):
#     url = "http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks"
#     params = {
#             "api_key": api_key,
#             "artist": artist['name'],
#             "format": "json"
#             }
#     response = requests.get(url, params=params).json()
#     track_list = response['toptracks']['track']
#     return track_list

# def get_artist_albums(artist):
#     url = "http://ws.audioscrobbler.com/2.0/?method=artist.gettopalbums"
#     params = {
#             "api_key": api_key,
#             "artist": artist['name'],
#             "format": "json"
#             }
#     response = requests.get(url, params=params).json()
#     album_list = response['topalbums']['album']
#     return album_list

# def play_tag(tag):
#     track_list = get_popular_tracks_by_tag(tag)
#     for track in track_list:
#         track_url = get_track_url(track)
#         if isinstance(track.get('artist'), dict):
#             artist_name = track['artist'].get('name', '')
#         else:
#             artist_name = track.get('artist', '')
#         print("Artist: ", artist_name)
#         print("Track: ", track['name'])
#         album_name = get_track_album(artist_name, track['name'])
#         subprocess.run(['mpv', '--no-video', '--no-sub', track_url])
#         scrobble_track(artist_name, track['name'], album_name)

# def play_user(user):
#     track_list = get_popular_tracks_by_user(user)
#     for track in track_list:
#         track_url = get_track_url(track)
#         if isinstance(track.get('artist'), dict):
#             artist_name = track['artist'].get('name', '')
#         else:
#             artist_name = track.get('artist', '')
#         print("Artist: ", artist_name)
#         print("Track: ", track['name'])
#         album_name = get_track_album(artist_name, track['name'])
#         subprocess.run(['mpv', '--no-video', '--no-sub', track_url])
#         scrobble_track(artist_name, track['name'], album_name)

# def get_popular_tracks_by_tag(tag):
#     url = "http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks"
#     params = {
#             "api_key": api_key,
#             "tag": tag,
#             "format": "json"
#             }
#     response = requests.get(url, params=params).json()
#     track_list = response['tracks']['track']
#     return track_list

# def get_popular_tracks_by_user(user):
#     url = "http://ws.audioscrobbler.com/2.0/?method=user.gettoptracks"
#     params = {
#             "api_key": api_key,
#             "user": user,
#             "format": "json"
#             }
#     response = requests.get(url, params=params).json()
#     track_list = response['toptracks']['track']
#     return track_list
def search_similar_track(track):
    url = "http://ws.audioscrobbler.com/2.0/?method=track.getsimilar"
    if isinstance(track, str):
        track = json.loads(track)
    if isinstance(track.get('artist'), dict):
        artist_name = track['artist']['name']
    else:
        artist_name = track['artist']
    params = {
        "api_key": api_key,
        "artist": artist_name,
        "track": track['name'],
        "limit": 50,
        "format": "json"
        }
    print("\nSearching next track... ")
    response = requests.get(url, params=params).json()
    if response.get('similartracks'):
        similar_tracks = response['similartracks']['track']
    else:
        similar_artist_track = get_similar_artist_track(artist_name)
        return similar_artist_track 


    if not similar_tracks:
        similar_track = extract_similar_track_from_html(artist_name, track['name'])
        if not similar_track:
            similar_artist_track = get_similar_artist_track(artist_name)
            if similar_artist_track:
                print(f"\nNext track is similar on artist: {similar_artist_track['artist']['name']} - {similar_artist_track['name']}")
            else:
                random_track = get_random_loved_track()
                print(f"\nNext track is random loved track: {random_track['artist']['name']} - {random_track['name']}")
                return random_track
            return similar_artist_track
        print(f"\nNext track is similar on track: {similar_track['artist']} - {similar_track['name']}")
        return similar_track

    for similar_track in similar_tracks:
        key = f"{similar_track['artist']['name']} - {similar_track['name']}"
        key_lower = key.lower()
        print("key: ", key_lower)
        print("played_tracks: ", played_tracks)
        if key_lower not in played_tracks:
            print(f"\nNext track is similar on track: {similar_track['artist']['name']} - {similar_track['name']}")
            return similar_track

def get_random_loved_track():
    print("Searching random loved track... ")
    url = "http://ws.audioscrobbler.com/2.0/?method=user.getlovedtracks"
    user = username
    params = {
            "api_key": api_key,
            "user": user,
            "format": "json"
            }
    response = requests.get(url, params=params).json()
    total_pages = int(response['lovedtracks']['@attr']['totalPages'])
    if total_pages == 0:
        raise ValueError("You have no tracks in your lovedtracks.")
    random_page = random.randint(1, total_pages)
    params["page"] = random_page
    response = requests.get(url, params=params).json()
    track_list = response['lovedtracks']['track']
    random_track = random.choice(track_list)
    print("OK")
    return random_track

def extract_similar_track_from_html(artist, track):
    track_url = f"https://www.last.fm/music/{artist}/_/{track}"
    response = requests.get(track_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        similar_track_section = soup.find('h3', string='Similar Tracks')
        if similar_track_section:
            similar_track_section = similar_track_section.find_next('ol')
            similar_tracks_items = similar_track_section.find_all('li')
            for item in similar_tracks_items:
                track_title = item.find('h3').find('a').text.strip()
                track_artist = item.find('p').find('span').find('a').text.strip()
                key = f"{track_artist} - {track_title}"
                if key not in played_tracks:
                    data = {
                            'name': track_title,
                            'artist': track_artist
                            }
                    similar_track = json.dumps(data)
                    if isinstance(similar_track, str):
                        similar_track = json.loads(similar_track)
                    return similar_track

def get_similar_artist_track(artist):
    if artist != 'None':
        artist_params = {
                "api_key": api_key,
                "artist": artist,
                "limit": 12,
                "format": "json"
                }
        similar_artist_response = requests.get("http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar", params=artist_params).json()
        similar_artists = similar_artist_response['similarartists']['artist']

        if not similar_artists:
            similar_artists = extract_similar_artist_from_html(artist)

        for artist in similar_artists:
            if 'artist' in artist:
                artist_name = artist['artist']
            else:
                artist_name = artist['name']
            key = f"{artist_name}"
            if key not in aborted_artists:
                top_tracks_params = {
                    "api_key": api_key,
                    "artist": artist_name,
                    "limit": 6,
                    "format": "json"
                    }
                top_tracks_response = requests.get("http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks", params=top_tracks_params).json()
                top_tracks = top_tracks_response['toptracks']['track']

                for top_track in top_tracks:
                    key = f"{top_track['artist']['name']} - {top_track['name']}"
                    if key not in played_tracks:
                        # print("OK")
                        return top_track

def extract_similar_artist_from_html(artist):
    similar_artists = []
    artist_url = f"https://www.last.fm/music/{artist}/+similar"
    response = requests.get(artist_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        similar_artists_section = soup.find('h2', string='Similar Artists')
        if similar_artists_section:
            similar_artists_section = similar_artists_section.find_next('ol')
            similar_artists_items = similar_artists_section.find_all('li')
            for item in similar_artists_items:
                if item.find('h3'):
                    artist_title = item.find('h3').find('a').text.strip()
                    similar_artists.append({'artist': artist_title})
                    similar_artists = json.dumps(similar_artists)
                    if isinstance(similar_artists, str):
                        similar_artists = json.loads(similar_artists)
            return similar_artists
    
def get_request_token(api_key, api_secret):
    url = "http://ws.audioscrobbler.com/2.0/?method=auth.getToken"
    api_sig = hashlib.md5((f"api_key{api_key}methodauth.getToken{api_secret}").encode()).hexdigest()
    params = {
            "api_key": api_key,
            "api_sig": api_sig,
            "format": "json"
            }
    response = requests.post(url, data=params).json()
    token = response["token"]
    return token

def get_session_key(api_key, api_secret, token):
    url = "http://ws.audioscrobbler.com/2.0/?method=auth.getSession"
    api_sig = hashlib.md5((f"api_key{api_key}methodauth.getSessiontoken{token}{api_secret}").encode()).hexdigest()
    params = {
            "api_key": api_key,
            "api_sig": api_sig,
            "token": token,
            "format": "json"
            }
    response = requests.post(url, data=params).json()
    session_key = response['session']['key']
    return session_key

def get_or_generate_session_key():
    config = configparser.ConfigParser()
    config.read('config.ini')
    if config.has_option('AUTH', 'SESSION_KEY'):
        session_key = config.get('AUTH', 'SESSION_KEY')
        return session_key
    else:
        token = get_request_token(api_key, api_secret)
        auth_url = f"http://www.last.fm/api/auth?api_key={api_key}&token={token}"
        print(f"Please grant permission at: {auth_url}")
        input("Press Enter after granting permission...")
        session_key = get_session_key(api_key, api_secret, token)
        save_session_key(session_key)
        return session_key

def save_session_key(session_key):
    config = configparser.ConfigParser()
    config.read('config.ini')
    if not config.has_section('AUTH'):
        config.add_section('AUTH')
    config.set('AUTH', 'SESSION_KEY', session_key)
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

def main():
    try:
        if args.track:
            track = search_track(args.track)
            play_track(track)

        # elif args.album:
        #     album = search_album(args.album)
        #     play_album(album)

        # elif args.artist:
        #     artist = search_artist(args.artist)
        #     display_choice = input("Play artist's tracks (1) or albums (2). Input 1 or 2: ")
        #     if display_choice == "1":
        #         play_artist_tracks(artist)
        #     elif display_choice == "2":
        #         play_artist_albums(artist)

        # elif args.tag:
        #     tag = args.tag        
        #     play_tag(tag)

        # elif args.user:
        #     user = args.user
        #     play_user(user)

        else:
            add_to_played_tracks(None, None, False)
            track = get_random_loved_track()
            play_track(track)
    except pylast.NetworkError as e:
        print("Network error:", str(e))

if __name__ == "__main__":
    main()

