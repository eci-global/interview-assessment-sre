# FROZEN: the caller as it was applied before the refactor. Do not edit.
terraform {
  required_version = ">= 1.9.0, < 2.0.0"
  required_providers {
    terraform = { source = "terraform.io/builtin/terraform" }
  }
}

module "fleet" {
  source      = "./modules/service_fleet"
  name        = "checkout"
  environment = "prod"
  servers = [
    { name = "web-a", size = "medium" },
    { name = "web-b", size = "medium" },
    { name = "worker-a" },
  ]
  allowed_cidrs = ["10.0.0.0/8", "172.16.0.0/12"]
  tags          = { CostCenter = "1234" }
}
