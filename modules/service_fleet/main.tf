locals {
  prefix = "${var.name}-${var.environment}"
  tags = merge({
    Environment = var.environment
    Service     = var.name
    ManagedBy   = "terraform"
  }, var.tags)
}

# One entry per server.
resource "terraform_data" "server" {
  count = length(var.servers)

  input = {
    name = "${var.name}_${count.index}"
    size = var.servers[count.index].size
    tags = local.tags
  }

  lifecycle {
    ignore_changes = all
  }
}

resource "terraform_data" "ingress" {
  for_each = toset(var.allowed_cidrs)

  input = {
    cidr = each.key
    port = 443
  }
}

# Holds the service's data. Losing this is an incident.
resource "terraform_data" "data_volume" {
  triggers_replace = [local.prefix]

  input = {
    name    = "${local.prefix}-data"
    size_gb = var.volume_gb
    tags    = local.tags
  }
}
