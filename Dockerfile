FROM ghcr.io/hassio-addons/base:latest

LABEL maintainer="Linus Eing <linus.eing@r13.de>"

RUN apk add --no-cache python3 py3-pip

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
