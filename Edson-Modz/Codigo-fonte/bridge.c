/* C / bridge.c / Linux x86 static / rooted Android emulator; read-only memory transport */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stddef.h>
#include <signal.h>

static int exact(int fd, void *p, size_t n, int sending) {
    char *b=p;
    while(n) {
        ssize_t k=sending ? write(fd,b,n) : read(fd,b,n);
        if(k<0 && errno==EINTR) continue;
        if(k<=0) return -1;
        b+=k;n-=k;
    }
    return 0;
}
int main(int argc,char **argv) {
    if(argc!=4 || strlen(argv[2])>90 || strlen(argv[3])!=64) return 2;
    char *end;long pid=strtol(argv[1],&end,10);
    if(*end || pid<=1) return 2;
    char path[80];snprintf(path,sizeof(path),"/proc/%ld/mem",pid);
    int mem=open(path,O_RDONLY|O_CLOEXEC);if(mem<0) return 3;
    int server=socket(AF_UNIX,SOCK_STREAM,0);if(server<0)return 4;
    struct sockaddr_un addr={0};addr.sun_family=AF_UNIX;
    memcpy(addr.sun_path+1,argv[2],strlen(argv[2]));
    if(bind(server,(struct sockaddr*)&addr,offsetof(struct sockaddr_un,sun_path)+1+strlen(argv[2]))<0)return 5;
    if(listen(server,1)<0)return 6;
    signal(SIGPIPE,SIG_IGN);alarm(30);
    int client=accept(server,NULL,NULL);if(client<0)return 7;
    char token[64];if(exact(client,token,64,0)||memcmp(token,argv[3],64))return 8;
    uint32_t hello=0x314d4445;if(exact(client,&hello,4,1))return 9;
    unsigned char *buffer=malloc(262144);if(!buffer)return 10;
    for(;;) {
        uint32_t request[2];alarm(30);
        if(exact(client,request,8,0))break;
        if(!request[1]||request[1]>262144)break;
        ssize_t got=pread(mem,buffer,request[1],(off_t)request[0]);
        int32_t status=got<0 ? -errno : (int32_t)got;
        if(exact(client,&status,4,1))break;
        if(got>0 && exact(client,buffer,got,1))break;
    }
    free(buffer);close(client);close(server);close(mem);return 0;
}
