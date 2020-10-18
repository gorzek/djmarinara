FROM gorzek/ffmpeg:arm64v8-latest

COPY djmarinara.py /home/djmarinara.py
COPY main.py /home/main.py

RUN apt-get -y update && apt-get -y install python3 openssl ca-certificates
