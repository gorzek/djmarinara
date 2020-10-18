FROM nerzhul/curl-arm64:latest

# Update this to pull the relevant files from a GitHub repo.
# That way it can be managed dynamically and supply new features easily.

RUN mkdir -p /media && \
    curl -L [YOUR_STANDBY_VIDEO_HERE] > startup.flv && \
    printf "ffconcat version 1.0\n" >> playlist0.txt && \
    printf "file startup.flv\n" >> playlist0.txt && \
    printf "file playlist1.txt\n" >> playlist0.txt && \
    printf "ffconcat version 1.0\n" >> playlist1.txt && \
    printf "file startup.flv\n" >> playlist1.txt && \
    printf "file playlist0.txt\n" >> playlist1.txt

