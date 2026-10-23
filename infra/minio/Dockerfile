# MinIO server + mc built from source at pinned release tags. MinIO no longer publishes free images on Docker Hub or
# quay.io (pulls are denied), so the same releases the stack was verified with are compiled here (AGPL-3.0, unmodified).
# The image keeps the layout the stack relies on: `minio` as entrypoint, `mc` on PATH (healthcheck `mc ready local`,
# backup/restore mirrors) and a shell for `--entrypoint sh` one-shots.
ARG MINIO_RELEASE=RELEASE.2024-07-16T23-46-41Z
ARG MC_RELEASE=RELEASE.2024-07-15T17-46-06Z

FROM golang:1.22.12-bookworm AS build
ARG MINIO_RELEASE
ARG MC_RELEASE
ENV CGO_ENABLED=0 GOFLAGS=-trimpath
WORKDIR /src
RUN git clone --depth 1 --branch "$MINIO_RELEASE" https://github.com/minio/minio.git minio \
 && cd minio && go build -tags kqueue -ldflags "$(go run buildscripts/gen-ldflags.go)" -o /out/minio . \
 && cd /src && git clone --depth 1 --branch "$MC_RELEASE" https://github.com/minio/mc.git mc \
 && cd mc && go build -ldflags "$(go run buildscripts/gen-ldflags.go)" -o /out/mc .

FROM alpine:3.22
RUN apk add --no-cache ca-certificates
COPY --from=build /out/minio /out/mc /usr/bin/
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
