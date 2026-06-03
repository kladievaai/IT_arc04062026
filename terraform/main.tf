terraform {
  required_version = ">= 1.3.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }
}

# Connect to current kubectl context (e.g., minikube)
provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = var.kube_context
}

# ─── Variables ───────────────────────────────────────────────────────────────

variable "kube_context" {
  description = "kubectl context to use (e.g. minikube)"
  type        = string
  default     = "minikube"
}

variable "image_name" {
  description = "Docker image name for the currency service"
  type        = string
  default     = "currency-service:latest"
}

variable "replicas" {
  description = "Number of pod replicas"
  type        = number
  default     = 2
}

variable "node_port" {
  description = "NodePort to expose the service on"
  type        = number
  default     = 30080
}

# ─── Deployment ──────────────────────────────────────────────────────────────

resource "kubernetes_deployment" "currency_service" {
  metadata {
    name      = "currency-service"
    namespace = "default"
    labels = {
      app = "currency-service"
    }
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app = "currency-service"
      }
    }

    template {
      metadata {
        labels = {
          app = "currency-service"
        }
      }

      spec {
        container {
          name              = "currency-service"
          image             = var.image_name
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 8000
          }

          env {
            name  = "USE_EXTERNAL_API"
            value = "false"
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "250m"
              memory = "256Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 3
            period_seconds        = 5
          }
        }
      }
    }
  }
}

# ─── Service ─────────────────────────────────────────────────────────────────

resource "kubernetes_service" "currency_service" {
  metadata {
    name      = "currency-service"
    namespace = "default"
    labels = {
      app = "currency-service"
    }
  }

  spec {
    selector = {
      app = "currency-service"
    }

    type = "NodePort"

    port {
      name        = "http"
      protocol    = "TCP"
      port        = 80
      target_port = 8000
      node_port   = var.node_port
    }
  }
}

# ─── Outputs ─────────────────────────────────────────────────────────────────

output "service_name" {
  value       = kubernetes_service.currency_service.metadata[0].name
  description = "Name of the Kubernetes Service"
}

output "node_port" {
  value       = var.node_port
  description = "NodePort exposed by the service"
}

output "deployment_name" {
  value       = kubernetes_deployment.currency_service.metadata[0].name
  description = "Name of the Kubernetes Deployment"
}
