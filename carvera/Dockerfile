FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir asyncio

COPY . .

EXPOSE 8888/udp
EXPOSE 2222/tcp

CMD ["python", "simulated_machine.py"]
