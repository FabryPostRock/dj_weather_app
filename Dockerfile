# Local Django image
# Python 3.14.6 official image, Debian slim based.
FROM python:3.14.6-slim-trixie

LABEL maintainer="fabripostrock"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/scripts:/py/bin:$PATH"

# System packages needed by Django dependencies, uWSGI and PostgreSQL client tools.
RUN apt-get update && \
    # - postgresql-client : is the client package that we're going to need installed inside our Alpine image in order for
    #   psycopg2 package to be able to connect to Postgres
    # - bash : This installs the Bash shell, an extended version of the standard Unix shell. It provides more features and 
    #   capabilities than the default Alpine Linux shell (Ash).
    # - libgcc and libstdc++ : These are the GCC (GNU Compiler Collection) runtime libraries required by some applications to run correctly.
    # - ncurses-libs: This installs the ncurses library, which provides terminal handling capabilities and is often used by 
    #   applications that require interactive terminal interfaces.
    # - sudo : add sudo package (doas is a more lightweight package)
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        curl \
        libpq-dev \
        postgresql-client \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*


COPY ./requirements.txt /tmp/requirements.txt

RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip setuptools wheel && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    rm -rf /tmp
    
# we must create volumes after the user creation because if we don't do that than volumes will be created
# with root priviledge and we will noSt be able to access these volumes
# chown generally requires sudo/root permissions. Owning the file alone is not enough to be able to change the owner.
RUN useradd --create-home --shell /bin/bash django-user && \
    mkdir -p /dj_weather_app /scripts /vol/web/static /vol/web/media && \
    chown -R django-user:django-user /dj_weather_app /scripts /vol/web

WORKDIR /dj_weather_app

COPY ./manage.py /dj_weather_app/manage.py
COPY ./config /dj_weather_app/config
COPY ./weather /dj_weather_app/weather
COPY ./db /dj_weather_app/db
COPY ./scripts/run.sh /scripts/run.sh

RUN chmod +x /scripts/run.sh && \
    chown -R django-user:django-user /dj_weather_app /scripts /vol/web

USER django-user

EXPOSE 8000

CMD ["run.sh"]
