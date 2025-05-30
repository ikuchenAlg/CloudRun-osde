import base64
import json
import logging
import os

from flask import Flask, request
from google.cloud import bigquery
from google.cloud import billing_budgets_v1
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth import default

# App Flask para Cloud Run
app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Variables de entorno necesarias
BILLING_ACCOUNT_ID = os.environ.get("BILLING_ACCOUNT_ID")
BQ_TABLE_FULL = os.environ.get("BQ_TABLE_FULL")  # Formato: proyecto.dataset.tabla
BQ_DATASET_PROJECT = os.environ.get("BQ_PROJECT_ID")
BUDGET_ID = os.environ.get("BUDGET_ID")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# Proyectos autorizados (puedes modificar esta lista)
PROJECT_IDS = {
    "oriproject",
    "pruebasparaosmati",
    "billingalertaccount",
}

def get_budget_limit_usd(billing_account_id: str, budget_id: str) -> float:
    client = billing_budgets_v1.BudgetServiceClient()
    name = f"billingAccounts/{billing_account_id}/budgets/{budget_id}"
    budget = client.get_budget(name=name)
    if budget.amount.WhichOneof("budget_amount") == "specified_amount":
        return float(budget.amount.specified_amount.units)
    raise ValueError("El presupuesto no tiene un límite fijo especificado.")

def get_project_spending(project_id: str) -> float:
    client = bigquery.Client(project=BQ_DATASET_PROJECT)
    query = f"""
        SELECT SUM(cost) AS total_cost
        FROM `{BQ_TABLE_FULL}`
        WHERE project.id = @project_id
          AND usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id)
        ]
    )
    result = client.query(query, job_config=job_config).result()
    for row in result:
        return float(row.total_cost or 0.0)
    return 0.0

def disable_billing(project_id: str):
    credentials, _ = default()
    billing_service = build("cloudbilling", "v1", credentials=credentials)
    project_name = f"projects/{project_id}"
    if DRY_RUN:
        logging.info(f"[DRY_RUN] Simulado: desactivaría billing en {project_id}")
        return "SIMULATED"
    try:
        billing_service.projects().updateBillingInfo(
            name=project_name,
            body={"billingAccountName": ""}
        ).execute()
        logging.info(f"✅ Billing desactivado para {project_id}")
        return "OK"
    except HttpError as e:
        logging.error(f"❌ Error HTTP al desactivar billing: {e}")
        return f"HTTP_ERROR: {e}"
    except Exception as e:
        logging.error(f"❌ Error inesperado al desactivar billing: {e}")
        return f"ERROR: {e}"

@app.route("/", methods=["POST"])
def stop_billing_handler():
    try:
        logging.info("🟢 Petición recibida.")
        envelope = request.get_json(silent=True)
        if not envelope or "message" not in envelope or "data" not in envelope["message"]:
            logging.error("⚠️ Mensaje Pub/Sub inválido.")
            return "Bad Request", 400

        decoded = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
        message = json.loads(decoded)
        project_id = message.get("project_id")

        logging.info(f"📦 Project ID recibido: {project_id}")
        if not project_id:
            return "Bad Request: missing project_id", 400

        if project_id not in PROJECT_IDS:
            return f"El proyecto '{project_id}' no está autorizado.", 403

        current_cost = get_project_spending(project_id)
        budget_limit = get_budget_limit_usd(BILLING_ACCOUNT_ID, BUDGET_ID)

        logging.info(f"💸 Gasto actual: ${current_cost:.2f} / Límite: ${budget_limit:.2f}")

        if current_cost >= budget_limit:
            result = disable_billing(project_id)
        else:
            result = "OK: dentro del límite"

        return json.dumps({
            "project_id": project_id,
            "current_cost": current_cost,
            "budget_limit": budget_limit,
            "result": result
        }), 200

    except Exception as e:
        logging.exception("🔥 Error inesperado")
        return "Internal Server Error", 500

# Solo para desarrollo local
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
