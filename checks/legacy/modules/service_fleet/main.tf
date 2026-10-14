# FROZEN: the module as it was applied in production before the refactor.
# Used only by checks/state_safety.sh to build "existing state". Do not edit.
locals {
  prefix = "${var.name}-${var.environment}"
  tags   = merge({ Environment = var.environment, Service = var.name, ManagedBy = "terraform" }, var.tags)
}

resource "terraform_data" "server" {
  count = length(var.servers)
  input = {
    name = "${var.name}_${count.index}"
    size = var.servers[count.index].size
    tags = local.tags
  }
}

resource "terraform_data" "ingress" {
  for_each = toset(var.allowed_cidrs)
  input    = { cidr = each.key, port = 443 }
}

resource "terraform_data" "data_volume" {
  triggers_replace = [local.prefix]
  input            = { name = "${local.prefix}-data", size_gb = var.volume_size_gb }
}
