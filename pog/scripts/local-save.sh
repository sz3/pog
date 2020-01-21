#!/bin/bash

NAME=$1
LOCAL_PATH=$2

SUBDIR=$(dirname $NAME)
mkdir -p /tmp/myhome/$SUBDIR

cp $LOCAL_PATH /tmp/myhome/$NAME

