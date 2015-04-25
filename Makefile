CFLAGS=-Wall -W -pedantic -std=c11 -g -O3

all: main

main: treebuffer.h treebuffer.c main.c

clean:
	rm -f main
