variable "name" {
  type = string
}

variable "environment" {
  type = string
}

variable "owner" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "servers" {
  type = list(object({
    name = string
    size = optional(string, "small")
  }))
}

variable "allowed_cidrs" {
  type    = list(string)
  default = []
}

variable "volume_size_gb" {
  type    = number
  default = 100
}

variable "db_password" {
  type    = string
  default = "changeme"
}
