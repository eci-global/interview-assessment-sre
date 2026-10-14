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

run "rejects_malformed_cidr" {
  command = plan

  module {
    source = "./modules/service_fleet"
  }

  variables {
    allowed_cidrs = ["10.0.0.0/33"]
  }

  expect_failures = [var.allowed_cidrs]
}
