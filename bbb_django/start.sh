#!/bin/bash

if [ -f /var/run/django.pid ]; then
    sudo kill -9 `cat /var/run/django.pid`
fi
sudo `which python` manage.py runfcgi host=127.0.0.1 port=9090 pidfile=/var/run/django.pid minspare=1 maxspare=2
