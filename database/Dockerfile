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

FROM postgis/postgis:17-3.7-alpine

# Preserve database engine, extensions, entrypoint, and data-directory format.
RUN apk upgrade --no-cache

# PostGIS 3.6.4's generated upgrade list predates stable 3.5.6/3.5.7.
# Register those source versions using the vendor's unmodified ANY tag template;
# the actual schema upgrade still uses the vendor's ANY-to-current SQL.
RUN set -eu; \
    extension_dir="$(pg_config --sharedir)/extension"; \
    for template in "$extension_dir"/postgis*--TEMPLATED--TO--ANY.sql; do \
      test -f "$template"; \
      template_name="${template##*/}"; \
      extension="${template_name%--TEMPLATED--TO--ANY.sql}"; \
      for source_version in 3.5.6 3.5.7; do \
        target="$extension_dir/$extension--$source_version--ANY.sql"; \
        if [ ! -e "$target" ]; then ln -s "$template_name" "$target"; fi; \
      done; \
    done; \
    test -f "$extension_dir/postgis--3.5.7--ANY.sql"
COPY --from=gosu-build /out/gosu /usr/local/bin/gosu
COPY --from=gosu-build /src/LICENSE /usr/local/share/licenses/gosu/LICENSE
COPY --from=gosu-build /usr/local/go/LICENSE /usr/local/share/licenses/gosu/GO-LICENSE
COPY --from=gosu-build /go/pkg/mod/golang.org/x/sys@v0.44.0/LICENSE /usr/local/share/licenses/gosu/X-SYS-LICENSE
RUN gosu --version \
    && test "$(gosu postgres id -u)" = "$(id -u postgres)"
