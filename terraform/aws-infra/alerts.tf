# ── SNS — CANAL DE ALERTA OPERACIONAL ──

resource "aws_sns_topic" "operational_alerts" {
  name = "nano-iaas-operational-alerts-${var.environment}"

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}
