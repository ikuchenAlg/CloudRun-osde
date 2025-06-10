FROM python:3.8-slim

WORKDIR /app

# Copia solo primero los archivos de dependencias
COPY requirements.txt .

# Instala dependencias primero (mejor para cache)
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Expone el puerto que Flask/gunicorn usará (opcional pero informativo)
EXPOSE 8080

# CMD para producción con gunicorn (recomendado)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]

