# title

FFmpeg零基础入门到实战教程， 适合新手小白入门

## log

p31

```c
#include<stdio.h>
#include<libavutil/log.h>

int main(int avgc, char* argv[]){
  av_log_set_level(AV_LOG_DEBUG);
  av_log(NULL, AV_LOG_INFO, "Hello, World! %s\n", "aaa");
  return 0;
}
```

clang -g -o ffmpeg_log ffmpeg_log.c -lavutil

p32

```sh
clang -g -o ff_log ff_log.c -I/usr/local/ffmpeg/include -L/usr/local/ffmpeg/lib -lavutil

# =>

clang -g -o ff_log ff_log.c `pkg-config --cflags --libs libavutil` -lavutil
```

## file operations

p33

```c
#include <libavformat/avformat.h>

avpriv_io_delete()

avpriv_io_move()
```

p34

avio_open_dir()
avio_read_dir()
avio_close_dir()

AVIODirContext
AVIODirEntry

```c
#include<libavutil/log.h>
#include<libavformat/avformat.h>

int main(int avgc, char* argv[]){

  int ret;

  AVIODirContext *ctx = NULL;
  AVIODirEntry *entry = NULL;
  av_log_set_level(AV_LOG_DEBUG);

  ret = avio_open_dir(&ctx, "./", NULL);
  if(ret < 0) {
    av_log(NULL, AV_LOG_ERROR, "Can't open dir %s\n", av_err2str(ret));
    return -1;
  }

  while(1) {
    ret = avio_read_dir(ctx, &entry);

    if(ret < 0) {
      av_log(NULL, AV_LOG_ERROR, "Can't read dir %s\n", av_err2str(ret));
      return -1;
    }

    if(!entry) {
      break;
    }
  }

  av_log(NULL, AV_LOG_INFO, "%12"PRId64" %s \n", entry->size, entry->name);

  return 0;
}
```
