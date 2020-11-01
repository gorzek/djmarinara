# djmarinara

djmarinara is an ffmpeg-based live streaming music queue manager!

* It pulls a user-defined URL which is expected to be full of *more* URLs, representing the playlist choices.
* While djmarinara is running, random URLs are chosen from the playlist URL and automatically converted into FLV videos suitable for YouTube and other streaming services.
* djmarinara also produces an endless series of playlist files. These are meant to be used by ffmpeg's `ffconcat` demuxer to act as an infinite playlist.

Note that you can see it live and in action here: https://youtube.com/gorzek/live

Believe it or not, that stream runs entirely off of a cluster of Raspberry Pi 4s!

But you probably don't care about the details. What you really want to know is...

## How do I use this?

First, pick which run method you want to use.

### Simple, Command-Line

1. Clone this repository.
1. Ensure you have Python3 installed.
1. Ensure you have `ffmpeg` and `ffprobe` in your PATH.
1. Update `src/djmarinara/main.py` with appropriate parameters. (Parameters will be described further down.)
1. Run `main.py`!
1. In another command line session, run `ffmpeg` like so: `ffmpeg -stats -re -f concat -i /media/playlist0.txt -progress - -nostats -c:v copy -c:a copy -f flv [YOUR_STREAMING_URL_HERE]"`
1. Monitor your streaming URL (YouTube works best, for now) and your startup video will play until some additional files have been pre-rendered.
1. Enjoy the show!

### Kubernetes Cluster (Raspberry Pi)

What?! You can run this in Kubernetes?!

Yes, djmarinara was initially built for a cluster of Raspberry Pi 4s.

Check out `src/ffmpeg-streamer/ffmpeg-streamer-deployment.yaml` for an example of how to run on Kubernetes.

Please note that you'll need to build your own Docker image for djmarinara with updated parameters. (Parameters will be described further down.)

### Podman (Raspberry Pi)

If you don't want to run a full Kubernetes cluster, consider `podman play kube`. You can run the manifest under `src/ffmpeg-streamer/ffmpeg-streamer-deployment.yaml` locally with podman!

Please note that the same caveats apply in terms of building your own Docker image for djmarinara with custom parameters. (Parameters will be described further down.)

## Configuration

Regardless of run method, you'll need to edit the djmarinara script to fit your needs.

For `src/djmarinara/main.py`, you can edit the following in the noted configuration section:

* `extensions` - A list of file extensions that can be downloaded and played. Only change these to add formats that ffmpeg supports! Note that archive types other than `zip` will be supported in the future.
* `temppath` - Files are stored here temporarily during processing. You shouldn't have to change this.
* `mediapath` - This is where your rendered videos and playlists are stored. If you change this, make sure when you run ffmpeg you point to the proper location for `playlist0.txt`.
* `playlisturl` - This needs to be a list of URLs of songs to play, one per line. `zip` files are fine, too, so long as they contain one or more songs. (A song is chosen at random from `zip` files containing more than one.)
* `fonturl` - URL to a font to use for rendering text on the videos. Fixed-width is preferred if playing music modules, as many contain ASCII art in their comments. Any of the fonts from this site that support code page 437 are highly recommended: https://int10h.org/oldschool-pc-fonts/
* `startupvideo` - This is a URL to a video that will be played until there are some songs queued up. Pick something a minute or two long that is pleasant to listen to and look at. :)
* `gastanklimit` - You probably won't have to change this. It defines, in seconds, how much djmarinara should have pre-rendered before taking a break. It's not perfect and will be replaced with a more adaptive method in the future.
* `targetspeed` - Target pre-rendering speed. 2.0 is a safe default, but set it higher if you have CPU to spare!

## Quirks and Limitations

This is a hobby project, so it's bound to have some peculiarities to it!

* It might crash. In Kubernetes, this is fine--it'll just restart. If you run it outside a cluster, consider running both the `main.py` script and `ffmpeg` in endless loops (in separate terminal sessions).
* When djmarinara crashes, it'll pick up where it left off when you start it again.
* The queue of pre-rendered videos is managed in a few different ways all at once. First, the `gastanklimit` defines how much play time to pre-render. Second, any video rendered more than 90 minutes ago is deleted. Third, if the disk used by `mediapath` goes above 80% full, pre-rendered songs will be deleted, starting with the oldest, until disk usage falls below 80% again. Finally, any files in the working directory where djmarinara is run *will be deleted regularly* (except for files critical to djmarinara itself.) So, don't go storing important files there! (This will be adjusted in the future, but consider it fair warning for now!)
* This app was built for Linux, and the Docker images are for 64-bit Raspberry Pi 4 systems, but you can probably run it on Windows or anything else that runs both Python3 and ffmpeg.
* Currently, only 1080p 30fps FLV videos are produced for streaming, with some hard-coded settings. Visualization is from ffmpeg's showcqt filter. These are all meant to be adjustable in the future, but they're set in stone for now. (You can, of course, edit the `djmarinara.py` module! Contributions welcome.)

## Roadmap

There are plenty of features and fixes planned. In no particular order:

* Parameterization of most ffmpeg options, allowing for more use cases than 1080p 30fps streaming of music files put through the showcqt filter. :)
* Proper health probes for the Kubernetes version.
* Parameterizing the `ffmpeg-bootstrap` image to pull its assets from another repo instead of being hard-coded.
* Parameterizing djmarinara's Docker image so it doesn't have to be rebuilt to use different settings.
* More intelligent switching from standby video to the actual playlist.
* Option to play a playlist in order instead of just randomly.
* Fix some quirks with the scrolling speed of info text when there is a *lot* of text.
* Efficiency improvements in conversion of music modules. Some use a vast amount of CPU and can have sub-real-time rendering speeds on low-power hardware.
* Add visualizer presets and make them user-configurable, while letting djmarinara choose them randomly when rendering.
* Add option to convert and play videos instead of just songs.

## Copyright Warning

Streaming copyrighted material, including music, is a fraught endeavor. Be sure that anything you stream with this tool won't get you into legal hot water. Stay safe!

