FROM registry.access.redhat.com/ubi9-minimal:latest

ARG PIPENV_DEV=False
ARG USER_ID=1000

ENV PYTHON_VERSION=3.11 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=1 \
    PIPENV_VERBOSITY=-1 \
    APP_ROOT=/opt/costemailer \
    APP_HOME=/opt/costemailer/costemailer \
    PLATFORM="el9"

ENV SUMMARY="Koku-report-emailer is a cost report email tool for the Cost Management application" \
    DESCRIPTION="Koku-report-emailer is a cost report email tool for the Cost Management application"

LABEL summary="$SUMMARY" \
    description="$DESCRIPTION" \
    io.k8s.description="$DESCRIPTION" \
    io.k8s.display-name="Koku-report-emailer" \
    io.openshift.tags="builder,python,python311,rh-python311" \
    com.redhat.component="python311-docker" \
    name="Koku-report-emailer" \
    version="1" \
    maintainer="Red Hat Cost Management Services"

USER root

# Very minimal set of packages
# glibc-langpack-en is needed to set locale to en_US and disable warning about it
# gcc to compile some python packages (e.g. ciso8601)
# shadow-utils to make useradd available
RUN INSTALL_PKGS="python3.11 python3.11-devel glibc-langpack-en gcc-c++ shadow-utils" && \
    microdnf --nodocs -y upgrade && \
    microdnf -y --setopt=tsflags=nodocs --setopt=install_weak_deps=0 install $INSTALL_PKGS && \
    rpm -V $INSTALL_PKGS && \
    microdnf -y clean all --enablerepo='*'

# Create a Python virtual environment for use by any application to avoid
# potential conflicts with Python packages preinstalled in the main Python
# installation.
RUN python3.11 -m venv /pipenv-venv \
    && /pipenv-venv/bin/python -m pip install --upgrade pip setuptools \
    && /pipenv-venv/bin/python -m pip install pipenv
ENV PATH="/pipenv-venv/bin:$PATH"

WORKDIR ${APP_ROOT}

# install dependencies
COPY Pipfile .
COPY Pipfile.lock .
RUN \
    # install the dependencies into the working dir (i.e. ${APP_ROOT}/.venv)
    pipenv install --deploy && \
    # delete the pipenv cache
    pipenv --clear

# Runtime env variables:
ENV VIRTUAL_ENV=${APP_ROOT}/.venv
ENV \
    # Add the koku virtual env bin to the front of PATH.
    # This activates the virtual env for all subsequent python calls.
    PATH="$VIRTUAL_ENV/bin:$PATH" \
    PROMETHEUS_MULTIPROC_DIR=/tmp

# copy the src files into the workdir
COPY costemailer costemailer
COPY send_email.py .

COPY LICENSE /licenses/MIT.txt

# create the koku user
RUN \
    adduser koku -u ${USER_ID} -g 0 && \
    chmod ug+rw ${APP_ROOT} ${APP_HOME} /tmp
USER koku

# Set the default CMD.
CMD ["python", "send_email.py"]
