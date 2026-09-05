ARG RUNNER_VERSION=2.337.0
FROM ghcr.io/actions/actions-runner:${RUNNER_VERSION}

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu openssl procps \
    && SUDO_FORCE_REMOVE=yes apt-get purge -y sudo \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /etc/sudoers.d/* \
    && (deluser runner sudo 2>/dev/null || true)

COPY --chmod=0755 entrypoint.sh /usr/local/bin/orux-runner-entrypoint
COPY --chmod=0755 healthcheck.sh /usr/local/bin/runner-healthcheck

WORKDIR /runner
ENTRYPOINT ["/usr/local/bin/orux-runner-entrypoint"]
