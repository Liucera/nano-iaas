from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "terraform/gcp/main.tf").read_text(encoding="utf-8")


def test_gcp_required_apis_are_managed_by_terraform():
    assert 'resource "google_project_service" "required"' in SOURCE
    assert '"storage.googleapis.com"' in SOURCE
    assert '"iam.googleapis.com"' in SOURCE
    assert '"cloudresourcemanager.googleapis.com"' in SOURCE
    assert "disable_on_destroy = false" in SOURCE


def test_gcp_buckets_enforce_security_controls():
    assert SOURCE.count('public_access_prevention    = "enforced"') == 3
    assert SOURCE.count("uniform_bucket_level_access = true") == 3
    assert SOURCE.count("prevent_destroy = true") == 3
    assert SOURCE.count("enabled = true") >= 3


def test_gcp_reader_uses_least_privilege_without_private_key_in_state():
    assert 'resource "google_project_iam_custom_role" "nano_iaas_bucket_lister"' in SOURCE
    assert '"storage.buckets.get"' in SOURCE
    assert '"storage.buckets.list"' in SOURCE
    assert SOURCE.count('role   = "roles/storage.objectViewer"') == 3
    assert 'resource "google_service_account_key"' not in SOURCE
    assert '"roles/owner"' not in SOURCE
    assert '"roles/editor"' not in SOURCE
