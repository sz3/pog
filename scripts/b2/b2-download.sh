#!/bin/bash

if [[ -z "$B2_BUCKET_NAME" ]]; then
   echo "need to specify bucket name!"
   exit 1
fi

for f in $@; do
    SUBDIR=${f:0:2}
    b2 download-file-by-name $B2_BUCKET_NAME data/$SUBDIR/$f $f
done
