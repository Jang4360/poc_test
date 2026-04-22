FROM eclipse-temurin:21-jre

ARG GH_VERSION=8.0

WORKDIR /opt/graphhopper

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget \
    && wget -q "https://github.com/graphhopper/graphhopper/releases/download/${GH_VERSION}/graphhopper-web-${GH_VERSION}.jar" -O graphhopper.jar \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8989

ENTRYPOINT ["java", "-Xms1g", "-Xmx4g", "-jar", "/opt/graphhopper/graphhopper.jar", "server", "/config/config.yaml"]
