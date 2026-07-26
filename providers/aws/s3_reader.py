import re
import boto3
from typing import Iterator, Dict, Any, Iterable, Optional, Tuple
from botocore.exceptions import ClientError

from core.provider import CloudProvider
from core.data_reader import DataReader
from core.observability import obter_logger


logger = obter_logger("providers.aws")


class S3Reader(CloudProvider):
    """Leitor de dados AWS S3 para Nano-IaaS."""

    name = "aws"
    required_prefix = "dados/"
    bucket_pattern = re.compile(
        r"(?=.{3,63}$)(?!.*\.\.)[a-z0-9][a-z0-9.-]*[a-z0-9]"
    )

    def __init__(self, allowed_buckets: Optional[Iterable[str]] = None):
        self.client = None
        self.session = None
        self.data_reader = DataReader()
        self.allowed_buckets = (
            None
            if allowed_buckets is None
            else frozenset(
                bucket.strip()
                for bucket in allowed_buckets
                if bucket.strip()
            )
        )

    def _parse_resource_path(self, resource_path: str) -> Tuple[str, str]:
        if not isinstance(resource_path, str) or not resource_path.startswith("s3://"):
            raise ValueError("Caminho S3 inválido")

        path = resource_path[len("s3://"):]
        bucket, separator, key = path.partition("/")

        if (
            not separator
            or not self.bucket_pattern.fullmatch(bucket)
            or not key.startswith(self.required_prefix)
        ):
            raise ValueError("Caminho S3 fora do prefixo permitido")

        if self.allowed_buckets is not None and bucket not in self.allowed_buckets:
            raise ValueError("Bucket S3 não autorizado")

        return bucket, key

    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Autentica usando profile AWS ou variaveis de ambiente."""
        try:
            import os
            if profile.get('access_key_id') and profile.get('secret_access_key'):
                self.session = boto3.Session(
                    aws_access_key_id=profile['access_key_id'],
                    aws_secret_access_key=profile['secret_access_key'],
                    aws_session_token=profile.get('session_token'),
                    region_name=profile.get('region_name') or os.environ.get('AWS_DEFAULT_REGION'),
                )
            elif os.environ.get('AWS_ACCESS_KEY_ID'):
                self.session = boto3.Session()
            else:
                mode = profile.get('mode', 'cli')
                profile_name = profile.get('profile_name', 'nano-iaas')
                if mode in ('sso', 'cli'):
                    self.session = boto3.Session(profile_name=profile_name)
                else:
                    self.session = boto3.Session()
            self.client = self.session.client('s3')
            return True
        except Exception:
            logger.warning("provider_authentication_failed", extra={"provider": "aws", "operation": "authenticate"})
            return False

    def validate_credentials(self) -> bool:
        """Valida as credenciais com uma chamada autenticada ao AWS STS."""
        try:
            if self.session is None:
                return False
            self.session.client("sts").get_caller_identity()
            return True
        except Exception:
            logger.warning("provider_credential_validation_failed", extra={"provider": "aws", "operation": "validate_credentials"})
            return False

    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista buckets S3."""
        if self.allowed_buckets is not None:
            for bucket in sorted(self.allowed_buckets):
                yield {
                    "name": bucket,
                    "created": None,
                    "type": "bucket",
                }
            return

        try:
            response = self.client.list_buckets()
            for bucket in response.get('Buckets', []):
                yield {
                    'name': bucket['Name'],
                    'created': bucket['CreationDate'].isoformat(),
                    'type': 'bucket'
                }
        except ClientError:
            logger.error("provider_list_failed", extra={"provider": "aws", "operation": "list_resources"})

    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        """
        Lê objetos S3.

        Args:
            resource_path: s3://bucket/prefix/ ou s3://bucket/key
        """
        bucket, prefix = self._parse_resource_path(resource_path)

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
                        if count >= limit:
                            return
                        record['_source'] = f"s3://{bucket}/{key}"
                        record['_last_modified'] = obj['LastModified'].isoformat()
                        record['_size'] = obj['Size']
                        yield record
                        count += 1

        except ClientError:
            logger.error("provider_read_failed", extra={"provider": "aws", "operation": "read"})

    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        bucket, key = self._parse_resource_path(resource_path)

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
        except ClientError:
            return {'error': 'Falha ao consultar metadados S3'}
