FROM ubuntu:18.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends locales \
    && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

ENV LANG en_US.utf8

# install blobfuse
RUN apt-get update \
    && apt-get install -y wget apt-utils \
    && wget https://packages.microsoft.com/config/ubuntu/18.04/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && apt-get remove -y wget \
    && apt-get update \
    && apt-get install -y --no-install-recommends fuse blobfuse libcurl3-gnutls libgnutls30 \
    && rm -rf /var/lib/apt/lists/*

# install Python 3 per fnndsc/ubuntu-python3
RUN apt-get update \
  && apt-get install -y python3-pip python3-dev \
  && rm -rf /var/lib/apt/lists/* \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip \
  && rm -fr ~/.cache/pip


COPY mount-blobfuse.sh /
RUN chmod 755 /mount-blobfuse.sh
ENTRYPOINT ["/mount-blobfuse.sh"]
