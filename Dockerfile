FROM python:3.9.14

WORKDIR /app
COPY ./wordSquad/requirements.txt .
RUN pip3 install -r requirements.txt

COPY ./wordSquad/ ./
RUN chown -R nobody /app
USER nobody
ENV DJANGO_SETTINGS_MODULE=change_me
ENV BOT_TOKEN=change_me

ENTRYPOINT ['python', 'bot.py']
