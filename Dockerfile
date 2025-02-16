FROM python:3.12-slim-bookworm
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm
# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

RUN mkdir -p /data && chmod 777 /data

WORKDIR /app
COPY app.py /app

CMD ["uv","run","app.py"]
