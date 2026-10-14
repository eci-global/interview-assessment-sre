variable "db_password" {
  type      = string
  sensitive = true
  # Offline demo value only. Real stacks read this from a secret store.
  default = "offline-demo-value"
}

module "fleet" {
  source      = "./modules/service_fleet"
  name        = "checkout"
  environment = "prod"
  owner       = "team-sre"

  servers = [
    { name = "web-a", size = "medium" },
    { name = "web-b", size = "medium" },
    { name = "worker-a" },
  ]

  allowed_cidrs = ["10.0.0.0/8", "172.16.0.0/12"]
  tags          = { CostCenter = "1234" }
  db_password   = var.db_password
}

output "server_names" {
  value = module.fleet.server_names
}
