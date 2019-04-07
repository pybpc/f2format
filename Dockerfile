# basic info
FROM library/ubuntu
LABEL version 0.5.2
LABEL description "Ubuntu Environment"

# prepare environment
ENV LANG "C.UTF-8"
ENV LC_ALL "C.UTF-8"
ENV PYTHONIOENCODING "UTF-8"

# install packages
RUN apt-get update \
 && apt-get install --yes python3 python3-distutils \
 && rm -rf /var/lib/apt/lists/*

# copy source
COPY . /f2format
RUN cd /f2format \
 && python3 /f2format/setup.py install

# cleanup
RUN apt-get remove python3-distutils --yes \
 && apt-get autoremove --yes \
 && apt-get autoclean \
 && apt-get clean

# setup entrypoint
ENTRYPOINT [ "python3", "-m", "f2format" ]
CMD [ "--help" ]
