# ⚙️ Automatización de Descarga de Logs de Auditoría RDS

Esta solución utiliza **FunctionGraph** de **Huawei Cloud** para **automatizar la descarga de logs de auditoría (Audit Logs)** de una instancia de **RDS PostgreSQL**.
Los logs se guardan en un bucket de **OBS (Object Storage Service)**, organizados por fecha, para su **almacenamiento permanente, análisis** y **cumplimiento de normativas**.

---

## ⚙️ Cómo Funciona (Métodos de API Utilizados)

La lógica principal de la función (`index.py`) realiza tres acciones clave utilizando los SDKs oficiales de Huawei Cloud, que corresponden a las siguientes llamadas de API:

* **1. `ListAuditlogs` (API de RDS):** Para obtener la lista de archivos de log disponibles que coinciden con el rango de tiempo.
* **2. `ShowAuditlogDownloadLink` (API de RDS):** Para generar una URL de descarga segura y temporal para cada archivo de log (usando el `log.id`).
* **3. `putContent` (API de OBS):** Para subir el contenido del log descargado directamente al bucket de OBS de destino (usando el SDK `esdk-obs-python`).

---

## 🗂️ Requisitos Previos

Antes de comenzar, asegúrese de contar con:

* ✅ Una cuenta de **Huawei Cloud** con permisos de administrador (**IAM**).
* ✅ Una instancia de **RDS PostgreSQL** ya creada y en ejecución.
* ✅ Un **bucket de OBS** ya creado.
* ✅ **Python 3** y **pip** instalados localmente (para preparar el paquete de código).
* ✅ Los archivos de esta solución: `index.py` y `requirements.txt`.

---

## 🚀 Pasos de Despliegue

Siga los siguientes pasos en orden para configurar la solución completa.

---

### **1️⃣ Configurar la Instancia de RDS**

> La función solo puede descargar logs que la base de datos esté generando.

#### **1.1. Instalar el plugin `pgAudit`**

1.  Vaya a la consola de **RDS**.
2.  Seleccione su instancia de **PostgreSQL**.
3.  En el menú lateral, abra **Plugins**.
4.  Busque **`pgAudit`** y haga clic en **Install**.

#### **1.2. Activar "SQL Audit"**

1.  En el menú de la instancia, vaya a **Logs → SQL Audit Logs**.
2.  Haga clic en **Set SQL Audit**.
3.  Active el interruptor para habilitar la auditoría.
4.  Establezca un **período de retención** (ej. 7 días).
5.  Haga clic en **OK**.

> 💡 **Nota:** Después de activar la auditoría, genere actividad en la base de datos (crear tablas, insertar datos, etc.) y **espere entre 30–40 minutos** hasta que los primeros archivos de log aparezcan.

---

### **2️⃣ Crear los Permisos (Agencia de IAM)**

> La función necesita permisos para comunicarse con otros servicios.

1.  Vaya a la consola de **IAM (Identity and Access Management)**.
2.  En el menú lateral, seleccione **Agencies → Create Agency**.
3.  Configure los siguientes campos:

    * **Agency Type:** `Cloud Service`
    * **Cloud Service:** `FunctionGraph`
4.  En **Permissions**, haga clic en **Authorize** y asigne:

    * **`FunctionGraph Administrator`**
    * **`RDS ManageAccess`**
    * **`OBS Administrator`** → o una política personalizada con permisos `PutObject` sobre el bucket destino.
5.  **Name:** `FunctionGraph-RDS-OBS-Agency`
6.  Haga clic en **OK** para crear la agencia.

---

### **3️⃣ Preparar el Paquete de Código (.zip)**

1.  Cree una carpeta local, por ejemplo: `AuditLogsDownloader`.
2.  Coloque dentro los archivos `index.py` y `requirements.txt`.
3.  Abra una terminal y navegue dentro de la carpeta:

    ```bash
    cd ruta/a/AuditLogsDownloader
    ```
4.  Instale las dependencias dentro de esa misma carpeta:

    ```bash
    pip install -r requirements.txt -t .
    ```

    > En Windows, si `pip` no se reconoce:
    > `py -m pip install -r requirements.txt -t .`
5.  Verifique que aparezcan las librerías (`requests`, `obs`, `huaweicloudsdkrds`, etc.).
6.  Comprima el contenido (no la carpeta entera):

    * Seleccione **todo el contenido** dentro de `AuditLogsDownloader`.
    * Clic derecho → **Comprimir en .zip**.
    * Nómbrelo `AuditLogsDownloader.zip`.

