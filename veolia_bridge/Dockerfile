ARG BUILD_FROM=mcr.microsoft.com/playwright/python:v1.65.2-noble
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY __init__.py /opt/veolia_bridge/__init__.py
COPY app /opt/veolia_bridge/app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

LABEL io.hass.type="addon" \
      io.hass.name="Veolia Bridge" \
      io.hass.arch="amd64|aarch64"

CMD ["/run.sh"]
