#!/bin/bash

#chkconfig: 2345 91 91
#description: NECOMAtter

cwd=`dirname "${0}"`
expr "${0}" : "/.*" > /dev/null || cwd=`(cd "${cwd}" && pwd)`

PATH=/sbin:/bin:/usr/sbin:/usr/bin
PROG=${cwd}/index.py
PROGNAME=NECOMAtter
DateTime=`date +%Y%m%d%H%M%S`
LOGFILE=${cwd}/logs/${PROGNAME}-${DateTime}.log
PIDFILE=${cwd}/${PROGNAME}.pid

CMD="python $PROG 8000"

if [ -f $PIDFILE ]; then
   pid=`cat $PIDFILE`
else
   pid="-1"
fi

if [ -d logs ]; then
    echo -n ''
else
    mkdir logs
fi

function start_necomatter(){
    if [ -d /proc/$pid ]; then
        echo "$PROGNAME is already started"
    else
	echo -n $"Starting $PROGNAME: "
	rm -f $PIDFILE
	$CMD > $LOGFILE 2>&1 &
	echo $! > $PIDFILE
	echo 
    fi
}

function stop_necomatter(){
    if [ -d /proc/$pid ]; then
	echo /proc/$pid
	echo -n $"Stopping $PROGNAME:"
	echo killing $pid
	kill $pid
	echo 
    fi
}

function status_necomatter(){
    if [ -d /proc/$pid ]; then
	echo "$PROGNAME is alive"
    else
	echo "$PROGNAME is dead"
    fi
}

case "$1" in
  start)
    start_necomatter
    ;;
  stop)
    stop_necomatter
    ;;
  status)
    status_necomatter
    ;;
  *)
    echo $"Usage: $PROGNAME {start|stop|status}" >&2
    exit 1
    ;;
esac
exit 0