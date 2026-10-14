output "server_names" { value = terraform_data.server[*].input.name }
