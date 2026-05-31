FROM alpine:3.20
RUN apk add --no-cache bash git ca-certificates tzdata
WORKDIR /app
COPY sync.sh /usr/local/bin/sync.sh
RUN chmod +x /usr/local/bin/sync.sh
ENTRYPOINT ["/usr/local/bin/sync.sh"]
