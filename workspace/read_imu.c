#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <termios.h>
#include <string.h>

int main() {
    int fd = open("/dev/imu", O_RDWR | O_NONBLOCK | O_NOCTTY | O_NDELAY); 
    if (fd < 0) {
        perror("Unable to open port");
        return -1;
    }
    struct termios oldtio, newtio;
    tcgetattr(fd, &oldtio);
    bzero(&newtio, sizeof(newtio));
    newtio.c_cflag = B460800 | CS8 | CLOCAL | CREAD;
    newtio.c_cflag &= ~CSTOPB;
    newtio.c_cflag &= ~PARENB;
    newtio.c_iflag = IGNPAR;  
    newtio.c_oflag = 0;
    tcflush(fd,TCIFLUSH);  
    tcsetattr(fd,TCSAFLUSH, &newtio);  
    
    unsigned char r_buffer[512];
    int total = 0;
    while(total < 128) {
        int n = read(fd, r_buffer + total, 128 - total);
        if (n > 0) total += n;
        else usleep(1000);
    }
    close(fd);
    
    for(int i=0; i<128; i++) {
        printf("%02X", r_buffer[i]);
    }
    printf("\n");
    return 0;
}
