# basic info
FROM library/ubuntu
LABEL version 0.7.3
LABEL description "Ubuntu Environment for F2FORMAT"

# prepare environment
ENV LANG "C.UTF-8"
ENV LC_ALL "C.UTF-8"
ENV PYTHONIOENCODING "UTF-8"

# install packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        software-properties-common \
 && add-apt-repository --yes ppa:deadsnakes/ppa
RUN apt-get update \
 && apt-get install --yes --no-install-recommends \
        python3.6 \
        python3-distutils \
 && ln -sf /usr/bin/python3.6 /usr/bin/python3

# copy source
COPY . /tmp/f2format
RUN cd /tmp/f2format \
 && python3 /f2format/setup.py install \
 && rm -rf /tmp/f2format

# cleanup
RUN rm -rf /var/lib/apt/lists/*\
 && apt-get remove --yes --auto-remove \
        python3-distutils \
        software-properties-common \
 && apt-get autoremove --yes \
 && apt-get autoclean \
 && apt-get clean

# final setup
RUN ln -sf /usr/bin/python3.6 /usr/bin/python3

# setup entrypoint
ENTRYPOINT [ "python3", "-m", "f2format" ]
CMD [ "--help" ]
