#!/bin/sh

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command>"
    echo "  server         : launch supervisor (scheduler)"
    echo "  <cli-command>  : run CLI command (see README)"
    exit 1
fi

if [ "$1" = "server" ]; then
    exec /usr/bin/supervisord -c /app/supervisord.conf
else
    exec python /app/main.py "$@"
fi
