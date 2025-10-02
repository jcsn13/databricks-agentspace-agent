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
      export GOOGLE_CLOUD_PROJECT='${var.project_id}'
      export GOOGLE_CLOUD_LOCATION='${var.region}'
      export GOOGLE_CLOUD_STORAGE_BUCKET='${var.google_cloud_storage_bucket}'
      export AGENTSPACE_APP_ID='${var.agentspace_app_id}'
      export AGENT_DISPLAY_NAME='${var.agent_display_name}'
      export AGENT_DESCRIPTION='${var.agent_description}'
      export AGENT_ICON_URI='${var.agent_icon_uri}'
      export DATABRICKS_CLIENT_ID='${var.databricks_client_id}'
      export DATABRICKS_CLIENT_SECRET='${var.databricks_client_secret}'
      export DATABRICKS_HOST='${var.databricks_host}'
      export DATABRICKS_SQL_WAREHOUSE_PATH='${var.databricks_sql_warehouse_path}'
      export DATABRICKS_CATALOG='${var.databricks_catalog}'
      export DATABRICKS_SCHEMA='${var.databricks_schema}'
      export ROOT_AGENT_MODEL='${var.root_agent_model}'
      export DATABRICKS_AGENT_MODEL='${var.databricks_agent_model}'
      export ANALYTICS_AGENT_MODEL='${var.analytics_agent_model}'
      export BASELINE_NL2SQL_MODEL='${var.baseline_nl2sql_model}'
      export NL2SQL_METHOD='${var.nl2sql_method}'
      export AUTHORIZATION_ID='${var.authorization_id}'
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
