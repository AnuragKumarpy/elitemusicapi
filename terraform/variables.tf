variable "aws_region" {
  type        = string
  default     = "eu-north-1"
  description = "AWS deployment region"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment name"
}

variable "worker_instance_type" {
  type        = string
  default     = "t4g.small"
  description = "EC2 ARM64 Graviton / AMD instance type for Voice Transcoding Workers"
}

variable "worker_min_size" {
  type        = number
  default     = 2
}

variable "worker_max_size" {
  type        = number
  default     = 10
}
