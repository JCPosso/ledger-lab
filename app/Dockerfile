FROM python:3.12-slim-bookworm
# ACCEPT_MSODBC_EULA=Y acepta la licencia del driver ODBC de Microsoft; la decide quien construye.
ARG ACCEPT_MSODBC_EULA

# Driver ODBC oficial de Microsoft, necesario para Azure SQL con pyodbc.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg unixodbc \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA="${ACCEPT_MSODBC_EULA:?}" apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[mssql]"

# /data solo se usa con SQLite local; debe existir antes para que el volumen herede el dueno.
RUN useradd --create-home --uid 10001 ledger && install -d -o ledger /data
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=90s \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["uvicorn", "ledger.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
