# Contract for modules/service_fleet. All runs are plan-only against the
# built-in terraform_data resource: no providers, no credentials, no network.

variables {
  name        = "checkout"
  environment = "prod"
  owner       = "team-sre"
  servers = [
    { name = "web-a", size = "medium" },
    { name = "worker-a" },
  ]
  allowed_cidrs = ["10.0.0.0/8"]
  db_password   = "not-a-real-secret"
}

run "allows_world_open_ingress_in_dev" {
  command = plan

  module {
    source = "./modules/service_fleet"
  }

  variables {
    environment   = "dev"
    allowed_cidrs = ["0.0.0.0/0"]
  }

  assert {
    condition     = length(terraform_data.ingress) == 1
    error_message = "dev may be open to the world"
  }
}
