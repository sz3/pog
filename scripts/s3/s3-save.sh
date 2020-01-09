#!/bin/bash
# uses `awscli` package

if [[ -z "$S3_BUCKET_NAME" ]]; then
   echo "need to specify bucket name!"
   exit 1
fi

NAME=$1
LOCAL_PATH=$2

file_exists=$(aws s3 ls s3://$S3_BUCKET_NAME/$NAME)
if [[ -z "$file_exists" ]]; then
   aws s3 cp $LOCAL_PATH s3://$S3_BUCKET_NAME/$NAME
fi


