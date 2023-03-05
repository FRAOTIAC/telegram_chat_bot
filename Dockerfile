FROM python:3.10-slim

RUN useradd -m appuser
USER appuser
WORKDIR /home/appuser/

ENV PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /home/appuser/app
COPY . .
COPY ./.env .

RUN pip install -r requirements.txt

CMD ["python", "main.py"]