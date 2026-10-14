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

run "connection_string_is_sensitive" {
  command = plan

  module {
    source = "./modules/service_fleet"
  }

  assert {
    condition     = issensitive(output.connection_string)
    error_message = "connection_string embeds the password and must be marked sensitive"
  }
}
