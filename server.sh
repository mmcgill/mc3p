#!/bin/sh

JVM_OPTS="-Xmx1024M -Xms1024M"
PROG_OPTS=nogui

pushd .
cd server

java $JVM_OPTS -jar minecraft_server.jar $PROG_OPTS

popd

