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

# Google Cloud Agent Configuration
variable "google_cloud_storage_bucket" {
  description = "GCS bucket for agent staging (will be created if it doesn't exist)"
  type        = string
}

# AgentSpace Configuration
variable "agentspace_app_id" {
  description = "AgentSpace application ID"
  type        = string
}

variable "agent_display_name" {
  description = "Display name for the agent in AgentSpace"
  type        = string
  default     = "Databricks Agent"
}

variable "agent_description" {
  description = "Description of the agent"
  type        = string
  default     = "Agent para queries no Databricks com análise avançada"
}

variable "agent_icon_uri" {
  description = "URI for the agent icon"
  type        = string
  default     = "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/database/default/24px.svg"
}

# Databricks OAuth M2M Configuration
variable "databricks_client_id" {
  description = "Databricks service principal client ID for OAuth M2M authentication"
  type        = string
}

variable "databricks_client_secret" {
  description = "Databricks service principal OAuth secret for M2M authentication"
  type        = string
}

variable "databricks_host" {
  description = "Databricks workspace host URL (e.g., https://your-workspace.cloud.databricks.com)"
  type        = string
}

variable "databricks_sql_warehouse_path" {
  description = "Path to Databricks SQL warehouse (e.g., /sql/1.0/warehouses/your-warehouse-id)"
  type        = string
}

variable "databricks_catalog" {
  description = "Databricks catalog name"
  type        = string
  default     = "samples"
}

variable "databricks_schema" {
  description = "Databricks schema name"
  type        = string
  default     = "nyctaxi"
}

# Model Configuration
variable "root_agent_model" {
  description = "Model to use for the root agent"
  type        = string
  default     = "gemini-2.0-flash-exp"
}

variable "databricks_agent_model" {
  description = "Model to use for the Databricks sub-agent"
  type        = string
  default     = "gemini-2.0-flash-exp"
}

variable "analytics_agent_model" {
  description = "Model to use for the analytics sub-agent"
  type        = string
  default     = "gemini-2.0-flash-exp"
}

variable "baseline_nl2sql_model" {
  description = "Model to use for baseline NL2SQL"
  type        = string
  default     = "gemini-2.0-flash-exp"
}

# NL2SQL Configuration
variable "nl2sql_method" {
  description = "Method to use for NL2SQL conversion"
  type        = string
  default     = "BASELINE"
}

variable "authorization_id" {
  description = "Authorization ID for Databricks agent"
  type        = string
  default     = "databricks-agent-auth"
}
