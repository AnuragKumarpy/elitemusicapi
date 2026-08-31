# ==============================================================================
# Security Group Matrix — Strict Zero-Trust Boundary Enforcements
# ==============================================================================

# 1. ALB Security Group (Only port 443/80 from internet/Cloudflare)
resource "aws_security_group" "alb_sg" {
  name        = "elite-alb-sg"
  description = "Allows incoming HTTPS traffic from Cloudflare / WAF"
  vpc_id      = aws_vpc.elite_vpc.id

  ingress {
    description = "HTTPS from Cloudflare/Internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description     = "Forward to App Subnet Gateway"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  tags = { Name = "elite-alb-sg" }
}

# 2. App Gateway Security Group (Port 8000 from ALB only)
resource "aws_security_group" "app_sg" {
  name        = "elite-app-sg"
  description = "Allows traffic only from ALB"
  vpc_id      = aws_vpc.elite_vpc.id

  ingress {
    description     = "HTTP from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    description = "Outbound to Redis, Postgres, and Workers"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/16"]
  }

  tags = { Name = "elite-app-sg" }
}

# 3. Voice Worker Security Group (NTgCalls WebRTC & MTProto egress)
resource "aws_security_group" "worker_sg" {
  name        = "elite-worker-sg"
  description = "Worker nodes for PyTgCalls MTProto streaming"
  vpc_id      = aws_vpc.elite_vpc.id

  ingress {
    description     = "Internal control from App Gateway"
    from_port       = 50051
    to_port         = 50051
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  egress {
    description = "Telegram MTProto WebRTC voice packets"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = { Name = "elite-worker-sg" }
}

# 4. Air-Gapped Data Security Group (PostgreSQL & Redis: App SG Ingress Only, Zero Egress)
resource "aws_security_group" "data_sg" {
  name        = "elite-data-sg"
  description = "Strictly air-gapped data layer"
  vpc_id      = aws_vpc.elite_vpc.id

  ingress {
    description     = "Redis Port 6379 from App SG"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  ingress {
    description     = "Postgres Port 5432 from App SG"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  # Zero outbound egress rules for complete air-gap protection
  tags = { Name = "elite-data-sg" }
}
