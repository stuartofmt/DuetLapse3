## Building ffmpeg 

Here are the steps I went through to build a more up-to-date ffmpeg (well - the straight line version that avoids the various dead ends and failures to compile the optional packages).  They were taken from here but shortened to omit the optional packages in the post and using a build that omits calling those packages.

https://pimylifeup.com/compiling-ffmpeg-raspberry-pi/



1. Remove existing ffmpeg

```
sudo apt remove ffmpeg
```

2. Make sure OS is up to date

```
sudo apt update
sudo apt upgrade
```

3. Install dependencies

```
sudo apt -y install autoconf automake build-essential cmake doxygen git graphviz imagemagick libasound2-dev libass-dev libavcodec-dev libavdevice-dev libavfilter-dev libavformat-dev libavutil-dev libfreetype6-dev libgmp-dev libmp3lame-dev libopencore-amrnb-dev libopencore-amrwb-dev libopus-dev librtmp-dev libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-net-dev libsdl2-ttf-dev libsnappy-dev libsoxr-dev libssh-dev libssl-dev libtool libv4l-dev libva-dev libvdpau-dev libvo-amrwbenc-dev libvorbis-dev libwebp-dev libx264-dev libx265-dev libxcb-shape0-dev libxcb-shm0-dev libxcb-xfixes0-dev libxcb1-dev libxml2-dev lzma-dev meson nasm pkg-config python3-dev python3-pip texinfo wget yasm zlib1g-dev libdrm-dev
```


4. Build ffmpeg (takes a while)

```
git clone --depth 1 https://github.com/FFmpeg/FFmpeg.git ~/FFmpeg \
  && cd ~/FFmpeg \
  && ./configure \
    --extra-cflags="-I/usr/local/include" \
    --extra-ldflags="-L/usr/local/lib" \
    --extra-libs="-lpthread -lm -latomic" \
    --arch=armel \
    --enable-gmp \
    --enable-gpl \
    --enable-libass \
    --enable-libdrm \
    --enable-libfreetype \
    --enable-libmp3lame \
    --enable-libopencore-amrnb \
    --enable-libopencore-amrwb \
    --enable-libopus \
    --enable-librtmp \
    --enable-libsnappy \
    --enable-libsoxr \
    --enable-libssh \
    --enable-libvorbis \
    --enable-libwebp \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libxml2 \
    --enable-mmal \
    --enable-nonfree \
    --enable-omx \
    --enable-omx-rpi \
    --enable-version3 \
    --target-os=linux \
    --enable-pthreads \
    --enable-openssl \
    --enable-hardcoded-tables \
  && make -j$(nproc) \
  && sudo make install
```
### Note that I also compiled this Debian on windows with the following changes:
replace -arch=armel with -arch-x86
delete: --enable-mmal, --enable-omx, --enable-omx-rpi
  
  5.  Check the  ffmpeg version
  
```
pi@srsenderpi:~ $ ffmpeg -version
ffmpeg version git-2020-12-22-a7f9b3b Copyright (c) 2000-2020 the FFmpeg developers
built with gcc 8 (Raspbian 8.3.0-6+rpi1)
configuration: --extra-cflags=-I/usr/local/include --extra-ldflags=-L/usr/local/lib --extra-libs='-lpthread -lm -latomic' --arch=armel --enable-gmp --enable-gpl --enable-libass --enable-libdrm --enable-libfreetype --enable-libmp3lame --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopus --enable-librtmp --enable-libsnappy --enable-libsoxr --enable-libssh --enable-libvorbis --enable-libwebp --enable-libx264 --enable-libx265 --enable-libxml2 --enable-mmal --enable-nonfree --enable-omx --enable-omx-rpi --enable-version3 --target-os=linux --enable-pthreads --enable-openssl --enable-hardcoded-tables
libavutil      56. 62.100 / 56. 62.100
libavcodec     58.115.102 / 58.115.102
libavformat    58. 65.100 / 58. 65.100
libavdevice    58. 11.103 / 58. 11.103
libavfilter     7. 94.100 /  7. 94.100
libswscale      5.  8.100 /  5.  8.100
libswresample   3.  8.100 /  3.  8.100
libpostproc    55.  8.100 / 55.  8.100
```

Check that tpad is available

```
 ffmpeg - filters | grep tpad
```

### NOTE:  Sometimes the directories where the new ffmeg is installed get "confused".
If ffmpeg - version gives an error note the path that it is trying to use (oldpath)
Then run
```
whereis ffmpeg
```
and note the path (newpath). You can then create a symbolic ling and all should be well

```
sudo ln -s newpath oldpath
```
