from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_aws_read_requires_dados_prefix():
    source = (ROOT / "web/backend/main.py").read_text(encoding="utf-8")

    assert 'f"s3://{bucket}/dados/"' in source
    assert 'f"s3://{bucket}/"' not in source


def test_backend_system_fallback_uses_configured_bucket_allowlist():
    source = (ROOT / "web/backend/main.py").read_text(encoding="utf-8")

    assert "NANO_IAAS_S3_ALLOWED_BUCKETS" in source
    assert "S3Reader(allowed_buckets=allowed_buckets)" in source


def test_ecs_s3_policy_uses_least_privilege():
    source = (
        ROOT / "terraform/aws-infra/main.tf"
    ).read_text(encoding="utf-8")

    start = source.index(
        'resource "aws_iam_role_policy" "ecs_task_s3_read"'
    )
    end = source.index(
        'resource "aws_ecs_task_definition" "nano_iaas_backend"',
        start,
    )
    policy = source[start:end]

    assert '"s3:ListAllMyBuckets"' not in policy
    assert '"s3:PutObject"' not in policy
    assert '"s3:DeleteObject"' not in policy
    assert 'Resource = ["*"]' not in policy

    assert '"s3:ListBucket"' in policy
    assert '"s3:GetObject"' in policy
    assert '"s3:GetBucketLocation"' in policy
    assert '"s3:prefix"' in policy
    assert '"dados/*"' in policy
    assert "local.nano_iaas_s3_allowed_bucket_arns" in policy
    assert '"${bucket_arn}/dados/*"' in policy
    assert '"arn:aws:s3:::' not in policy


def test_ecs_configures_only_official_s3_buckets():
    source = (
        ROOT / "terraform/aws-infra/main.tf"
    ).read_text(encoding="utf-8")

    assert '"raw"' in source
    assert '"processed"' in source
    assert '"archive"' in source
    assert '"nano-iaas-${each.key}-${var.environment}"' in source
    assert "aws_s3_bucket.nano_iaas_data[role].bucket" in source
    assert '"NANO_IAAS_S3_ALLOWED_BUCKETS"' in source

def test_official_s3_buckets_have_mandatory_security_controls():
    source = (
        ROOT / "terraform/aws-infra/main.tf"
    ).read_text(encoding="utf-8")

    required_resources = [
        'resource "aws_s3_bucket" "nano_iaas_data"',
        'resource "aws_s3_bucket_public_access_block" "nano_iaas_data"',
        'resource "aws_s3_bucket_ownership_controls" "nano_iaas_data"',
        'resource "aws_s3_bucket_versioning" "nano_iaas_data"',
    ]

    for resource in required_resources:
        assert resource in source

    assert (
        '"aws_s3_bucket_server_side_encryption_configuration" '
        '"nano_iaas_data"'
    ) in source

    assert "prevent_destroy = true" in source
    assert "block_public_acls       = true" in source
    assert "block_public_policy     = true" in source
    assert "ignore_public_acls      = true" in source
    assert "restrict_public_buckets = true" in source
    assert 'object_ownership = "BucketOwnerEnforced"' in source
    assert 'sse_algorithm = "AES256"' in source
    assert 'status = "Enabled"' in source
