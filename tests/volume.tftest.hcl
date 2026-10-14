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

run "data_volume_name_is_stable_and_tagged" {
  command = plan

  module {
    source = "./modules/service_fleet"
  }

  assert {
    condition     = terraform_data.data_volume.input.name == "checkout-prod-data" && terraform_data.data_volume.input.size_gb == 100
    error_message = "data volume must keep its name and default size"
  }
}