> ⚠️ **Error común:** no comprimir la carpeta raíz completa; el `.zip` debe contener directamente los archivos y librerías.

---

### **4️⃣ Crear y Desplegar la Función**

1.  Ingrese a la consola de **FunctionGraph**.
2.  Haga clic en **Create Function**.
3.  Configure:

    * **Create With:** `Create from scratch`
    * **Function Type:** `Event function`
    * **Name:** `AuditLogsDownloader`
    * **Agency:** la creada en el Paso 2 (`FunctionGraph-RDS-OBS-Agency`)
    * **Runtime:** `Python 3.9`
4.  Haga clic en **Create Function**.

---

### **5️⃣ Configurar la Función**

1.  Una vez creada la función, vaya a la pestaña **"Code"** (Código).
2.  En el apartado de **"Code Source"** haga click en **`Upload`** → Local ZIP.
3.  Suba el archivo `AuditLogsDownloader.zip` que creó.
4.  Haga clic en **Save**.
5.  Ahora vaya a la pestaña **"Configuration"** (Configuración) y abra **"Basic Settings"**.
6.  Aumente **Initialization Timeout** a **`30` segundos** (el .zip es grande y tarda en cargar).
7.  En **"Environment Variables"**, añada las siguientes variables:

*   **`HUAWEI_CLOUD_AK`**: `xxxxxx` (Access Key de IAM)
*   **`HUAWEI_CLOUD_SK`**: `xxxxxx` (Secret Key de IAM)
*   **`HUAWEI_CLOUD_PROJECT_ID`**: `xxxxxx` (ID del proyecto regional)

    *Para obtener estas credenciales:*
    1.  Haga clic en el nombre de su cuenta (esquina superior derecha).
    2.  Seleccione **My Credentials**.

*   **`RDS_INSTANCE_ID`**: `rds-xxxxxx` (ID de la instancia RDS)
*   **`RDS_REGION`**: `la-south-2` (Región de la instancia RDS)
*   **`OBS_BUCKET_NAME`**: `mi-bucket-de-logs` (Nombre del bucket destino en OBS)
---

### **6️⃣ Automatizar (Configurar el Trigger)**

1.  Abra la pestaña **Triggers**.
2.  Haga clic en **Create Trigger**.
3.  Configure:

    * **Trigger Type:** `Timer`
    * **Trigger Period:** `CRON expression`
    * **Ejemplos de CRON:**

        * `0 2 * * *` → Ejecuta todos los días a las **02:00 AM (UTC)**
        * `0 */1 * * *` → Ejecuta **cada hora**
4.  Haga clic en **OK**.

---

### **7️⃣ Prueba y Verificación**

1.  Vaya a la pestaña **Test**.
2.  Ejecute una prueba con un evento vacío `{}`.
3.  En la **salida del log**, debería ver mensajes como:

    ```
    Buscando logs en el rango: 2025-11-06T14:30:00+0000 a 2025-11-07T14:30:00+0000
    Formato de rango aceptado (utc_offset)
    Se encontraron 2 archivos de log.
    Procesando archivo (ID): fa163e86...
    Descargando desde ...
    Subiendo a OBS: s3://mi-bucket-de-logs/20251107/log-archivo-1.gz
    Procesando archivo (ID): fa163e87...
    Descargando desde ...
    Subiendo a OBS: s3://mi-bucket-de-logs/20251107/log-archivo-2.gz
    Proceso completado.
    ```
4.  Verifique en su **bucket de OBS** que se haya creado una carpeta con la fecha (por ejemplo `20251107`) y los archivos `.gz` correspondientes.

---

## 📁 Estructura del Proyecto

La estructura del proyecto antes de comprimir debe verse así:

````

AuditLogsDownloader/
│
├── index.py
├── requirements.txt
├── obs/
├── requests/
├── huaweicloudsdkcore/
├── huaweicloudsdkrds/
└── (otras dependencias instaladas por pip)

```

> 💡 **Importante:**
> El archivo `.zip` debe contener directamente el contenido de esta carpeta (no la carpeta `AuditLogsDownloader` entera).
> Ejemplo correcto al abrir el `.zip`: se deben ver `index.py`, `requirements.txt` y las carpetas de librerías en la raíz.
```
