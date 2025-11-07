import os
import json
import requests
import datetime
from datetime import timezone
from typing import Any, Dict

# SDKs de Huawei Cloud
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkrds.v3 import RdsClient
from huaweicloudsdkrds.v3.region.rds_region import RdsRegion
from obs.client import ObsClient

# Modelos de RDS
from huaweicloudsdkrds.v3.model import (
    ListAuditlogsRequest,
    ShowAuditlogDownloadLinkRequest,
    GenerateAuditlogDownloadLinkRequest,
)

# --- Variables de Configuración ---
try:
    AK = os.environ['HUAWEI_CLOUD_AK']
    SK = os.environ['HUAWEI_CLOUD_SK']
    PROJECT_ID = os.environ['HUAWEI_CLOUD_PROJECT_ID']
    RDS_INSTANCE_ID = os.environ['RDS_INSTANCE_ID']
    RDS_REGION = os.environ['RDS_REGION']
    OBS_BUCKET_NAME = os.environ['OBS_BUCKET_NAME']
except KeyError as e:
    print(f"Error Crítico: Falta la variable de entorno {e}")
    raise

OBS_ENDPOINT = f"obs.{RDS_REGION}.myhuaweicloud.com"
MAX_AUDIT_LOG_LIMIT = 50  # Límite de la API

# --- Clientes de API ---

def get_rds_client() -> RdsClient:
    """Crea y retorna un cliente RDS autenticado."""
    # El cliente RDS SÍ necesita el PROJECT_ID para la autenticación
    credentials = BasicCredentials(AK, SK, PROJECT_ID)
    return (
        RdsClient.new_builder()
        .with_credentials(credentials)
        .with_region(RdsRegion.value_of(RDS_REGION))
        .build()
    )

def get_obs_client() -> ObsClient:
    """Crea y retorna un cliente OBS autenticado."""
    # El cliente OBS (esdk-obs-python) usa access_key_id
    return ObsClient(
        access_key_id=AK,
        secret_access_key=SK,
        server=f"https://{OBS_ENDPOINT}",
    )

# --- Lógica Principal de la Función ---

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Función principal:
    1. Lista los logs de auditoría de RDS de las últimas 24 horas.
    2. Genera un enlace de descarga para cada log.
    3. Descarga el archivo y lo sube a un bucket de OBS en una carpeta por fecha.
    """
    print(f"Iniciando descarga de logs para instancia: {RDS_INSTANCE_ID}")

    try:
        # 1. Definir el Rango de Tiempo (formato UTC con offset)
        end_time = datetime.datetime.now(timezone.utc)
        start_time = end_time - datetime.timedelta(days=1)

        # Formato necesario: YYYY-MM-DDTHH:MM:SS+0000
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S%z")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S%z")
        
        print(f"Buscando logs en el rango: {start_time_str} a {end_time_str}")

        rds_client = get_rds_client()
        obs_client = get_obs_client()

        # 2. Listar los Archivos de Log
        list_req = ListAuditlogsRequest(
            instance_id=RDS_INSTANCE_ID,
            start_time=start_time_str,
            end_time=end_time_str,
            offset=0,
            limit=MAX_AUDIT_LOG_LIMIT
        )
        list_resp = rds_client.list_auditlogs(list_req)

        if not list_resp.auditlogs:
            print("No se encontraron nuevos audit logs en el rango de tiempo.")
            return {"statusCode": 200, "body": json.dumps({"message": "No new logs found."})}

        print(f"Se encontraron {len(list_resp.auditlogs)} archivos de log.")
        downloaded_files = []

        # 3. Generar Enlace, Descargar y Subir cada archivo
        for log in list_resp.auditlogs:
            print(f"Procesando archivo (ID): {log.id}")

            # 3a. Generar el enlace
            body = GenerateAuditlogDownloadLinkRequest(ids=[log.id])
            link_req = ShowAuditlogDownloadLinkRequest(
                instance_id=RDS_INSTANCE_ID,
                body=body,
            )
            link_resp = rds_client.show_auditlog_download_link(link_req)

            links = getattr(link_resp, "links", None)
            download_url = links[0] if links else None

            if not download_url:
                # ¡IMPORTANTE! Si esto falla, es un error de permisos (403)
                print(f"No se pudo generar el enlace para el ID: {log.id} (Archivo: {log.name})")
                continue  # Salta al siguiente log

            # 3b. Descargar el contenido del log
            print(f"Descargando desde {download_url[:50]}...")
            log_response = requests.get(download_url)
            log_response.raise_for_status()
            log_content = log_response.content

            
            # 3c. Crear el path de OBS (YYYYMMDD/nombre_archivo.gz)
            date_folder = ""
            try:
                # Intenta parsear la fecha de inicio del log (ej: "2025-11-06T09:03:34+0800")
                log_datetime = datetime.datetime.strptime(log.begin_time, "%Y-%m-%dT%H:%M:%S%z")
                date_folder = log_datetime.strftime("%Y%m%d")
            except (ValueError, TypeError, AttributeError):
                # Fallback: si no puede parsear, usa la fecha de hoy (UTC)
                print(f"No se pudo parsear log.begin_time, usando fecha actual.")
                date_folder = datetime.datetime.now(timezone.utc).strftime("%Y%m%d")

            # Extrae solo el nombre del archivo del path completo
            file_name = os.path.basename(log.name)

            obs_key = f"{date_folder}/{file_name}"

            print(f"Subiendo a OBS: s3://{OBS_BUCKET_NAME}/{obs_key}")
            obs_client.putContent(
                bucketName=OBS_BUCKET_NAME,
                objectKey=obs_key,
                content=log_content,
            )
            downloaded_files.append(obs_key)

        print("Proceso completado.")
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Logs descargados y guardados en OBS exitosamente.",
                    "downloaded_files": downloaded_files,
                }
            ),
        }

    except exceptions.ClientRequestException as e:
        print(f"Error de API de Huawei Cloud: {e.status_code} - {e.error_msg}")
        return {"statusCode": 500, "body": str(e)}
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar el archivo: {e}")
        return {"statusCode": 500, "body": str(e)}
    except Exception as e:
        print(f"Error inesperado: {e}")
        return {"statusCode": 500, "body": str(e)}
