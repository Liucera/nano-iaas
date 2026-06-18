terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Bucket S3 - Raw data
resource "aws_s3_bucket" "nano_iaas_raw" {
  bucket = "nano-iaas-raw-${var.environment}"
  tags = {
    Project     = "nano-iaas"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Bucket S3 - Processed data
resource "aws_s3_bucket" "nano_iaas_processed" {
  bucket = "nano-iaas-processed-${var.environment}"
  tags = {
    Project     = "nano-iaas"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Bucket S3 - Archive
resource "aws_s3_bucket" "nano_iaas_archive" {
  bucket = "nano-iaas-archive-${var.environment}"
  tags = {
    Project     = "nano-iaas"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Bloqueia acesso publico em todos os buckets
resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.nano_iaas_raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "processed" {
  bucket                  = aws_s3_bucket.nano_iaas_processed.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket                  = aws_s3_bucket.nano_iaas_archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Usuario IAM para o nano-iaas com permissao somente leitura
resource "aws_iam_user" "nano_iaas_reader" {
  name = "nano-iaas-reader-${var.environment}"
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_iam_user_policy" "nano_iaas_read_only" {
  name = "nano-iaas-read-only"
  user = aws_iam_user.nano_iaas_reader.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.nano_iaas_raw.arn,
          "${aws_s3_bucket.nano_iaas_raw.arn}/*",
          aws_s3_bucket.nano_iaas_processed.arn,
          "${aws_s3_bucket.nano_iaas_processed.arn}/*",
          aws_s3_bucket.nano_iaas_archive.arn,
          "${aws_s3_bucket.nano_iaas_archive.arn}/*"
        ]
      }
    ]
  })
}
