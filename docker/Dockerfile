FROM ubuntu:16.04

# install blobfuse
RUN apt-get update \
    && apt-get install -y wget apt-utils \
    && wget https://packages.microsoft.com/config/ubuntu/16.04/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y blobfuse

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
