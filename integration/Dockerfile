FROM python:3.11-slim
WORKDIR /workspace
COPY integration/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/core-api/app ./app
COPY services/core-api/alembic ./alembic
COPY services/core-api/alembic.ini ./alembic.ini
COPY integration ./integration
ENV PYTHONPATH=/workspace
CMD ["pytest", "integration", "-v", "--tb=short", "--junitxml=/reports/integration.xml"]
