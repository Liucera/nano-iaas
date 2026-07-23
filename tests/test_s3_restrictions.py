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
    assert '"arn:aws:s3:::${bucket}/dados/*"' in policy


def test_ecs_configures_only_official_s3_buckets():
    source = (
        ROOT / "terraform/aws-infra/main.tf"
    ).read_text(encoding="utf-8")

    assert '"nano-iaas-raw-${var.environment}"' in source
    assert '"nano-iaas-processed-${var.environment}"' in source
    assert '"nano-iaas-archive-${var.environment}"' in source
    assert '"NANO_IAAS_S3_ALLOWED_BUCKETS"' in source
