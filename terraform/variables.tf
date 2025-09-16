# Project Configuration
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for resources"
  type        = string
  default     = "us-central1"
}

# VPC Configuration
variable "vpc_network_name" {
  description = "Name of the VPC network"
  type        = string
  default     = "databricks-agent-vpc"
}

variable "vpc_subnet_name" {
  description = "Name of the VPC subnet"
  type        = string
  default     = "databricks-agent-subnet"
}

variable "vpc_subnet_cidr" {
  description = "CIDR range for the VPC subnet"
  type        = string
  default     = "10.0.0.0/24"
}

# NAT Configuration
variable "cloud_router_name" {
  description = "Name of the Cloud Router for NAT"
  type        = string
  default     = "databricks-agent-router"
}

variable "cloud_nat_gateway_name" {
  description = "Name of the Cloud NAT gateway"
  type        = string
  default     = "databricks-agent-nat"
}

variable "static_ip_count" {
  description = "Number of static IP addresses to reserve"
  type        = number
  default     = 4
}

# Network Attachment Configuration
variable "network_attachment_name" {
  description = "Name of the network attachment for Private Service Connect"
  type        = string
  default     = "databricks-agent-attachment"
}

# Agent Deployment Configuration
variable "deploy_agent" {
  description = "Whether to deploy the agent automatically via Terraform"
  type        = bool
  default     = true
}

variable "agent_deployment_script_path" {
  description = "Path to the agent deployment script"
  type        = string
  default     = "../deployment/deploy.py"
}
