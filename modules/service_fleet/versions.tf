terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    # Built-in provider: ships inside the terraform binary, so there is nothing
    # to download and no version to pin beyond the CLI itself.
    terraform = {
      source = "terraform.io/builtin/terraform"
    }
  }
}
