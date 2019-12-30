#!/bin/bash

if [[ -z "$B2_BUCKET_NAME" ]]; then
   echo "need to specify bucket name!"
   exit 1
fi

NAME=$1
LOCAL_PATH=$2

file_exists=$(b2 list-file-names $B2_BUCKET_NAME $NAME 1 | grep "$NAME")
if [[ -z "$file_exists" ]]; then
   b2 upload_file $B2_BUCKET_NAME $LOCAL_PATH $NAME
fi


