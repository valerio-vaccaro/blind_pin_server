FROM debian:buster@sha256:903779f30a7ee46937bfb21406f125d5fdace4178074e1cc71c49039ebf7f48f

ENV PYTHONPATH="/usr/lib/python3.7"
ENV PYTHON_VERSION=3.7

RUN apt update -yqq \
 && apt install -yqq autoconf automake libtool swig git python3-pip python3-setuptools \
 && git clone https://github.com/ElementsProject/libwally-core.git \
 && cd libwally-core \
 && git checkout release_0.8.2 \
 && git submodule init \
 && git submodule sync --recursive \
 && git submodule update --init --recursive \
 && ln -sf /usr/local/bin/python3.6 /usr/local/bin/python3.7.6 \
 && ln -sf /usr/local/bin/python3.6 /usr/local/bin/python3.7.7 \
 && ln -sf /usr/local/bin/python3.6 /usr/local/bin/python3.7.8 \
 && ln -sf /usr/local/bin/python3.6 /usr/local/bin/python3.7.9 \
 && ln -sf /usr/local/bin/python3.6 /usr/local/bin/python3.7.10 \
 && pip3 install .


RUN apt update -yqq \
&& apt upgrade -yqq \
&& apt install --no-install-recommends -yqq procps uwsgi uwsgi-plugin-python3 nginx runit \ 
&& mkdir /etc/service/nginx \
RUN mkdir /etc/service/wsgi

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx.runit /etc/service/nginx/run
COPY wsgi.runit /etc/service/wsgi/run

WORKDIR /pinserver
COPY runit_boot.sh wsgi.ini requirements.txt wsgi.py server.py lib.py pindb.py __init__.py generateserverkey.py flaskserver.py /pinserver/
RUN pip3 install wheel
RUN pip3 install --require-hashes -r /pinserver/requirements.txt

CMD ["./runit_boot.sh"]
