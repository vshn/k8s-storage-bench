FROM golang:1.16.5-buster as builder

RUN apt-get update && apt-get install -y patch
RUN mkdir /kubestr
WORKDIR /kubestr
RUN git clone https://github.com/kastenhq/kubestr.git .
COPY kubestr.patch .
RUN patch -p1 < kubestr.patch
RUN go build -v

FROM python:3.8-slim

RUN apt-get update -y \
    && apt-get install -y bash curl jq \
    && rm -rf /var/lib/apt/lists

COPY --from=builder /kubestr/kubestr /usr/local/bin/kubestr

RUN curl -Lo /usr/local/bin/kubectl \
    "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl

RUN mkdir -p /opt/bench

COPY requirements.txt /opt/bench/
RUN pip install -r /opt/bench/requirements.txt

COPY bench.py data.py graphs.py render.py /opt/bench/

ENTRYPOINT ["/opt/bench/bench.py"]
