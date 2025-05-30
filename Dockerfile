# Imagen base ligera con Python
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Exponer el puerto esperado por Cloud Run
EXPOSE 8080

# Arrancar usando Gunicorn
CMD ["gunicorn", "--bind", ":8080", "main:app"]
