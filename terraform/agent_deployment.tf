# Agent Engine Deployment Integration

# Deploy the agent using the existing Python script
resource "null_resource" "deploy_agent" {
  count = var.deploy_agent ? 1 : 0

  depends_on = [
    google_compute_network_attachment.psc_attachment,
    google_compute_router_nat.nat,
    google_compute_instance.proxy,
    google_compute_firewall.allow_proxy,
    google_project_iam_member.vertex_network_admin,
    google_project_iam_member.vertex_network_user,
    google_project_service.required_apis
  ]

  # Deploy the agent with network attachment
  provisioner "local-exec" {
    command = <<-EOT
      export NETWORK_ATTACHMENT_ID='${google_compute_network_attachment.psc_attachment.id}'
      export STATIC_IPS='${join(",", google_compute_address.static_ips.*.address)}'
      export PROXY_INTERNAL_IP='${google_compute_instance.proxy.network_interface[0].network_ip}'
      export PROJECT_ID='${var.project_id}'
      export REGION='${var.region}'
      python deployment/deploy.py --network-attachment
    EOT

    working_dir = "${path.module}/.."
  }

  # Trigger redeployment when these resources change
  triggers = {
    network_attachment_id = google_compute_network_attachment.psc_attachment.id
    nat_gateway_id        = google_compute_router_nat.nat.id
    static_ips            = join(",", google_compute_address.static_ips.*.address)
    deployment_script     = filemd5("${path.module}/${var.agent_deployment_script_path}")
  }
}

# Undeploy the agent when destroying infrastructure
resource "null_resource" "undeploy_agent" {
  count = var.deploy_agent ? 1 : 0

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      python deployment/undeploy.py || true
    EOT

    working_dir = "${path.module}/.."
  }

  # This runs when the deployment resource is destroyed
  depends_on = [null_resource.deploy_agent]
}

# Output the deployment status
output "agent_deployment_status" {
  description = "Status of agent deployment"
  value = var.deploy_agent ? {
    deployed           = true
    network_attachment = google_compute_network_attachment.psc_attachment.id
    static_ips_used    = google_compute_address.static_ips.*.address
    deployment_trigger = null_resource.deploy_agent[0].triggers
    message            = "Agent deployment is enabled and active"
    } : {
    deployed           = false
    network_attachment = null
    static_ips_used    = []
    deployment_trigger = null
    message            = "Agent deployment is disabled (deploy_agent = false)"
  }
}
