#!/usr/bin/env python
"""Automatically pre-renders a queue of videos for live streaming.

djmarinara does the following:
1) Polls a URL to obtain a list of URLs of songs.
2) Chooses a song URL at random.
3) Generates a video from the song, with visualizer output and song text (ID3 tags, etc.)
4) Manages playlist files for use by ffmpeg's ffconcat demuxer.
5) Manages the playlist buffer to ensure limited disk space usage and a healthy buffer of queued songs.
"""

import glob
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.parse as parse
import urllib.request as request
import zipfile
from contextlib import closing
from pathlib import Path

__author__ = "James Huffman"
__copyright__ = "Copyright 2020, James Huffman"
__credits__ = ["James Huffman"]
__license__ = "Unlicense"
__version__ = "1.0.3"
__maintainer__ = "James Huffman"
__email__ = "gorzek@gmail.com"


class djmarinara:
    def __init__(self,
                 extensions=['zip', 'xm', 'it', 's3m', 'mod', 'mp3', 'mp4', 'flac', 'm4a', 'aac', 'flv', '3gp', 'ogg',
                             'ra', 'rm'],
                 temppath="/tmp/songs",
                 mediapath="/media",
                 playlisturl="",
                 fonturl="",
                 startupvideo="",
                 gastanklimit=3600.0,
                 targetspeed=2.0):
        self.extensions = extensions
        self.temppath = temppath
        self.mediapath = mediapath
        self.playlisturl = playlisturl
        self.fonturl = fonturl
        self.startupvideo = startupvideo
        self.gastanklimit = gastanklimit
        self.listhash = ""
        self.linewidth = 80
        self.getFont()
        self.maxlength = (gastanklimit / 2.0)
        self.manifest = open('manifest', 'r').read().split("\n")
        self.crf = 17
        self.mincrf = 17  # Best quality with compression
        self.maxcrf = 28  # Worst acceptable quality
        self.targetspeed = targetspeed
        self.qualitypresets = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower',
                               'veryslow']
        self.preset = 0  # Use ultrafast to start

    def initRun(self):
        self.gastank = 0
        self.getFileNumber()
        self.elapsedtime = 0.0
        self.starttime = time.time()

    def run(self):
        self.initRun()
        while 1:
            self.sanityCheck()
            self.playlistCheck()

    def sanityCheck(self):
        if not os.path.exists(os.path.join(self.mediapath, "playlist0.txt")):
            print("Playlist sanity check failed. Fixing...")
            outfile = open('/media/playlist0.txt', 'w')
            outfile.write("ffconcat version 1.0\n")
            outfile.write("file startup.flv\n")
            outfile.write("file playlist1.txt\n")
            outfile.close()
            outfile = open('/media/playlist1.txt', 'w')
            outfile.write("ffconcat version 1.0\n")
            outfile.write("file startup.flv\n")
            outfile.write("file playlist0.txt\n")
            outfile.close()
            self.filenumber = 0
        if not os.path.exists(os.path.join(self.mediapath, "startup.flv")):
            print("Startup video sanity check failed. Fixing...")
            with closing(request.urlopen(self.startupvideo)) as r:
                print("Opening URL:", self.startupvideo)
                with open("/media/startup.flv", 'wb') as f:
                    print("Downloading:", "/media/startup.flv")
                    shutil.copyfileobj(r, f)
            self.filenumber = 0

    def getFont(self):
        with closing(request.urlopen(self.fonturl)) as r:
            print("Opening URL:", self.fonturl)
            with open('font.ttf', 'wb') as f:
                print("Downloading:", 'font.ttf')
                shutil.copyfileobj(r, f)

    def getFileNumber(self):
        try:
            filelist = glob.glob(self.mediapath + '/*.txt')
            filelist.sort(key=self.naturalKeys)
            lastfile = filelist[-1]
            lastnumber = int(''.join(list(filter(str.isdigit, lastfile))))
            # False positive caused by the presence of 2 initial playlists!
            # Just reset back to 1 if we find it
            if lastnumber == 1:
                lastnumber = 0
        except:
            print("Couldn't find valid startup files!")
            lastnumber = 0
        print("File number is now:", lastnumber)
        self.filenumber = lastnumber

    def playlistCheck(self):
        with closing(request.urlopen(self.playlisturl)) as r:
            hasher = hashlib.md5()
            buf = r.read()
            hasher.update(buf)
            newhash = hasher.hexdigest()
            # Update the playlist immediately if the source file changed!
            # Otherwise, check the gas tank. Pre-render if we're not full.
            # If we're full, just sleep for 60 seconds.
            if (newhash != self.listhash):
                print("Remote playlist updated!")
                self.listhash = newhash
                self.updatePlaylist(str(buf))
            elif self.checkGas() < self.gastanklimit:
                print("Filling up gas tank! (", self.gastank, " of ", self.gastanklimit, " seconds ready...)")
                self.updatePlaylist(str(buf))
            else:
                print("Gas tank is at ", self.gastank, " seconds, so wait...")
                # Sleep until the gas tank falls below full.
                time.sleep(self.gastank - self.gastanklimit)

    def checkGas(self):
        # Reduce gastank by the time elapsed since last elapsedtime.
        # Then return the current value of gastank.
        curtime = time.time()
        newelapsed = curtime - self.starttime
        gasused = newelapsed - self.elapsedtime
        print("Elapsed since start:", newelapsed)
        print("Gas used this round:", gasused)
        self.gastank -= gasused
        self.elapsedtime = newelapsed
        return self.gastank

    def processZip(self, zf):
        print("Unzipping:", zf)
        playfile = ""
        candidates = []
        # Wrap the entire zipfile block
        # Don't want it to blow up the entire program!
        try:
            with zipfile.ZipFile(zf, "r") as zip_ref:
                try:
                    os.makedirs(self.temppath)
                except:
                    pass
                try:
                    zip_ref.extractall(self.temppath)
                    for root, dirs, files in os.walk(self.temppath):
                        for file in files:
                            filelower = file.lower()
                            extension = filelower.split(".")[-1]
                            if extension in self.extensions:
                                candidatepath = os.path.join(root, file)
                                candidatepath = candidatepath.replace("\\", "/")
                                candidates.append(candidatepath)
                                print("Candidate file:", candidatepath)
                except:
                    # Naughty zip file!
                    # Just skip it.
                    print("Bad zip file:", zf)
                    print("We'll skip this one...")
        except:
            print("Bad zip file:", zf)
            print("We'll skip this one...")
        if len(candidates) > 0:
            choice = random.choice(candidates)
            playfile = choice.split("/")[-1].lower()
            shutil.move(choice, playfile)
        # Now clean up.
        for filename in os.listdir(self.temppath):
            filepath = os.path.join(self.temppath, filename)
            try:
                shutil.rmtree(filepath)
            except OSError:
                os.remove(filepath)
        os.remove(zf)
        return playfile

    def processFile(self, file):
        processstart = time.time()
        filename = file.split("/")[-1].lower()
        print("Filename:", filename)
        parts = file.split("://")
        protocol = parts[0]
        urlstring = parts[1]
        newfile = protocol + "://" + parse.quote(urlstring)
        print("Parsed:", newfile)
        try:
            with closing(request.urlopen(newfile)) as r:
                print("Opening URL:", file)
                with open(filename, 'wb') as f:
                    print("Downloading:", filename)
                    shutil.copyfileobj(r, f)
                # ZIP files need to be extracted and scanned.
                if filename.endswith('.zip'):
                    sourcefile = self.processZip(filename)
                    # The returned file might be znother zip!
                    # Process it, too.
                    while sourcefile.endswith('.zip'):
                        sourcefile = self.processZip(sourcefile)
                else:
                    sourcefile = filename
                # No file? No sleep!
                # No file at this point means something went wrong acquiring the source
                if sourcefile == "":
                    return 0
                # Convert the file into a video we can queue
                filedata = self.convertFile(sourcefile)
                # Should get back a dictionary.
                # No file? No sleep!
                # No file at this point means we couldn't convert for some reason
                if 'playfile' not in filedata.keys():
                    # Clean up the original file if we couldn't convert it
                    os.remove(sourcefile)
                    return 0
                else:
                    playfile = filedata['playfile']
                # Copy file to destination
                # It's expected that playfile is in the current directory
                print("Queueing:", playfile)
                shutil.copy(playfile, self.mediapath + "/" + playfile)
                # Add playfile to a playlist in /media
                # Increment filenumber
                self.filenumber += 1
                playlistfile = self.mediapath + "/playlist" + str(self.filenumber) + ".txt"
                playlist = open(playlistfile, 'w')
                playlist.write("ffconcat version 1.0\n")
                playlist.write("file " + playfile + "\n")
                playlist.write("file playlist" + str(self.filenumber + 1) + ".txt\n")
                # Clean up local file(s)
                os.remove(playfile)
                # Add duration to the gas tank
                self.gastank += float(filedata['duration'])
            processend = time.time()
            processtook = processend - processstart
            ratio = float(filedata['duration']) / processtook
            print("File processing took", processtook, "seconds, ran at", ratio, "x...")
            # Reduce quality to improve render time
            # Or improve quality if we have render time to spare
            if ratio < self.targetspeed:
                self.crf += 1
            elif ratio > self.targetspeed:
                self.crf -= 1
            self.crf = self.clamp(self.crf, self.mincrf, self.maxcrf)
            # Adjust quality preset, too
            if ratio < (self.targetspeed - 0.5) and self.preset > 0:
                # Too slow
                # Faster preset!
                self.preset -= 1
            elif ratio > (self.targetspeed + 0.5) and self.preset < 8:
                # Too fast
                # Slower preset!
                self.preset += 1
            print("Quality preset is now:", self.qualitypresets[self.preset])
            print("CRF is now:", self.crf)
        except:
            print("Failed to obtain or process file:", filename)
            print('-' * 60)
            traceback.print_exc(file=sys.stdout)
            print('-' * 60)
            return 0
        return 1

    def convertFile(self, file):
        # First need to probe file to obtain some info about it
        print("Probing:", file, "...")
        probe = subprocess.Popen(['ffprobe',
                                  file,
                                  '-v',
                                  'quiet',
                                  '-print_format',
                                  'json=compact=1',
                                  '-show_format'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        filejson = json.loads(probe.communicate()[0].decode("utf-8"))
        # Example:
        # {'format': {'filename': 'funksqua.s3m', 'nb_streams': 1,
        #   'nb_programs': 0, 'format_name': 'libopenmpt',
        #   'format_long_name': 'Tracker formats (libopenmpt)',
        #   'duration': '206.400000', 'size': '352720',
        #   'bit_rate': '13671', 'probe_score': 76, 'tags':
        #     {'title': 'Funky Squad',
        #     'encoder': 'Scream Tracker 3.20', 'comment':
        #       'Funky Squad by\n             FireLight\n\nInspired by those hip \ncats the d-generation \nand their tv show\nfunky squad :)\nOriginal guitar samples\nmade at a friends house\nusing his guitar+wah pedal.\nSupports the global volume\neffect (fade out at end) &\nfine vibrato so make sure\nyou use a decent player.\n'
        # }}}
        filedata = {}
        try:
            filedata['filename'] = filejson['format']['filename']
        except:
            # No filename? No can do!
            print("Skipping due to no filename:", file)
            return {}
        try:
            filedata['title'] = filejson['format']['tags']['title']
        except:
            # No title? No can do!
            print("Skipping due to no title:", file)
            return {}
        try:
            filedata['artist'] = filejson['format']['tags']['artist']
        except:
            pass
        try:
            filedata['comments'] = filejson['format']['tags']['comment']
        except:
            pass
        try:
            filedata['duration'] = filejson['format']['duration']
        except:
            # No duration? No can do!
            print("Skipping due to no duration:", file)
            return {}
        # Don't allow songs longer than maxlength
        # maxlength is always half the gastanklimit
        if float(filedata['duration']) > self.maxlength:
            print("Skipping due to excessive length:", file)
            return {}
        filedata['playfile'] = file
        if 'comments' in filedata.keys():
            print("File comments:")
            print(filedata['comments'])
        filecount = str(self.filenumber + 1)
        filedata['playfile'] = 'media' + filecount + '.flv'
        filedata['textfile'] = 'media' + filecount + '.txt'
        self.makeText(filedata)
        # Then, convert to a video
        # ffmpeg -i [FILE] -y -loglevel warning -nostats -hide_banner -filter_complex "[0:a]showcqt=sono_h=0:axis=0:s=1920x1080:fps=30:bar_h=1080:cscheme=1|0|1|0|1|0:csp=bt470bg[left]; [left] drawtext=fontfile=/usr/share/fonts/TTF/Vera.ttf:fontcolor=white:x=20:y=h-mod(max(t-0.0\,0)*(h+th)/44.0\,(h+th)):text='\"Song Title\" by Artist'[out]" -map "[out]" -map 0:a -c:v libx264 -preset ultrafast -tune fastdecode -crf 31 -ar 44100 -c:a aac output.flv
        print("Converting", file, "to", filedata['playfile'], "...")
        # First conversion trims starting/ending silence and turns into AAC.
        convert = subprocess.Popen(["ffmpeg",
                                    "-i",
                                    file,
                                    "-y",
                                    "-loglevel", "warning",
                                    "-nostats",
                                    "-hide_banner",
                                    "-af",
                                    r"silenceremove=start_periods=1:stop_periods=1:detection=peak",
                                    "-ar", "44100",
                                    "-c:a", "aac",
                                    "-b:a", "128k",
                                    "out.aac"],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        print(convert.communicate()[0].decode("utf-8"))
        # Duration may have changed, so check it again.
        probe = subprocess.Popen(['ffmpeg',
                                  '-nostdin',
                                  '-hide_banner',
                                  '-nostats',
                                  '-loglevel',
                                  'info',
                                  '-i', 'out.aac',
                                  '-f', 'null',
                                  '-c', 'copy',
                                  '-'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        output = probe.communicate()[0].decode("utf-8")
        print(output)
        newduration = output.split("time=")[1].split(" ")[0]
        convertedduration = sum(x * float(t) for x, t in zip([1, 60, 3600], reversed(newduration.split(":"))))
        try:
            filedata['duration'] = convertedduration
            print("True duration is:", filedata['duration'])
        except:
            # No duration? No can do!
            print("Skipping due to no duration:", file)
            return {}
        # Cap fadeouttime at 0 seconds; don't go negative!
        fadeouttime = max(0, float(filedata['duration']) - 5.0)
        convert = subprocess.Popen(["ffmpeg",
                                    "-i",
                                    "out.aac",
                                    "-y",
                                    "-loglevel", "warning",
                                    "-nostats",
                                    "-hide_banner",
                                    "-filter_complex",
                                    r"[0:a]showcqt=sono_h=0:axis=0:s=1920x1080:fps=30:bar_h=1080:cscheme=1|0|1|0|1|0:csp=bt470bg[left]; [left] hflip [left]; [left] drawtext=fontfile=font.ttf:fontsize=24:fontcolor=white:x=20:y=h-mod(max(t-0.0\,0)*(h+th)/50.0\,(h+th)):textfile=" +
                                    filedata['textfile'] + " [out]; [out] fade=t=in:st=0:d=5,fade=t=out:st=" + str(
                                        fadeouttime) + ":d=5 [out]",
                                    "-map", "[out]",
                                    "-map", "0:a",
                                    "-c:v", "libx264",
                                    "-x264-params", "nal-hrd=cbr:force-cfr=1",
                                    "-b:v", "4.5M",
                                    "-preset", self.qualitypresets[self.preset],
                                    "-tune", "fastdecode",
                                    "-crf", str(self.crf),
                                    "-maxrate", "4.5M",
                                    "-minrate", "4.5M",
                                    "-bufsize", "9M",
                                    "-ar", "44100",
                                    "-c:a", "copy",
                                    "-g", "4",
                                    filedata['playfile']],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        print(convert.communicate()[0].decode("utf-8"))
        filesize = os.path.getsize(filedata['playfile'])
        if (filesize == 0):
            # Empty file? No good!
            print("Skipping due to conversion failure:", file)
            return {}
        # Remove original file
        os.remove(file)
        # Remove metadata text file
        os.remove(filedata['textfile'])
        # Remove reference to text file
        del filedata['textfile']
        return filedata

    def makeText(self, data):
        # Check for:
        # data['title'] - Required
        # data['filename'] - Required
        # data['artist'] - Optional
        # data['comments'] - Optional
        handle = open(data['textfile'], 'w', encoding='utf-8')
        outlines = []
        outlines.append("Title: " + data['title'] + "\n")
        if 'artist' in data.keys():
            outlines.append("Artist: " + data['artist'] + "\n")
        outlines.append("Filename: " + data['filename'] + "\n")
        if 'comments' in data.keys():
            outlines.append("Comments:\n")
            # Need to split comments if they're multi-line.
            # This is to prevent bad text wrapping behavior.
            if data['comments'].find("\n") != -1:
                commentlines = data['comments'].split("\n")
                for l in commentlines:
                    outlines.append(l + "\n")
            else:
                outlines.append(data['comments'])
        outstring = ""
        for l in outlines:
            if len(l) > self.linewidth:
                outstring += "\n".join(
                    textwrap.wrap(l, width=self.linewidth, expand_tabs=False, replace_whitespace=False,
                                  drop_whitespace=False, break_long_words=False, break_on_hyphens=False))
            else:
                outstring += l
        print("Wrapped lines:")
        print(outstring)
        handle.write(outstring)
        handle.close()

    def updatePlaylist(self, inputlist):
        # Queue up another song.
        gotsong = 0
        while not gotsong:
            lines = inputlist.split("\\n")
            choice = random.choice(lines)
            extension = choice.split(".")[-1].lower()
            if extension not in self.extensions:
                continue
            print("Selected:", choice)
            # Process the selected file.
            status = self.processFile(choice)
            # No sleep time? We didn't get a song!
            if not status:
                continue
            else:
                gotsong = 1
        self.cleanCache()
        self.updateStartup()

    def updateStartup(self):
        # Get the oldest playlist file that isn't playlist0.txt.
        # Update playlist0.txt to point to that playlist.
        filelist = glob.glob(self.mediapath + '/playlist*.txt')
        filelist.sort(key=self.naturalKeys)
        # Remove playlist0.txt 
        filelist.pop(0)
        # If we have any files left, use the first one
        try:
            newfile = filelist.pop(0)
            newplaylist = newfile.split("/")[-1]
            print("Updating playlist0.txt to start at", newplaylist, "...")
            outfile = open('/media/playlist0.txt', 'w')
            outfile.write("ffconcat version 1.0\n")
            outfile.write("file startup.flv\n")
            outfile.write("file " + newplaylist + "\n")
            outfile.close()
        except:
            # Didn't get a file, so don't change anything
            pass

    def cleanCache(self):
        timeago = time.time() - 5400  # 90 minutes
        filelist = glob.glob(self.mediapath + '/media*.flv')
        filelist.sort(key=self.naturalKeys)
        for file in filelist:
            st = os.stat(os.path.join(self.mediapath, file))
            mtime = st.st_mtime
            if mtime < timeago:
                print("Cleaning up:", file)
                number = int(''.join(list(filter(str.isdigit, file))))
                os.remove(os.path.join(self.mediapath, file))
                os.remove(os.path.join(self.mediapath, 'playlist' + str(number) + '.txt'))
        # Check disk space being used
        # If we're over 80% we need to remove files until we fall under the threshold
        filelist = glob.glob(self.mediapath + '/media*.flv')
        filelist.sort(key=self.naturalKeys)
        diskusage = shutil.disk_usage(self.mediapath)
        diskpercent = (diskusage.used / diskusage.total) * 100.0
        print("Disk usage:", diskusage.used, "of", diskusage.total, "(", diskpercent, "%)")
        while (diskusage.used / diskusage.total) > 0.8:
            done = 0
            while not done:
                # Can't operate on an empty list
                if len(filelist) == 0:
                    return
                item = filelist.pop(0)
                print("Removing file to free up disk:", item)
                number = int(''.join(list(filter(str.isdigit, item))))
                os.remove(os.path.join(self.mediapath, item))
                os.remove(os.path.join(self.mediapath, 'playlist' + str(number) + '.txt'))
                done = 1
            diskusage = shutil.disk_usage(self.mediapath)
        # Finally, check for any files in the working directory
        # Delete them if present!
        # Only keep font.ttf and djmarinara.py
        filelist = glob.glob('./*')
        for file in filelist:
            filename = Path(file).name
            if filename not in self.manifest:
                print("Removing errant temporary file:", filename)
                os.remove(file)

    def atoi(self, text):
        return int(text) if text.isdigit() else text

    def naturalKeys(self, text):
        return [self.atoi(c) for c in re.split(r'(\d+)', text)]

    def clamp(self, n, minn, maxn):
        return max(min(maxn, n), minn)


if __name__ == '__main__':
    pass
