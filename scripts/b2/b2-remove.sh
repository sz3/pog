#!/bin/bash

if [[ -z "$B2_BUCKET_NAME" ]]; then
   echo "need to specify bucket name!"
   exit 1
fi

PATHS=$@

for f in $PATHS; do
    echo $f
    file_exists=$(b2 list-file-names $B2_BUCKET_NAME $f 1 | grep "$f")
    if [[ -n "$file_exists" ]]; then
        file_id=$(b2 list-file-names $B2_BUCKET_NAME $f 1 | grep "fileId" | awk -F\" '{print $4}')
        b2 delete-file-version $f $file_id
    fi
done
