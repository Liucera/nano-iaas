import boto3
from typing import Iterator, Dict, Any
from botocore.exceptions import ClientError

from core.provider import CloudProvider
from core.data_reader import DataReader


class S3Reader(CloudProvider):
    """Leitor de dados AWS S3 para Nano-IaaS."""
    
    name = "aws"
    
    def __init__(self):
        self.client = None
        self.session = None
        self.data_reader = DataReader()
    
    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Autentica usando profile AWS."""
        try:
            mode = profile.get('mode', 'sso')
            profile_name = profile.get('profile_name', 'default')
            
            if mode == 'sso':
                self.session = boto3.Session(profile_name=profile_name)
            else:
                self.session = boto3.Session()
            
            self.client = self.session.client('s3')
            self.client.list_buckets()
            print("✅ AWS autenticado com sucesso!")
            return True
        except Exception as e:
            print(f"❌ Falha na autenticação AWS: {e}")
            return False
    
    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista buckets S3."""
        try:
            response = self.client.list_buckets()
            for bucket in response.get('Buckets', []):
                yield {
                    'name': bucket['Name'],
                    'created': bucket['CreationDate'].isoformat(),
                    'type': 'bucket'
                }
        except ClientError as e:
            print(f"❌ Erro ao listar buckets: {e}")
    
    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        path = resource_path.replace('s3://', '')
        parts = path.split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''
        
        limit = options.get('limit', 100)
        count = 0
        
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
            
            for page in pages:
                for obj in page.get('Contents', []):
                    if count >= limit:
                        return
                    
                    key = obj['Key']
                    if key.endswith('/'):
                        continue
                    
                    response = self.client.get_object(Bucket=bucket, Key=key)
                    content = response['Body'].read()
                    
                    file_format = self.data_reader.infer_format(key)
                    
                    for record in self.data_reader.parse_raw(content, file_format):
                        record['_source'] = f"s3://{bucket}/{key}"
                        record['_last_modified'] = obj['LastModified'].isoformat()
                        record['_size'] = obj['Size']
                        yield record
                        count += 1
                        
        except ClientError as e:
            print(f"❌ Erro ao ler S3: {e}")
    
    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        path = resource_path.replace('s3://', '')
        parts = path.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        try:
            response = self.client.head_object(Bucket=bucket, Key=key)
            return {
                'bucket': bucket,
                'key': key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType', 'unknown'),
                'etag': response['ETag']
            }
        except ClientError as e:
            return {'error': str(e)}
