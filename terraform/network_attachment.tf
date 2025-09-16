# Network Attachment for Private Service Connect Interface
resource "google_compute_network_attachment" "psc_attachment" {
  name                  = var.network_attachment_name
  region                = var.region
  description           = "Network attachment for Vertex AI Agent Engine Private Service Connect"
  connection_preference = "ACCEPT_AUTOMATIC"

  subnetworks = [
    google_compute_subnetwork.subnet.self_link
  ]
}

# Grant necessary IAM role to Vertex AI service agent for network operations
resource "google_project_iam_member" "vertex_network_admin" {
  project = var.project_id
  role    = "roles/compute.networkAdmin"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}

# Additional IAM role for network user access (required for Shared VPC scenarios)
resource "google_project_iam_member" "vertex_network_user" {
  project = var.project_id
  role    = "roles/compute.networkUser"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}
