FROM python:3.12.8-bookworm

WORKDIR /app
COPY ./wordSquad/requirements.txt .
RUN pip3 install -r requirements.txt

COPY ./wordSquad/ ./
RUN chown -R nobody /app && \
    date > /app/build-time
USER nobody
ENV BOT_TOKEN=change_me

ENTRYPOINT ["/usr/local/bin/python", "./bot.py"]
