FROM golang:1.27.3-alpine3.24 AS gosu-build

# Upstream gosu 1.20, rebuilt with a patched Go toolchain instead of Go 1.24.6.
ARG GOSU_COMMIT=29b939aa5bd4dc588af765b8248f6e39150d2565
RUN apk add --no-cache git \
    && git init /src \
    && git -C /src fetch --depth 1 https://github.com/tianon/gosu.git "${GOSU_COMMIT}" \
    && git -C /src checkout --detach FETCH_HEAD
WORKDIR /src
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
RUN go get golang.org/x/sys@v0.44.0 \
    && go mod verify \
    && go build -trimpath -ldflags=-w -o /out/gosu .

FROM postgis/postgis:17-3.5-alpine

# Preserve database engine, extensions, entrypoint, and data-directory format.
RUN apk upgrade --no-cache
COPY --from=gosu-build /out/gosu /usr/local/bin/gosu
COPY --from=gosu-build /src/LICENSE /usr/local/share/licenses/gosu/LICENSE
COPY --from=gosu-build /usr/local/go/LICENSE /usr/local/share/licenses/gosu/GO-LICENSE
COPY --from=gosu-build /go/pkg/mod/golang.org/x/sys@v0.44.0/LICENSE /usr/local/share/licenses/gosu/X-SYS-LICENSE
RUN gosu --version \
    && test "$(gosu postgres id -u)" = "$(id -u postgres)"
