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

run "servers_are_keyed_by_name_and_follow_the_naming_convention" {
  command = plan

  module {
    source = "./modules/service_fleet"
  }

  assert {
    condition     = terraform_data.server["web-a"].input.name == "checkout-prod-web-a"
    error_message = "servers must be keyed by name and named <service>-<env>-<name>"
  }

  assert {
    condition     = output.server_names["worker-a"] == "checkout-prod-worker-a"
    error_message = "server_names must be a map of server name -> full name"
  }

  assert {
    condition     = terraform_data.server["worker-a"].input.size == "small"
    error_message = "size must default to small"
  }
}
