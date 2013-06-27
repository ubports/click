LIB := libclickpreload.so

CC := gcc
CFLAGS := -O2 -g -Wall
LDLIBS := -ldl
prefix := /usr
libdir := $(prefix)/lib
pkglibdir = $(libdir)/click

all: $(LIB)

clean:
	rm -f $(LIB) *.o

clickpreload.o: clickpreload.c
	$(CC) -c $(CFLAGS) -fPIC -o $@ $<

$(LIB): clickpreload.o
	$(CC) -shared -Wl,-soname,$@ $(LDFLAGS) -o $@ $< $(LDLIBS)

install: $(LIB)
	mkdir -p $(DESTDIR)$(pkglibdir)
	cp -p $(LIB) $(DESTDIR)$(pkglibdir)/
