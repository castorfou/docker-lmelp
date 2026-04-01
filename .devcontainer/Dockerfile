FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

# Supprimer la source Yarn cassée héritée de l'image de base
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    /usr/share/keyrings/yarnkey.gpg \
    /etc/apt/sources.list.d/yarn.list.save 2>/dev/null || true
