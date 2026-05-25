# syntax=docker/dockerfile:1.7

# ── Build stage ────────────────────────────────────────────────
FROM eclipse-temurin:21-jdk AS build
WORKDIR /app

# Prime the dependency cache first so code changes don't re-download the world.
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN ./mvnw -B -ntp dependency:go-offline

# Now copy sources and package.
COPY src ./src
RUN ./mvnw -B -ntp -DskipTests package \
    && mv target/*.jar target/app.jar

# ── Runtime stage ──────────────────────────────────────────────
FROM eclipse-temurin:21-jre
WORKDIR /app

# curl is used by the docker-compose healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user.
RUN useradd --system --uid 1001 --home /app spring \
    && chown spring:spring /app
USER spring

COPY --from=build /app/target/app.jar /app/app.jar

EXPOSE 8080
ENV JAVA_OPTS=""
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
