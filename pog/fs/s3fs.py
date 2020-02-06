from os import environ

import boto3
from botocore.exceptions import ClientError

from .pogfs import Pogfs


BUCKET_NAME = environ.get('S3_BUCKET_NAME')


class s3fs(Pogfs):
    def __init__(self, bucket_name=None, **kwargs):
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

    def upload_file(self, local_path, remote_path):
        s3 = boto3.client('s3')
        s3.upload_file(local_path, self.bucket_name, remote_path)

    def download_file(self, local_path, remote_path):
        s3 = boto3.client('s3')
        s3.download_file(self.bucket_name, remote_path, local_path)

    def remove_file(self, remote_path):
        s3 = boto3.client('s3')
        s3.delete_object(Bucket=self.bucket_name, Key=remote_path)

    def list_files(self, remote_path='', pattern=None, recursive=False):
        s3 = boto3.client('s3')
        pager = s3.get_paginator("list_objects_v2")

        kwargs = {
            'Bucket': self.bucket_name,
            'Prefix': remote_path,
        }
        if not recursive:
            kwargs['Delimiter'] = '/'

        for p in pager.paginate(**kwargs):
            for d in p.get('CommonPrefixes', []):
                yield d['Prefix']
            for f in p.get('Contents', []):
                filename = f['Key']
                if pattern and not self._match(filename, pattern):
                    continue
                yield filename
