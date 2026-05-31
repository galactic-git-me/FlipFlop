FROM alpine:3.20
RUN apk add --no-cache bash git ca-certificates tzdata findutils
WORKDIR /app
COPY sync-all.sh /usr/local/bin/sync-all.sh
RUN chmod +x /usr/local/bin/sync-all.sh
ENTRYPOINT ["/usr/local/bin/sync-all.sh"]
