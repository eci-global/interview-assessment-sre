output "server_names" {
  value = terraform_data.server[*].input.name
}

output "server_ids" {
  value = terraform_data.server[*].id
}

output "connection_string" {
  value = "postgres://app:${var.db_password}@db.${local.prefix}.internal:5432/app"
}

output   "tags" {
  value = local.tags
}
