# ── CLOUDWATCH — ALARMES OPERACIONAIS ──

locals {
  cloudwatch_alarm_definitions = {
    alb_no_healthy_targets = {
      alarm_name          = "nano-iaas-alb-no-healthy-targets-${var.environment}"
      alarm_description   = "Nenhum target saudável disponível no ALB do Nano-IaaS."
      comparison_operator = "LessThanThreshold"
      evaluation_periods  = 2
      datapoints_to_alarm = 2
      metric_name         = "HealthyHostCount"
      namespace           = "AWS/ApplicationELB"
      period              = 60
      statistic           = "Minimum"
      threshold           = 1
      treat_missing_data  = "breaching"
      dimensions = {
        LoadBalancer = aws_lb.nano_iaas.arn_suffix
        TargetGroup  = aws_lb_target_group.nano_iaas_backend.arn_suffix
      }
    }

    alb_target_5xx = {
      alarm_name          = "nano-iaas-alb-target-5xx-${var.environment}"
      alarm_description   = "Cinco ou mais respostas 5xx dos targets em cinco minutos."
      comparison_operator = "GreaterThanOrEqualToThreshold"
      evaluation_periods  = 1
      datapoints_to_alarm = 1
      metric_name         = "HTTPCode_Target_5XX_Count"
      namespace           = "AWS/ApplicationELB"
      period              = 300
      statistic           = "Sum"
      threshold           = 5
      treat_missing_data  = "notBreaching"
      dimensions = {
        LoadBalancer = aws_lb.nano_iaas.arn_suffix
        TargetGroup  = aws_lb_target_group.nano_iaas_backend.arn_suffix
      }
    }

    alb_high_latency = {
      alarm_name          = "nano-iaas-alb-high-latency-${var.environment}"
      alarm_description   = "Latência média dos targets acima de um segundo por quinze minutos."
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 3
      datapoints_to_alarm = 3
      metric_name         = "TargetResponseTime"
      namespace           = "AWS/ApplicationELB"
      period              = 300
      statistic           = "Average"
      threshold           = 1
      treat_missing_data  = "notBreaching"
      dimensions = {
        LoadBalancer = aws_lb.nano_iaas.arn_suffix
        TargetGroup  = aws_lb_target_group.nano_iaas_backend.arn_suffix
      }
    }

    ecs_high_cpu = {
      alarm_name          = "nano-iaas-ecs-high-cpu-${var.environment}"
      alarm_description   = "CPU média do serviço ECS acima de 80% por cinco minutos."
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 5
      datapoints_to_alarm = 5
      metric_name         = "CPUUtilization"
      namespace           = "AWS/ECS"
      period              = 60
      statistic           = "Average"
      threshold           = 80
      treat_missing_data  = "notBreaching"
      dimensions = {
        ClusterName = aws_ecs_cluster.nano_iaas.name
        ServiceName = aws_ecs_service.nano_iaas_backend.name
      }
    }

    ecs_high_memory = {
      alarm_name          = "nano-iaas-ecs-high-memory-${var.environment}"
      alarm_description   = "Memória média do serviço ECS acima de 80% por cinco minutos."
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 5
      datapoints_to_alarm = 5
      metric_name         = "MemoryUtilization"
      namespace           = "AWS/ECS"
      period              = 60
      statistic           = "Average"
      threshold           = 80
      treat_missing_data  = "notBreaching"
      dimensions = {
        ClusterName = aws_ecs_cluster.nano_iaas.name
        ServiceName = aws_ecs_service.nano_iaas_backend.name
      }
    }

    rds_high_cpu = {
      alarm_name          = "nano-iaas-rds-high-cpu-${var.environment}"
      alarm_description   = "CPU média do RDS acima de 80% por cinco minutos."
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 5
      datapoints_to_alarm = 5
      metric_name         = "CPUUtilization"
      namespace           = "AWS/RDS"
      period              = 60
      statistic           = "Average"
      threshold           = 80
      treat_missing_data  = "notBreaching"
      dimensions = {
        DBInstanceIdentifier = aws_db_instance.nano_iaas.identifier
      }
    }

    rds_low_free_storage = {
      alarm_name          = "nano-iaas-rds-low-free-storage-${var.environment}"
      alarm_description   = "Armazenamento livre do RDS abaixo de 2 GiB por cinco minutos."
      comparison_operator = "LessThanThreshold"
      evaluation_periods  = 5
      datapoints_to_alarm = 5
      metric_name         = "FreeStorageSpace"
      namespace           = "AWS/RDS"
      period              = 60
      statistic           = "Minimum"
      threshold           = 2147483648
      treat_missing_data  = "missing"
      dimensions = {
        DBInstanceIdentifier = aws_db_instance.nano_iaas.identifier
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "operations" {
  for_each = local.cloudwatch_alarm_definitions

  alarm_name                = each.value.alarm_name
  alarm_description         = each.value.alarm_description
  comparison_operator       = each.value.comparison_operator
  evaluation_periods        = each.value.evaluation_periods
  datapoints_to_alarm       = each.value.datapoints_to_alarm
  metric_name               = each.value.metric_name
  namespace                 = each.value.namespace
  period                    = each.value.period
  statistic                 = each.value.statistic
  threshold                 = each.value.threshold
  treat_missing_data        = each.value.treat_missing_data
  dimensions                = each.value.dimensions
  actions_enabled           = true
  alarm_actions             = [aws_sns_topic.operational_alerts.arn]
  ok_actions                = [aws_sns_topic.operational_alerts.arn]
  insufficient_data_actions = []

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# ── CLOUDWATCH — DASHBOARD OPERACIONAL ──

resource "aws_cloudwatch_dashboard" "nano_iaas_operations" {
  dashboard_name = "nano-iaas-operations-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ALB — disponibilidade dos targets"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stacked = false
          metrics = [
            [
              "AWS/ApplicationELB",
              "HealthyHostCount",
              "LoadBalancer",
              aws_lb.nano_iaas.arn_suffix,
              "TargetGroup",
              aws_lb_target_group.nano_iaas_backend.arn_suffix,
              {
                label = "Targets saudáveis"
                stat  = "Minimum"
              }
            ],
            [
              "AWS/ApplicationELB",
              "UnHealthyHostCount",
              "LoadBalancer",
              aws_lb.nano_iaas.arn_suffix,
              "TargetGroup",
              aws_lb_target_group.nano_iaas_backend.arn_suffix,
              {
                label = "Targets não saudáveis"
                stat  = "Maximum"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ALB — respostas 5xx"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 300
          stacked = false
          metrics = [
            [
              "AWS/ApplicationELB",
              "HTTPCode_Target_5XX_Count",
              "LoadBalancer",
              aws_lb.nano_iaas.arn_suffix,
              "TargetGroup",
              aws_lb_target_group.nano_iaas_backend.arn_suffix,
              {
                label = "5xx dos targets"
                stat  = "Sum"
              }
            ],
            [
              "AWS/ApplicationELB",
              "HTTPCode_ELB_5XX_Count",
              "LoadBalancer",
              aws_lb.nano_iaas.arn_suffix,
              {
                label = "5xx do ALB"
                stat  = "Sum"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ALB — latência dos targets"
          view   = "timeSeries"
          region = var.aws_region
          period = 300
          metrics = [
            [
              "AWS/ApplicationELB",
              "TargetResponseTime",
              "LoadBalancer",
              aws_lb.nano_iaas.arn_suffix,
              "TargetGroup",
              aws_lb_target_group.nano_iaas_backend.arn_suffix,
              {
                label = "Latência média"
                stat  = "Average"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "ECS — CPU e memória"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stacked = false
          metrics = [
            [
              "AWS/ECS",
              "CPUUtilization",
              "ClusterName",
              aws_ecs_cluster.nano_iaas.name,
              "ServiceName",
              aws_ecs_service.nano_iaas_backend.name,
              {
                label = "CPU"
                stat  = "Average"
              }
            ],
            [
              "AWS/ECS",
              "MemoryUtilization",
              "ClusterName",
              aws_ecs_cluster.nano_iaas.name,
              "ServiceName",
              aws_ecs_service.nano_iaas_backend.name,
              {
                label = "Memória"
                stat  = "Average"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title   = "RDS — CPU e conexões"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stacked = false
          metrics = [
            [
              "AWS/RDS",
              "CPUUtilization",
              "DBInstanceIdentifier",
              aws_db_instance.nano_iaas.identifier,
              {
                label = "CPU"
                stat  = "Average"
              }
            ],
            [
              "AWS/RDS",
              "DatabaseConnections",
              "DBInstanceIdentifier",
              aws_db_instance.nano_iaas.identifier,
              {
                label = "Conexões"
                stat  = "Average"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title   = "RDS — capacidade disponível"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stacked = false
          metrics = [
            [
              "AWS/RDS",
              "FreeStorageSpace",
              "DBInstanceIdentifier",
              aws_db_instance.nano_iaas.identifier,
              {
                label = "Armazenamento livre"
                stat  = "Minimum"
              }
            ],
            [
              "AWS/RDS",
              "FreeableMemory",
              "DBInstanceIdentifier",
              aws_db_instance.nano_iaas.identifier,
              {
                label = "Memória disponível"
                stat  = "Minimum"
              }
            ]
          ]
        }
      }
    ]
  })
}
