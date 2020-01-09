from os import environ

import boto3
from botocore.exceptions import ClientError

from ..pogfs import Pogfs


BUCKET_NAME = environ.get('S3_BUCKET_NAME')


class s3fs(Pogfs):
    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or BUCKET_NAME

    def exists(self, remote_path):
        resource_s3 = boto3.resource('s3')
        try:
            resource_s3.Object(self.bucket_name, remote_path).load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                raise

    def download_file(self, remote_path, local_path):
        s3 = boto3.client('s3')
        s3.download_file(self.bucket_name, remote_path, local_path)

    def remove_file(self, remote_path):
        raise NotImplementedError()

    def list_files(self, remote_path='', recursive=True):
        s3 = boto3.client('s3')
        pag = s3.get_paginator("list_objects_v2")
        for p in pag.paginate(Bucket=self.bucket_name, Prefix=remote_path):
            for e in p.get('Contents', []):
                yield e['Key']
