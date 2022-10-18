FROM python:3.9.14

WORKDIR /app
COPY ./myproj/requirements.txt .
RUN pip3 install -r requirements.txt

COPY ./myproj/*.* .
RUN chown -R nobody /app
USER nobody
ENV DJANGO_SETTINGS_MODULE=myproj.settings-tg
ENV BOT_TOKEN=change_me

ENTRYPOINT ['python3', 'bot.py']
