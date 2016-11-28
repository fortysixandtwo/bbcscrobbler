#!/usr/bin/env python
# Authors: Amr Hassan <amr.hassan@gmail.com>
# and hugovk <https://github.com/hugovk>

import argparse
import os
import pylast
from sys import platform as _platform
import subprocess
import time

import bbcrealtime  # https://github.com/hugovk/bbc-tools

API_KEY = "8fe0d07b4879e9cd6f8d78d86a8f447c"
API_SECRET = "debb11ad5da3be07d06fddd8fe95cc42"

SESSION_KEY_FILE = os.path.join(os.path.expanduser("~"), ".session_key")
ONE_HOUR_IN_SECONDS = 60*60

last_output = None
WM_USER = 0x400


class Escape(Exception):
    pass


def osascript(args):
    try:
        return subprocess.check_output(args).strip()
    except Exception as e:
        return("Error: %s" % repr(e))


def is_playing_bbc(now_playing, player_name):
    if "bbc" not in now_playing.lower():
        output(player_name + ":      Not BBC")
        return False
    else:
        if "BBC Radio 1" in now_playing:
            args.station = "bbcradio1"
        elif ("BBC 1Xtra" in now_playing or
              "BBC Radio 1Xtra" in now_playing):
            args.station = "bbc1xtra"
        elif "BBC Radio 2" in now_playing:
            args.station = "bbcradio2"
        elif ("BBC 6Music" in now_playing or
              "BBC 6 Music" in now_playing or
              "6music" in now_playing or
              "BBC Radio 6 Music" in now_playing):
            args.station = "bbc6music"
        else:
            output(player_name + ":      Wrong station")
            return False
        return True
    return False


def check_itunes():
    """
    If not Mac, return True.
    If Mac, return True if iTunes is now playing BBC Radio
    """
    if args.ignore_itunes or _platform != "darwin":
        return True

    else:

        # Is iTunes running?
        count = int(osascript([
            "osascript",
            "-e", "tell application \"System Events\"",
            "-e", "count (every process whose name is \"iTunes\")",
            "-e", "end tell"]))
        if count == 0:
            output("iTunes:      not running")
        else:

            # Is iTunes playing?
            state = osascript([
                "osascript",
                "-e", "tell application \"iTunes\" to player state as string"
                ])

            if state != "playing":
                output("iTunes:      " + state)
            else:
                # Is iTunes playing BBC Radio?
                now_playing = osascript([
                    "osascript",
                    "-e", "tell application \"iTunes\"",
                    "-e", "set thisTitle to name of current track",
                    "-e", "set output to thisTitle",
                    "-e", "end tell"])
                return is_playing_bbc(now_playing, "iTunes")

    return False


def check_winamp():
    """
    If not Windows, return True.
    If Windows, return True if Winamp is now playing BBC Radio
    """
    if args.ignore_winamp or _platform != "win32":
        return True

    else:
        # Is Winamp playing?
        import win32api
        import win32gui
        handle = win32gui.FindWindow('Winamp v1.x', None)
        state = win32api.SendMessage(handle, WM_USER, 0, 104)

        if state == 0:
            output("Winamp:      stopped")
        elif state == 3:
            output("Winamp:      paused")
        elif state != 1:
            output("Winamp:      unknown state " + state)
        elif state == 1:  # playing
            # Is Winamp playing BBC Radio?
            now_playing = win32gui.GetWindowText(handle)
            return is_playing_bbc(now_playing, "Winamp")

        return False


def check_media_player():
    """
    If Mac, check iTunes.
    If Windows, check Winamp.
    Else return True.
    """
    if _platform == "darwin":
        return check_itunes()
    elif _platform == "win32":
        return check_winamp()
    else:
        return True


def update_now_playing(track):
    if not track:
        return
    network.update_now_playing(
        track.artist.name,
        track.title,
        duration=duration(track))
    output("Now playing: %s" % track)


def scrobble(track):
    if not track:
        return
    network.scrobble(
        track.artist.name,
        track.title,
        track.start,
        duration=duration(track))
    output("Scrobbled:   %s" % track)


