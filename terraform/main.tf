terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Data source to get project information
data "google_project" "project" {
  project_id = var.project_id
}

# VPC Network
resource "google_compute_network" "vpc" {
  name                    = var.vpc_network_name
  auto_create_subnetworks = false
  description             = "VPC network for Databricks Agent with static IP egress"
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name          = var.vpc_subnet_name
  ip_cidr_range = var.vpc_subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
  description   = "Subnet for Databricks Agent Engine with Private Service Connect"

  # Enable private Google access for internal Google API calls
  private_ip_google_access = true
}

# Enable required APIs for the project
resource "google_project_service" "required_apis" {
  for_each = toset([
    "compute.googleapis.com",
    "aiplatform.googleapis.com",
    "servicenetworking.googleapis.com",
    "dns.googleapis.com"
  ])

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}
