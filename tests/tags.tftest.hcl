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

run "mandatory_tags_cannot_be_overridden" {
  command = plan

  module {
    source = "./modules/service_fleet"
  }

  variables {
    tags = { ManagedBy = "hand", CostCenter = "1234" }
  }

  assert {
    condition     = output.tags.ManagedBy == "terraform"
    error_message = "caller tags must not override mandatory tags"
  }

  assert {
    condition     = output.tags.Owner == "team-sre" && output.tags.CostCenter == "1234"
    error_message = "Owner tag must be set from var.owner and caller tags must be kept"
  }
}
