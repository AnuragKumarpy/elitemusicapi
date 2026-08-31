# ==============================================================================
# Elite Music API — Terraform Infrastructure (Zero Public Exposure VPC)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- VPC with IPv6 /56 CIDR Block ---
resource "aws_vpc" "elite_vpc" {
  cidr_block                       = "10.0.0.0/16"
  enable_dns_hostnames             = true
  enable_dns_support               = true
  assign_generated_ipv6_cidr_block = true

  tags = {
    Name        = "elite-music-vpc"
    Environment = var.environment
  }
}

# --- Internet Gateway (Ingress to Public ALB Only) ---
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.elite_vpc.id
  tags   = { Name = "elite-igw" }
}

# --- Egress-Only Internet Gateway (For Voice Workers IPv6 Media Ingestion) ---
resource "aws_egress_only_internet_gateway" "eigw" {
  vpc_id = aws_vpc.elite_vpc.id
  tags   = { Name = "elite-ipv6-eigw" }
}

# --- 1. Public Subnets (ALB & NAT Gateways Only) ---
resource "aws_subnet" "public_1a" {
  vpc_id                  = aws_vpc.elite_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "elite-public-1a" }
}

resource "aws_subnet" "public_1b" {
  vpc_id                  = aws_vpc.elite_vpc.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true
  tags                    = { Name = "elite-public-1b" }
}

# --- 2. Private App Subnets (FastAPI Gateway Fleet) ---
resource "aws_subnet" "private_app_1a" {
  vpc_id            = aws_vpc.elite_vpc.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "elite-private-app-1a" }
}

resource "aws_subnet" "private_app_1b" {
  vpc_id            = aws_vpc.elite_vpc.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.aws_region}b"
  tags              = { Name = "elite-private-app-1b" }
}

# --- 3. Private Worker Subnets with Free /64 IPv6 Block for Media Ingestion ---
resource "aws_subnet" "private_worker_1a" {
  vpc_id                          = aws_vpc.elite_vpc.id
  cidr_block                      = "10.0.20.0/24"
  ipv6_cidr_block                 = cidrsubnet(aws_vpc.elite_vpc.ipv6_cidr_block, 8, 1)
  assign_ipv6_address_on_creation = true
  availability_zone               = "${var.aws_region}a"
  tags                            = { Name = "elite-private-worker-1a" }
}

# --- 4. Air-Gapped Private Data Subnets (PostgreSQL & Redis) ---
resource "aws_subnet" "private_data_1a" {
  vpc_id            = aws_vpc.elite_vpc.id
  cidr_block        = "10.0.30.0/24"
  availability_zone = "${var.aws_region}a"
  tags              = { Name = "elite-private-data-1a" }
}

resource "aws_subnet" "private_data_1b" {
  vpc_id            = aws_vpc.elite_vpc.id
  cidr_block        = "10.0.31.0/24"
  availability_zone = "${var.aws_region}b"
  tags              = { Name = "elite-private-data-1b" }
}
