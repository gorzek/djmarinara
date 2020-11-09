#!/usr/bin/env python
"""Simple shim around the djmarinara module. Runs with default settings.
"""

import djmarinara

# Set configuration here.
dj = djmarinara.djmarinara(
    extensions=['zip', 'xm', 'it', 's3m', 'mod', 'mp3', 'mp4', 'flac', 'm4a', 'aac', 'flv', '3gp', 'ogg', 'ra', 'rm'],
    temppath="/tmp/songs",
    mediapath="/media",
    playlisturl="[YOUR_PLAYLIST_URL_HERE]",
    fonturl="[YOUR_FONT_URL_HERE]",
    startupvideo="[YOUR_STARTUP_VIDEO_HERE]",
    gastanklimit=3600.0,
    targetspeed=2.0
)
# Run!
# Will run until terminated forcefully.
dj.run()
