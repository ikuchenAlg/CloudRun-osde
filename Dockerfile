# Imagen base oficial de Python
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos necesarios
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expone el puerto que Cloud Run usará
ENV PORT=8080
EXPOSE 8080

# Comando de arranque con gunicorn
CMD ["gunicorn", "-b", ":8080", "main:app"]
