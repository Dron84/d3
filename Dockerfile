FROM python:3.14.6-slim-trixie
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY certs /app/certs/
COPY server.py /app/server.py
COPY client.py /app/client.py
COPY d3_ca.py /app/d3_ca.py
COPY .env /app/.env
CMD ["python3", "server.py"]
EXPOSE 6666 1080
