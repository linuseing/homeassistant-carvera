# ARG BUILD_FROM
# FROM $BUILD_FROM

FROM python:3.12-slim
LABEL maintainer="Linus Eing <linus.eing@r13.de>"

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
