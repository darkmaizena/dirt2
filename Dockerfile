FROM python:3.13-slim

WORKDIR /app/dirtnet
COPY dirtnet/ /app/dirtnet/

CMD ["python", "main.py"]