def output(text):
    global last_output
    if last_output == text:
        return
    else:
        last_output = text
    print(text)
    # Windows:
    if _platform == "win32":
        if "&" in text:
            text = text.replace("&", "^&")  # escape ampersand
        os.system("title " + text)
    # Linux, OS X or Cygwin:
    elif _platform in ["linux", "linux2", "darwin", "cygwin"]:
        import sys
        sys.stdout.write("\x1b]2;" + text + "\x07")


def duration(track):
    """Return duration in seconds"""
    return track.end - track.start


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="BBC Radio scrobbler. "
        "On Mac: scrobbles BBC from iTunes if it's running, "
        "or the station of your choice if --ignore-itunes. "
        "On Windows: scrobbles BBC from Winamp if it's running, "
        "or the station of your choice if --ignore-winamp.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-i', '--ignore-media-player',  action='store_true',
        help='Shortcut for --ignore-itunes on Mac '
        'or --ignore-winamp on Windows')
    parser.add_argument(
        '--ignore-itunes',  action='store_true',
        help='Mac only: Ignore whatever iTunes is doing and scrobble the '
        'station. For example, use this if listening via web or a real '
        'radio.')
    parser.add_argument(
        '--ignore-winamp',  action='store_true',
        help='Windows only: Ignore whatever Winamp is doing and scrobble the '
        'station. For example, use this if listening via web or a real '
        'radio.')
    parser.add_argument(
        'station',  nargs='?', default='bbc6music',
        choices=('bbc6music', 'bbcradio1', 'bbcradio2', 'bbc1xtra'),
        help='BBC station to scrobble')
    args = parser.parse_args()

    if args.ignore_media_player:
        if _platform == "darwin":
            args.ignore_itunes = True
        elif _platform == "win32":
            args.ignore_winamp = True

    network = pylast.LastFMNetwork(API_KEY, API_SECRET)

    if not os.path.exists(SESSION_KEY_FILE):
        skg = pylast.SessionKeyGenerator(network)
        url = skg.get_web_auth_url()

        print(
            "Please authorize the scrobbler "
            "to scrobble to your account: %s\n" % url)
        import webbrowser
        webbrowser.open(url)

        while True:
            try:
                session_key = skg.get_web_auth_session_key(url)
                fp = open(SESSION_KEY_FILE, "w")
                fp.write(session_key)
                fp.close()
                break
            except pylast.WSError:
                time.sleep(1)
    else:
        session_key = open(SESSION_KEY_FILE).read()

    network.session_key = session_key

    last_station = None
    last_scrobbled = None
    playing_track = None
    np_time = None
    scrobble_me_next = None

    try:
        while True:
            if not check_media_player():

                last_station = None
                playing_track = None

            else:

                if last_station != args.station:
                    last_station = args.station
                    output("Tuned in to %s\n---------------------" %
                           args.station)

                try:
                    # Get now playing track
                    realtime = bbcrealtime.nowplaying(args.station)
                    if realtime:
                        new_track = pylast.Track(
                            realtime['artist'], realtime['title'], network)
                        new_track.start = realtime['start']
                        new_track.end = realtime['end']
                    else:
                        new_track = None

                    if new_track and \
                            (time.time() - new_track.end) > \
                            ONE_HOUR_IN_SECONDS:
                        print("Last track over an hour ago, don't scrobble")
                        raise Escape

                    # A new, different track
                    if new_track != playing_track:

                        if scrobble_me_next:
                            scrobble(scrobble_me_next)
                            scrobble_me_next = None
                            last_scrobbled = scrobble_me_next

                        playing_track = new_track
                        update_now_playing(playing_track)
                        np_time = int(time.time())

                    # Scrobblable if 30 seconds has gone by
                    else:
                        now = int(time.time())
                        if playing_track \
                           and playing_track != last_scrobbled \
                           and now - np_time >= 30:
                            scrobble_me_next = playing_track

                except Escape:
                    pass
                except (pylast.NetworkError,
                        pylast.MalformedResponseError) as e:
                    print("Error: %s" % repr(e))

            time.sleep(15)

    except KeyboardInterrupt:
        if scrobble_me_next:
            scrobble(scrobble_me_next)
        print("exit")

# End of file
