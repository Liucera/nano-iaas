import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OBSERVABILITY = (
    ROOT / "terraform/aws-infra/observability.tf"
).read_text(encoding="utf-8")
MAIN = (
    ROOT / "terraform/aws-infra/main.tf"
).read_text(encoding="utf-8")
OUTPUTS = (
    ROOT / "terraform/aws-infra/outputs.tf"
).read_text(encoding="utf-8")


def _alarm_definition(name):
    match = re.search(
        rf"^    {name} = \{{(?P<body>.*?)^    \}}$",
        OBSERVABILITY,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def test_defines_exactly_seven_operational_alarms():
    definitions = OBSERVABILITY.split(
        'resource "aws_cloudwatch_metric_alarm" "operations"',
        1,
    )[0]

    names = set(re.findall(
        r"^    ([a-z0-9_]+) = \{$",
        definitions,
        flags=re.MULTILINE,
    ))

    assert names == {
        "alb_no_healthy_targets",
        "alb_target_5xx",
        "alb_high_latency",
        "ecs_high_cpu",
        "ecs_high_memory",
        "rds_high_cpu",
        "rds_low_free_storage",
    }

    assert (
        'resource "aws_cloudwatch_metric_alarm" "operations"'
        in OBSERVABILITY
    )
    assert "for_each = local.cloudwatch_alarm_definitions" in (
        OBSERVABILITY
    )


def test_alarm_dimensions_reference_official_resources():
    assert "LoadBalancer = aws_lb.nano_iaas.arn_suffix" in (
        OBSERVABILITY
    )
    assert (
        "TargetGroup  = "
        "aws_lb_target_group.nano_iaas_backend.arn_suffix"
    ) in OBSERVABILITY
    assert "ClusterName = aws_ecs_cluster.nano_iaas.name" in (
        OBSERVABILITY
    )
    assert (
        "ServiceName = aws_ecs_service.nano_iaas_backend.name"
    ) in OBSERVABILITY
    assert (
        "DBInstanceIdentifier = "
        "aws_db_instance.nano_iaas.identifier"
    ) in OBSERVABILITY


def test_alarm_thresholds_and_missing_data_are_explicit():
    healthy = _alarm_definition("alb_no_healthy_targets")
    assert 'metric_name         = "HealthyHostCount"' in healthy
    assert 'comparison_operator = "LessThanThreshold"' in healthy
    assert "threshold           = 1" in healthy
    assert 'treat_missing_data  = "breaching"' in healthy

    target_5xx = _alarm_definition("alb_target_5xx")
    assert (
        'metric_name         = "HTTPCode_Target_5XX_Count"'
        in target_5xx
    )
    assert "period              = 300" in target_5xx
    assert 'statistic           = "Sum"' in target_5xx
    assert "threshold           = 5" in target_5xx
    assert 'treat_missing_data  = "notBreaching"' in target_5xx

    latency = _alarm_definition("alb_high_latency")
    assert 'metric_name         = "TargetResponseTime"' in latency
    assert "evaluation_periods  = 3" in latency
    assert "period              = 300" in latency
    assert "threshold           = 1" in latency

    storage = _alarm_definition("rds_low_free_storage")
    assert 'metric_name         = "FreeStorageSpace"' in storage
    assert "threshold           = 2147483648" in storage
    assert 'treat_missing_data  = "missing"' in storage


def test_dashboard_covers_required_native_metrics():
    assert (
        'resource "aws_cloudwatch_dashboard" '
        '"nano_iaas_operations"'
    ) in OBSERVABILITY
    assert OBSERVABILITY.count('type   = "metric"') == 6

    for namespace in (
        "AWS/ApplicationELB",
        "AWS/ECS",
        "AWS/RDS",
    ):
        assert namespace in OBSERVABILITY

    for metric in (
        "HealthyHostCount",
        "UnHealthyHostCount",
        "HTTPCode_Target_5XX_Count",
        "HTTPCode_ELB_5XX_Count",
        "TargetResponseTime",
        "CPUUtilization",
        "MemoryUtilization",
        "DatabaseConnections",
        "FreeStorageSpace",
        "FreeableMemory",
    ):
        assert metric in OBSERVABILITY


def test_block_8_3_does_not_create_alert_channel_or_insights():
    forbidden_actions = re.search(
        r"^\s*(alarm_actions|ok_actions|"
        r"insufficient_data_actions)\s*=",
        OBSERVABILITY,
        flags=re.MULTILINE,
    )
    assert forbidden_actions is None
    assert 'resource "aws_sns_' not in OBSERVABILITY
    assert "containerInsights" not in OBSERVABILITY
    assert "containerInsights" not in MAIN


def test_existing_log_retention_and_https_control_are_preserved():
    assert "retention_in_days = 14" in MAIN
    assert 'variable "enable_https"' in (
        ROOT / "terraform/aws-infra/variables.tf"
    ).read_text(encoding="utf-8")


def test_observability_outputs_are_declared():
    assert 'output "cloudwatch_dashboard_name"' in OUTPUTS
    assert (
        "aws_cloudwatch_dashboard.nano_iaas_operations.dashboard_name"
        in OUTPUTS
    )
    assert 'output "cloudwatch_alarm_names"' in OUTPUTS
    assert (
        "for alarm in aws_cloudwatch_metric_alarm.operations"
        in OUTPUTS
    )
