FROM docker.sieve.com.br/alpine/py27/uwsgi20:0.0.11

#Version: 0.0.25
#Tag: infra/hollowman

ARG _=""
ENV GIT_COMMIT_HASH=${_}

ENV UWSGI_MODULE=hollowman.app:application
ENV UWSGI_PROCESSES=4

COPY requirements.txt /tmp/
RUN pip --no-cache-dir install -r /tmp/requirements.txt

COPY . /opt/app
WORKDIR /opt/app